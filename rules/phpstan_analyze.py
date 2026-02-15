"""PHPStan analyze rule for PHP code analysis"""

import csv
import json
from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings


class PHPStanAnalyzeRule(BaseRule):
    """Rule to analyze PHP code using PHPStan static analyzer"""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        super().__init__(config=config, base_path=base_path, log_level=log_level, max_errors=max_errors, rules_file_path=rules_file_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._phpstan_executed = False

    def _get_bundled_phpstan_path(self) -> str | None:
        """Get PHPStan path from bundled php/vendor/bin folder."""
        script_dir = Path(__file__).parent.parent
        paths = [
            script_dir / 'php' / 'vendor' / 'bin' / 'phpstan.bat',
            script_dir / 'php' / 'vendor' / 'bin' / 'phpstan',
        ]
        for p in paths:
            if p.exists():
                return str(p)
        return None

    def check(self, _file_path: Path) -> list[Violation]:
        """Run PHPStan check on the entire project (only once)."""
        if self._phpstan_executed:
            return []

        self._phpstan_executed = True
        print("\nRunning PHPStan check...")

        # First check bundled php/vendor/bin folder
        phpstan_path = self._get_bundled_phpstan_path()
        if not phpstan_path:
            phpstan_path = self._get_tool_path('phpstan', self.settings.get_phpstan_path, self.settings.prompt_and_save_phpstan_path)
        if not phpstan_path:
            return []

        violations = self._run_phpstan_check(phpstan_path)
        return violations

    def _run_phpstan_check(self, phpstan_path: str) -> list[Violation]:
        """Execute PHPStan check and parse results."""
        cmd = [phpstan_path, 'analyse', '--error-format=json', '--no-progress']

        # Add analysis level if configured (0-9)
        level = self.config.get('level', 5)
        cmd.extend(['--level', str(level)])

        # Add exclude patterns as --exclude options
        if self.config.get('exclude_patterns'):
            for pattern in self.config['exclude_patterns']:
                # PHPStan uses --exclude for directory exclusion
                if '**' in pattern:
                    pattern = pattern.replace('/**', '').replace('**/', '')
                cmd.extend(['--exclude', pattern])

        # Add path to analyze
        analyze_path = self.config.get('analyze_path', str(self.base_path))
        if not Path(analyze_path).is_absolute():
            analyze_path = str(self.base_path / analyze_path)
        cmd.append(analyze_path)

        try:
            result = self._run_subprocess(cmd, self.base_path)
            output = result.stdout

            violations = self._parse_phpstan_json(output)
            violations = self._filter_violations_by_log_level(violations)

            if self.max_errors and len(violations) > self.max_errors:
                violations = violations[:self.max_errors]

            if violations:
                print(f"PHPStan found {len(violations)} issue(s)")
            else:
                print("PHPStan: No issues found")

            if self.output_folder and violations:
                output_file = self.output_folder / 'phpstan_analyze.csv'
                if self._write_csv_output(output_file, output):
                    print(f"PHPStan report saved to: {output_file}")

            return violations

        except FileNotFoundError:
            print(f"Error: PHPStan executable not found: {phpstan_path}")
            print("Please ensure PHPStan is installed: composer require --dev phpstan/phpstan")
            return []
        except Exception as e:
            print(f"Error running PHPStan check: {e}")
            return []

    def _map_phpstan_severity(self, level: str | int) -> Severity:
        """Map PHPStan error level to severity."""
        # PHPStan doesn't have explicit severity levels in output,
        # but we can use the configured analysis level as a hint
        # For now, treat all PHPStan errors as errors since they're static analysis issues
        return Severity.ERROR

    def _parse_phpstan_json(self, output: str) -> list[Violation]:
        """Parse PHPStan JSON output into violations.

        PHPStan JSON format:
        {
            "totals": {"errors": 0, "file_errors": 5},
            "files": {
                "/path/to/file.php": {
                    "errors": 2,
                    "messages": [
                        {"message": "...", "line": 10, "ignorable": true}
                    ]
                }
            },
            "errors": []
        }
        """
        violations = []

        if not output or not output.strip():
            return violations

        try:
            data = json.loads(output)
            files = data.get('files', {})

            for file_path, file_data in files.items():
                messages = file_data.get('messages', [])

                for msg in messages:
                    message_text = msg.get('message', '')
                    line_num = msg.get('line', 0)
                    identifier = msg.get('identifier', '')

                    try:
                        rel_path = self._get_relative_path(Path(file_path))
                    except Exception:
                        rel_path = file_path

                    detailed_message = f"{message_text}"
                    if identifier:
                        detailed_message += f" [{identifier}]"
                    detailed_message += f" at line {line_num}"

                    violation = Violation(
                        file_path=rel_path,
                        rule_name='phpstan_analyze',
                        severity=Severity.ERROR,
                        message=detailed_message
                    )
                    violations.append(violation)

            # Also process general errors (not file-specific)
            for error in data.get('errors', []):
                violation = Violation(
                    file_path='<project>',
                    rule_name='phpstan_analyze',
                    severity=Severity.ERROR,
                    message=str(error)
                )
                violations.append(violation)

        except json.JSONDecodeError as e:
            print(f"Error parsing PHPStan JSON output: {e}")
            print(f"Output was: {output[:200]}...")
        except Exception as e:
            print(f"Error processing PHPStan results: {e}")

        return violations

    def _write_csv_output(self, output_file: Path, json_content: str) -> bool:
        """Write PHPStan results to CSV file.

        Returns:
            True if CSV was written successfully, False otherwise.
        """
        try:
            data = json.loads(json_content)
            files = data.get('files', {})

            if not files and not data.get('errors', []):
                return False

            all_violations = []

            for file_path, file_data in files.items():
                for msg in file_data.get('messages', []):
                    try:
                        rel_path = self._get_relative_path(Path(file_path))
                    except Exception:
                        rel_path = file_path

                    all_violations.append({
                        'file': rel_path,
                        'line': msg.get('line', 0),
                        'severity': 'error',
                        'identifier': msg.get('identifier', ''),
                        'message': msg.get('message', ''),
                        'ignorable': msg.get('ignorable', True)
                    })

            # Also process general errors (not file-specific)
            for error in data.get('errors', []):
                all_violations.append({
                    'file': '<project>',
                    'line': 0,
                    'severity': 'error',
                    'identifier': '',
                    'message': str(error),
                    'ignorable': False
                })

            # Apply max_errors limit
            if self.max_errors and len(all_violations) > self.max_errors:
                all_violations = all_violations[:self.max_errors]

            if not all_violations:
                return False

            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['file', 'line', 'severity', 'identifier', 'message', 'ignorable'])

                for v in all_violations:
                    writer.writerow([v['file'], v['line'], v['severity'], v['identifier'], v['message'], v['ignorable']])

            return True

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON for CSV output: {e}")
            return False
        except Exception as e:
            print(f"Error writing PHPStan CSV file: {e}")
            return False
