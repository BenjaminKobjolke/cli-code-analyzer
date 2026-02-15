"""
ESLint analyze rule for JavaScript/TypeScript code analysis
"""

import csv
import json
from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings


class ESLintAnalyzeRule(BaseRule):
    """Rule to analyze JavaScript/TypeScript code using ESLint linter"""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        """Initialize ESLint analyze rule.

        Args:
            config: Rule configuration from rules.json
            base_path: Base path for analysis
            output_folder: Optional folder for file output (None = console output)
            log_level: Log level for filtering violations
            max_errors: Optional limit on number of violations to include in CSV
            rules_file_path: Path to the rules.json file
        """
        super().__init__(config=config, base_path=base_path, log_level=log_level, max_errors=max_errors, rules_file_path=rules_file_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._eslint_executed = False  # Track if eslint has been executed
        self._svelte_files_cache = None  # Cache for _has_svelte_files() result

    def check(self, _file_path: Path) -> list[Violation]:
        """Run eslint check on the entire project (only once).

        Note: eslint analyzes entire projects, not individual files.
        This method will execute eslint once on the first file and return empty for subsequent files.

        Args:
            file_path: Path to a file (used to determine base directory)

        Returns:
            List of violations found (only on first execution)
        """
        # Only execute eslint once per analysis run
        if self._eslint_executed:
            return []

        self._eslint_executed = True

        print("\nRunning ESLint check...")

        # Get eslint path using base utility
        eslint_path = self._get_tool_path('eslint', self.settings.get_eslint_path, self.settings.prompt_and_save_eslint_path)
        if not eslint_path:
            return []

        # Run eslint check
        violations = self._run_eslint_check(eslint_path)

        return violations

    def _run_eslint_check(self, eslint_path: str) -> list[Violation]:
        """Execute eslint check and parse results.

        Args:
            eslint_path: Path to eslint executable

        Returns:
            List of violations
        """
        # Build command with JSON format
        cmd = [eslint_path, '--format', 'json']

        # Handle config mode
        config_mode = self.config.get('config_mode', 'auto')

        if config_mode == 'builtin':
            # Use builtin rules, ignore project config
            cmd.append('--no-eslintrc')
            # Add env settings
            env_config = self.config.get('env', {})
            for env_name, enabled in env_config.items():
                if enabled:
                    cmd.extend(['--env', env_name])
            # Add rules from config
            rules_config = self.config.get('rules', {})
            for rule_name, rule_value in rules_config.items():
                cmd.extend(['--rule', f'{rule_name}: {rule_value}'])
        elif config_mode == 'project':
            # Require project config - check if it exists
            if not self._has_project_config():
                print("Error: config_mode is 'project' but no ESLint config found")
                print("Create eslint.config.js or .eslintrc.* in your project")
                return []
        # config_mode == 'auto': ESLint will automatically detect project config or use defaults

        # Add exclude patterns as ignore patterns
        if self.config.get('exclude_patterns'):
            for pattern in self.config['exclude_patterns']:
                cmd.extend(['--ignore-pattern', pattern])

        # Add extensions to analyze
        # If explicitly configured, use that; otherwise auto-detect
        if 'extensions' in self.config:
            extensions = self.config['extensions']
        else:
            extensions = ['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx']
            # Auto-include .svelte if eslint-plugin-svelte is available
            if self._has_svelte_eslint_plugin():
                extensions.append('.svelte')
            elif self._has_svelte_files():
                print("Warning: .svelte files found but eslint-plugin-svelte is not installed — skipping ESLint for .svelte files")
                print("  Install it with: npm install --save-dev eslint-plugin-svelte svelte-eslint-parser")
                print("  Then configure your eslint.config.js to use the Svelte parser (see CLI Code Analyzer README)")
        cmd.extend(['--ext', ','.join(extensions)])

        # Add base path to analyze
        cmd.append(str(self.base_path))

        # Execute eslint using base utility
        try:
            result = self._run_subprocess(cmd, self.base_path)

            # ESLint outputs JSON to stdout
            output = result.stdout

            # Parse JSON output
            violations = self._parse_eslint_json(output)

            # Apply log level filter to violations
            violations = self._filter_violations_by_log_level(violations)

            # Apply max_errors limit to returned violations
            if self.max_errors and len(violations) > self.max_errors:
                violations = violations[:self.max_errors]

            # Print summary
            if violations:
                print(f"ESLint found {len(violations)} issue(s)")
            else:
                print("ESLint: No issues found")

            # Write to CSV file if output folder is specified and violations found
            if self.output_folder and violations:
                output_file = self.output_folder / 'eslint_analyze.csv'
                self._write_csv_output(output_file, output)

            return violations

        except FileNotFoundError:
            print(f"Error: ESLint executable not found: {eslint_path}")
            print("Please ensure ESLint is installed: npm install -g eslint")
            return []
        except Exception as e:
            print(f"Error running eslint check: {e}")
            return []

    def _has_project_config(self) -> bool:
        """Check if project has ESLint configuration.

        Returns:
            True if project config exists
        """
        config_files = [
            'eslint.config.js',
            'eslint.config.mjs',
            'eslint.config.cjs',
            '.eslintrc.js',
            '.eslintrc.cjs',
            '.eslintrc.yaml',
            '.eslintrc.yml',
            '.eslintrc.json',
            '.eslintrc',
        ]
        for config_file in config_files:
            if (self.base_path / config_file).exists():
                return True

        # Also check package.json for eslintConfig
        package_json = self.base_path / 'package.json'
        if package_json.exists():
            try:
                with open(package_json) as f:
                    pkg = json.load(f)
                    if 'eslintConfig' in pkg:
                        return True
            except (json.JSONDecodeError, OSError):
                pass

        return False

    def _has_svelte_eslint_plugin(self) -> bool:
        """Check if the project has eslint-plugin-svelte available.

        Checks for the package in node_modules.

        Returns:
            True if eslint-plugin-svelte is installed
        """
        return (self.base_path / 'node_modules' / 'eslint-plugin-svelte').is_dir()

    def _has_svelte_files(self) -> bool:
        """Check if the project contains any .svelte files (cached after first call).

        Skips node_modules to avoid expensive traversal.

        Returns:
            True if at least one .svelte file exists under base_path
        """
        if self._svelte_files_cache is None:
            self._svelte_files_cache = False
            for path in self.base_path.rglob('*.svelte'):
                if 'node_modules' not in path.parts:
                    self._svelte_files_cache = True
                    break
        return self._svelte_files_cache

    def _map_eslint_severity(self, severity: int) -> Severity:
        """Map ESLint severity to internal Severity.

        ESLint severity levels:
        - 2 = error
        - 1 = warning

        Args:
            severity: ESLint severity number

        Returns:
            Severity enum value
        """
        if severity == 2:
            return Severity.ERROR
        elif severity == 1:
            return Severity.WARNING
        else:
            return Severity.INFO

    def _parse_eslint_json(self, output: str) -> list[Violation]:
        """Parse eslint check JSON output into violations.

        ESLint JSON format:
        [
            {
                "filePath": "/path/to/file.js",
                "messages": [
                    {
                        "ruleId": "no-unused-vars",
                        "severity": 2,
                        "message": "'x' is defined but never used",
                        "line": 10,
                        "column": 5
                    }
                ],
                "errorCount": 1,
                "warningCount": 0
            }
        ]

        Args:
            output: JSON output from eslint check

        Returns:
            List of violations
        """
        violations = []

        if not output or not output.strip():
            return violations

        try:
            data = json.loads(output)

            # ESLint returns an array of file results
            for file_result in data:
                file_path = file_result.get('filePath', 'unknown')

                for message in file_result.get('messages', []):
                    rule_id = message.get('ruleId', 'unknown')
                    msg = message.get('message', '')
                    line_num = message.get('line', 0)
                    col_num = message.get('column', 0)
                    severity_num = message.get('severity', 1)

                    # Map severity
                    severity = self._map_eslint_severity(severity_num)

                    # Create relative path
                    try:
                        rel_path = self._get_relative_path(Path(file_path))
                    except Exception:
                        rel_path = file_path

                    # Build detailed message
                    detailed_message = f"{msg} ({rule_id}) at line {line_num}, column {col_num}"

                    violation = Violation(
                        file_path=rel_path,
                        rule_name='eslint_analyze',
                        severity=severity,
                        message=detailed_message,
                        line=line_num,
                        column=col_num
                    )
                    violations.append(violation)

        except json.JSONDecodeError as e:
            print(f"Error parsing eslint JSON output: {e}")
            print(f"Output was: {output[:200]}...")  # Print first 200 chars for debugging
        except Exception as e:
            print(f"Error processing eslint results: {e}")

        return violations

    def _write_csv_output(self, output_file: Path, json_content: str):
        """Write eslint results to CSV file, filtered by log level.

        Args:
            output_file: Path to CSV output file
            json_content: JSON content from eslint check
        """
        try:
            data = json.loads(json_content)

            if not data:
                return

            # Collect all messages with filtering
            filtered_messages = []
            for file_result in data:
                file_path = file_result.get('filePath', 'unknown')

                for message in file_result.get('messages', []):
                    severity_num = message.get('severity', 1)
                    severity = self._map_eslint_severity(severity_num)

                    # Apply log level filter
                    if (self.log_level == LogLevel.ERROR and severity != Severity.ERROR) or \
                       (self.log_level == LogLevel.WARNING and severity not in (Severity.ERROR, Severity.WARNING)):
                        continue

                    filtered_messages.append({
                        'file_path': file_path,
                        'message': message,
                        'severity': severity
                    })

            # Apply max_errors limit
            if self.max_errors and len(filtered_messages) > self.max_errors:
                # Sort by severity (ERROR first)
                def message_sort_key(m):
                    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
                    return severity_order.get(m['severity'], 3)

                filtered_messages.sort(key=message_sort_key)
                filtered_messages = filtered_messages[:self.max_errors]

            # Don't create CSV if no violations match the filter
            if not filtered_messages:
                return

            # Write CSV
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(['file', 'line', 'column', 'severity', 'rule', 'message'])

                # Write data rows
                for item in filtered_messages:
                    file_path = item['file_path']
                    message = item['message']
                    severity = item['severity']

                    # Get relative path
                    try:
                        rel_path = self._get_relative_path(Path(file_path))
                    except Exception:
                        rel_path = file_path

                    line_num = message.get('line', 0)
                    col_num = message.get('column', 0)
                    rule_id = message.get('ruleId', 'unknown')
                    msg = message.get('message', '')

                    writer.writerow([rel_path, line_num, col_num, severity.value, rule_id, msg])

            print(f"ESLint report saved to: {output_file}")

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON for CSV output: {e}")
        except Exception as e:
            print(f"Error writing eslint CSV file: {e}")
