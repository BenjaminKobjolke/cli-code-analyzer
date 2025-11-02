"""
Dart Code Linter (DCM) rule for Flutter/Dart code metrics analysis
"""

import subprocess
import json
import csv
import shutil
import platform
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any
from rules.base import BaseRule
from models import Violation, Severity, LogLevel
from settings import Settings


class DartCodeLinterRule(BaseRule):
    """Rule to analyze Dart/Flutter code metrics using dart_code_linter"""

    def __init__(self, config: dict, base_path: Path = None, output_folder: Optional[Path] = None, log_level: LogLevel = LogLevel.ALL, max_errors: Optional[int] = None, rules_file_path: str = None):
        """Initialize Dart Code Linter rule.

        Args:
            config: Rule configuration from rules.json
            base_path: Base path for analysis
            output_folder: Optional folder for file output (None = console output)
            log_level: Log level for filtering violations
            max_errors: Optional limit on number of violations to include in CSV
            rules_file_path: Path to the rules.json file
        """
        super().__init__(config, base_path, max_errors, rules_file_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._executed = False  # Track if dart_code_linter has been executed
        self.project_root = None  # Will be set when pubspec.yaml is found

    def check(self, file_path: Path) -> List[Violation]:
        """Run dart_code_linter on the entire project (only once).

        Note: dart_code_linter analyzes entire projects, not individual files.
        This method will execute once on the first file and return empty for subsequent files.

        Args:
            file_path: Path to a file (used to determine base directory)

        Returns:
            List of violations found (only on first execution)
        """
        # Only execute once per analysis run
        if self._executed:
            return []

        self._executed = True

        print("\nChecking dart_code_linter metrics...")

        # Get dart path
        dart_path = self._get_or_prompt_dart_path()
        if not dart_path:
            return []

        # Check if dart_code_linter is installed in the project
        if not self._check_dart_code_linter_installed():
            if self.config.get('auto_install', False):
                if not self._install_dart_code_linter(dart_path):
                    return []
            else:
                print("Warning: dart_code_linter is not installed in this project")
                print("Run: dart pub add --dev dart_code_linter")
                print("Or set 'auto_install': true in rules.json")
                return []

        # Run dart_code_linter
        violations = self._run_dart_code_linter(dart_path)

        return violations

    def _get_or_prompt_dart_path(self) -> Optional[str]:
        """Get dart path from settings or PATH, or prompt user.

        Returns:
            Path to dart executable or None if failed
        """
        # First check if dart is in PATH
        dart_in_path = shutil.which('dart')
        if dart_in_path:
            return dart_in_path

        # Check settings
        dart_path = self.settings.get_dart_path()

        if not dart_path:
            # Prompt user to provide path
            dart_path = self.settings.prompt_and_save_dart_path()
            if not dart_path:
                return None

        # Validate path exists
        if not Path(dart_path).exists():
            print(f"Error: Dart executable not found at: {dart_path}")
            print("Please update the path in settings.ini or delete settings.ini to reconfigure")
            return None

        return dart_path

    def _check_dart_code_linter_installed(self) -> bool:
        """Check if dart_code_linter is listed in pubspec.yaml.

        Searches for pubspec.yaml in base_path, then parent directory.
        Sets self.project_root when pubspec.yaml is found.

        Returns:
            True if dart_code_linter is in dev_dependencies
        """
        # Try base_path first
        pubspec_path = self.base_path / 'pubspec.yaml'

        # If not found in base_path, try parent directory (common when analyzing lib/ folder)
        if not pubspec_path.exists():
            pubspec_path = self.base_path.parent / 'pubspec.yaml'

        if not pubspec_path.exists():
            print(f"Warning: pubspec.yaml not found in {self.base_path} or parent directory")
            return False

        # Store project root for later use
        self.project_root = pubspec_path.parent

        try:
            with open(pubspec_path, 'r', encoding='utf-8') as f:
                pubspec_data = yaml.safe_load(f)

            if not pubspec_data:
                return False

            dev_dependencies = pubspec_data.get('dev_dependencies', {})
            if dev_dependencies and 'dart_code_linter' in dev_dependencies:
                return True

            return False

        except Exception as e:
            print(f"Error reading pubspec.yaml: {e}")
            return False

    def _install_dart_code_linter(self, dart_path: str) -> bool:
        """Install dart_code_linter using dart pub add.

        Args:
            dart_path: Path to dart executable

        Returns:
            True if installation succeeded
        """
        print("dart_code_linter not found. Installing...")

        # Use project_root if found, otherwise fall back to base_path
        install_dir = self.project_root if self.project_root else self.base_path

        cmd = [dart_path, 'pub', 'add', '--dev', 'dart_code_linter']
        use_shell = platform.system() == 'Windows'

        try:
            result = subprocess.run(
                cmd,
                cwd=install_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace',  # Replace invalid characters instead of crashing
                check=False,
                shell=use_shell
            )

            if result.returncode == 0:
                print("dart_code_linter installed successfully\n")
                return True
            else:
                print(f"Failed to install dart_code_linter: {result.stderr}")
                return False

        except Exception as e:
            print(f"Error installing dart_code_linter: {e}")
            return False

    def _run_dart_code_linter(self, dart_path: str) -> List[Violation]:
        """Execute dart_code_linter and parse results.

        Args:
            dart_path: Path to dart executable

        Returns:
            List of violations
        """
        # Get the path to analyze from config, default to 'lib'
        analyze_path = self.config.get('analyze_path', 'lib')

        print(f"Running dart_code_linter analysis on '{analyze_path}'...")

        # Use project_root if found, otherwise fall back to base_path
        working_dir = self.project_root if self.project_root else self.base_path

        # Create temporary report path - use output folder if specified, otherwise use project root
        if self.output_folder:
            report_dir = self.output_folder / 'code_analysis'
        else:
            report_dir = working_dir / 'code_analysis'
        report_dir.mkdir(exist_ok=True)
        report_json = report_dir / 'report.json'

        # Build command
        # Note: dart_code_linter adds .json extension automatically, so we pass the path without extension
        cmd = [
            dart_path, 'run', 'dart_code_linter:metrics', 'analyze',
            '--fatal-warnings', '--fatal-style',
            '--reporter=json',
            f'--json-path={report_dir / "report"}',
            analyze_path
        ]

        use_shell = platform.system() == 'Windows'

        # Execute dart_code_linter from project root
        try:
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace',  # Replace invalid characters instead of crashing
                check=False,
                shell=use_shell
            )

            # Check if report.json was created
            if not report_json.exists():
                print("Warning: dart_code_linter did not generate report.json")
                print(f"Command executed: {' '.join(cmd)}")
                print(f"Return code: {result.returncode}")
                if result.stdout:
                    print(f"Stdout: {result.stdout}")
                if result.stderr:
                    print(f"Stderr: {result.stderr}")
                return []

            # Report file exists - print location
            print(f"Metrics report saved to: {report_json}")

            # Parse JSON output
            violations = self._parse_metrics_json(report_json)
            print(f"DEBUG: Parsed {len(violations)} violations from JSON")

            # Apply log level filter to violations
            violations = self._filter_violations_by_log_level(violations)
            print(f"DEBUG: After log level filter: {len(violations)} violations")

            # Print summary
            if violations:
                print(f"\nDart Code Linter found {len(violations)} metric violation(s)")
            else:
                print("\nDart Code Linter: No metric violations found")

            # Write to CSV file if output folder is specified and violations found
            if self.output_folder and violations:
                output_file = self.output_folder / 'dart_code_linter.csv'
                self._write_csv_output(output_file, violations, report_json)

            # Cleanup entire report directory if keep_report is false
            if not self.config.get('keep_report', False):
                try:
                    shutil.rmtree(report_dir)
                    print(f"Cleaned up: {report_dir}")
                except Exception as e:
                    print(f"Warning: Could not delete report directory: {e}")

            return violations

        except FileNotFoundError:
            print(f"Error: Dart executable not found: {dart_path}")
            print("Please ensure Dart/Flutter SDK is installed and configured correctly")
            return []
        except Exception as e:
            import traceback
            print(f"Error running dart_code_linter: {e}")
            print("Full traceback:")
            traceback.print_exc()
            return []

    def _parse_metrics_json(self, report_path: Path) -> List[Violation]:
        """Parse dart_code_linter JSON report into violations.

        Args:
            report_path: Path to report.json file

        Returns:
            List of violations
        """
        violations = []

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Get configured metric thresholds
            metric_thresholds = self.config.get('metrics', {})
            print(f"DEBUG: Checking against {len(metric_thresholds)} configured metrics")

            records = data.get('records', [])
            print(f"DEBUG: Processing {len(records)} file(s) from report")

            # Process each record (file)
            for record in records:
                file_path = record.get('path', 'unknown')

                # Process file-level metrics
                for metric in record.get('fileMetrics', []):
                    violation = self._check_metric_threshold(
                        file_path, metric, metric_thresholds, context='file'
                    )
                    if violation:
                        violations.append(violation)

                # Process class metrics
                for class_name, class_data in record.get('classes', {}).items():
                    for metric in class_data.get('metrics', []):
                        violation = self._check_metric_threshold(
                            file_path, metric, metric_thresholds,
                            context=f'class {class_name}'
                        )
                        if violation:
                            violations.append(violation)

                # Process function metrics
                for func_name, func_data in record.get('functions', {}).items():
                    for metric in func_data.get('metrics', []):
                        violation = self._check_metric_threshold(
                            file_path, metric, metric_thresholds,
                            context=f'function {func_name}'
                        )
                        if violation:
                            violations.append(violation)

        except FileNotFoundError:
            print(f"Error: Report file not found: {report_path}")
        except json.JSONDecodeError as e:
            print(f"Error parsing dart_code_linter JSON output: {e}")
            # Show first 200 chars of file for debugging
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    content = f.read(200)
                    print(f"File content (first 200 chars): {content}...")
            except:
                pass
        except Exception as e:
            import traceback
            print(f"Error processing dart_code_linter results: {e}")
            print("Full traceback:")
            traceback.print_exc()

        return violations

    def _check_metric_threshold(
        self,
        file_path: str,
        metric: Dict[str, Any],
        thresholds: Dict[str, Dict[str, int]],
        context: str = ''
    ) -> Optional[Violation]:
        """Check if a metric exceeds configured thresholds.

        Args:
            file_path: Path to the file
            metric: Metric data from JSON
            thresholds: Configured thresholds from rules.json
            context: Additional context (e.g., 'class Foo', 'function bar')

        Returns:
            Violation if threshold exceeded, None otherwise
        """
        metric_id = metric.get('metricsId', 'unknown')
        value = metric.get('value', 0)

        # Check if this metric has configured thresholds
        if metric_id not in thresholds:
            return None

        threshold_config = thresholds[metric_id]
        # Check for file-specific exceptions
        effective_thresholds = self._get_threshold_for_file(Path(file_path), threshold_config, metric_id)
        error_threshold = effective_thresholds.get('error')
        warning_threshold = effective_thresholds.get('warning')

        # Skip metric if both thresholds are 0 (disabled)
        if error_threshold == 0 and warning_threshold == 0:
            return None

        severity = None
        threshold_value = None

        # Special handling for inverse metrics (lower is worse)
        is_inverse_metric = metric_id in ['maintainability-index', 'weight-of-class']

        if is_inverse_metric:
            # For inverse metrics (lower is worse), error threshold should be LOWER than warning threshold
            # Example: error: 20, warning: 40 means values below 20 are errors, below 40 are warnings
            if (error_threshold is not None and warning_threshold is not None and
                error_threshold >= warning_threshold):
                print(f"Warning: Metric '{metric_id}' has backwards thresholds! " +
                      f"For inverse metrics, error ({error_threshold}) should be < warning ({warning_threshold})")

            # Lower values are worse for inverse metrics
            if error_threshold is not None and value <= error_threshold:
                severity = Severity.ERROR
                threshold_value = error_threshold
            elif warning_threshold is not None and value <= warning_threshold:
                severity = Severity.WARNING
                threshold_value = warning_threshold
        else:
            # Higher values are worse for most metrics
            if error_threshold is not None and value >= error_threshold:
                severity = Severity.ERROR
                threshold_value = error_threshold
            elif warning_threshold is not None and value >= warning_threshold:
                severity = Severity.WARNING
                threshold_value = warning_threshold

        # No threshold exceeded
        if severity is None:
            return None

        # Create relative path
        try:
            rel_path = self._get_relative_path(Path(file_path))
        except:
            rel_path = file_path

        # Build message
        context_str = f" in {context}" if context else ""
        operator = "<=" if is_inverse_metric else ">="
        message = f"{metric_id} = {value} {operator} {threshold_value} (threshold){context_str}"

        return Violation(
            file_path=rel_path,
            rule_name='dart_code_linter',
            severity=severity,
            message=message
        )

    def _filter_violations_by_log_level(self, violations: List[Violation]) -> List[Violation]:
        """Filter violations based on log level.

        Args:
            violations: List of all violations

        Returns:
            Filtered list of violations based on log level
        """
        if self.log_level == LogLevel.ALL:
            return violations

        filtered = []
        for violation in violations:
            if self.log_level == LogLevel.ERROR and violation.severity != Severity.ERROR:
                continue
            elif self.log_level == LogLevel.WARNING and violation.severity not in (Severity.ERROR, Severity.WARNING):
                continue
            filtered.append(violation)

        return filtered

    def _write_csv_output(self, output_file: Path, violations: List[Violation], report_json: Path):
        """Write dart_code_linter results to CSV file with structured columns.

        Args:
            output_file: Path to CSV output file
            violations: List of violations (used for filtering)
            report_json: Path to the JSON report file for extracting structured data
        """
        try:
            # Load JSON report
            with open(report_json, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Get configured metric thresholds
            metric_thresholds = self.config.get('metrics', {})

            # Build a set of violation file+metric combinations for filtering
            violation_keys = set()
            for v in violations:
                # Extract metric name from message (format: "metric-name = value ...")
                if ' = ' in v.message:
                    metric_name = v.message.split(' = ')[0]
                    violation_keys.add((v.file_path, metric_name))

            # Prepare CSV data
            csv_rows = []

            records = data.get('records', [])
            for record in records:
                file_path = record.get('path', 'unknown')

                # Get relative path
                try:
                    rel_path = self._get_relative_path(Path(file_path))
                except:
                    rel_path = file_path

                # Process file-level metrics
                for metric in record.get('fileMetrics', []):
                    row = self._build_csv_row(rel_path, metric, metric_thresholds, context='file')
                    if row and (row['file_path'], row['metric']) in violation_keys:
                        csv_rows.append(row)

                # Process class metrics
                for class_name, class_data in record.get('classes', {}).items():
                    for metric in class_data.get('metrics', []):
                        row = self._build_csv_row(rel_path, metric, metric_thresholds,
                                                  context=f'class {class_name}')
                        if row and (row['file_path'], row['metric']) in violation_keys:
                            csv_rows.append(row)

                # Process function metrics
                for func_name, func_data in record.get('functions', {}).items():
                    for metric in func_data.get('metrics', []):
                        row = self._build_csv_row(rel_path, metric, metric_thresholds,
                                                  context=f'function {func_name}')
                        if row and (row['file_path'], row['metric']) in violation_keys:
                            csv_rows.append(row)

            # Apply max_errors limit to csv_rows
            if self.max_errors and len(csv_rows) > self.max_errors:
                # Sort by severity (ERROR first), then by value (higher = worse)
                def row_sort_key(row):
                    severity_order = {'ERROR': 0, 'WARNING': 1, 'INFO': 2}
                    return (severity_order.get(row['severity'], 3), -row['value'])

                csv_rows.sort(key=row_sort_key)
                csv_rows = csv_rows[:self.max_errors]

            # Write CSV
            if csv_rows:
                with open(output_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)

                    # Write header
                    writer.writerow(['file_path', 'metric', 'value', 'threshold', 'severity', 'context'])

                    # Write data rows
                    for row in csv_rows:
                        writer.writerow([
                            row['file_path'],
                            row['metric'],
                            row['value'],
                            row['threshold'],
                            row['severity'],
                            row['context']
                        ])

                print(f"Dart Code Linter report saved to: {output_file}")

        except Exception as e:
            import traceback
            print(f"Error writing dart_code_linter CSV file: {e}")
            print("Full traceback:")
            traceback.print_exc()

    def _build_csv_row(
        self,
        file_path: str,
        metric: Dict[str, Any],
        thresholds: Dict[str, Dict[str, int]],
        context: str = ''
    ) -> Optional[Dict[str, Any]]:
        """Build a CSV row dict if the metric exceeds configured thresholds.

        Args:
            file_path: Path to the file
            metric: Metric data from JSON
            thresholds: Configured thresholds from rules.json
            context: Additional context (e.g., 'class Foo', 'function bar', 'file')

        Returns:
            Dict with row data if threshold exceeded, None otherwise
        """
        metric_id = metric.get('metricsId', 'unknown')
        value = metric.get('value', 0)

        # Check if this metric has configured thresholds
        if metric_id not in thresholds:
            return None

        threshold_config = thresholds[metric_id]
        # Check for file-specific exceptions
        effective_thresholds = self._get_threshold_for_file(Path(file_path), threshold_config, metric_id)
        error_threshold = effective_thresholds.get('error')
        warning_threshold = effective_thresholds.get('warning')

        # Skip metric if both thresholds are 0 (disabled)
        if error_threshold == 0 and warning_threshold == 0:
            return None

        severity = None
        threshold_value = None

        # Special handling for inverse metrics (lower is worse)
        is_inverse_metric = metric_id in ['maintainability-index', 'weight-of-class']

        if is_inverse_metric:
            # Lower values are worse for inverse metrics
            if error_threshold is not None and value <= error_threshold:
                severity = 'ERROR'
                threshold_value = error_threshold
            elif warning_threshold is not None and value <= warning_threshold:
                severity = 'WARNING'
                threshold_value = warning_threshold
        else:
            # Higher values are worse for most metrics
            if error_threshold is not None and value >= error_threshold:
                severity = 'ERROR'
                threshold_value = error_threshold
            elif warning_threshold is not None and value >= warning_threshold:
                severity = 'WARNING'
                threshold_value = warning_threshold

        # No threshold exceeded
        if severity is None:
            return None

        return {
            'file_path': file_path,
            'metric': metric_id,
            'value': value,
            'threshold': threshold_value,
            'severity': severity,
            'context': context
        }
