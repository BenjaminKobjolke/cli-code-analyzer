"""PHP-CS-Fixer analyze rule for PHP code style checking"""

import csv
import json
from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings


class PHPCSFixerAnalyzeRule(BaseRule):
    """Rule to analyze PHP code style using PHP-CS-Fixer in dry-run mode"""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        super().__init__(config=config, base_path=base_path, log_level=log_level, max_errors=max_errors, rules_file_path=rules_file_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._fixer_executed = False

    def _get_bundled_fixer_path(self) -> str | None:
        """Get PHP-CS-Fixer path from bundled php/vendor/bin folder."""
        script_dir = Path(__file__).parent.parent
        paths = [
            script_dir / 'php' / 'vendor' / 'bin' / 'php-cs-fixer.bat',
            script_dir / 'php' / 'vendor' / 'bin' / 'php-cs-fixer',
        ]
        for p in paths:
            if p.exists():
                return str(p)
        return None

    def check(self, _file_path: Path) -> list[Violation]:
        """Run PHP-CS-Fixer check in dry-run mode on the entire project (only once)."""
        if self._fixer_executed:
            return []

        self._fixer_executed = True
        print("\nRunning PHP-CS-Fixer check...")

        # First check bundled php/vendor/bin folder
        fixer_path = self._get_bundled_fixer_path()
        if not fixer_path:
            fixer_path = self._get_tool_path('php-cs-fixer', self.settings.get_php_cs_fixer_path, self.settings.prompt_and_save_php_cs_fixer_path)
        if not fixer_path:
            return []

        violations = self._run_fixer_check(fixer_path)
        return violations

    def _run_fixer_check(self, fixer_path: str) -> list[Violation]:
        """Execute PHP-CS-Fixer in dry-run mode and parse results."""
        cmd = [fixer_path, 'fix', '--dry-run', '--format=json', '--verbose']

        # Add rules configuration if specified
        rules = self.config.get('rules', '@PSR12')
        if rules:
            cmd.extend(['--rules', rules])

        # Add path to analyze
        analyze_path = self.config.get('analyze_path', str(self.base_path))
        if not Path(analyze_path).is_absolute():
            analyze_path = str(self.base_path / analyze_path)
        cmd.append(analyze_path)

        try:
            result = self._run_subprocess(cmd, self.base_path)
            output = result.stdout

            violations = self._parse_fixer_json(output)
            violations = self._filter_violations_by_log_level(violations)

            if self.max_errors and len(violations) > self.max_errors:
                violations = violations[:self.max_errors]

            if violations:
                print(f"\nPHP-CS-Fixer found {len(violations)} issue(s)")
            else:
                print("\nPHP-CS-Fixer: No issues found")

            if self.output_folder and violations:
                output_file = self.output_folder / 'php_cs_fixer.csv'
                self._write_csv_output(output_file, output)

            return violations

        except FileNotFoundError:
            print(f"Error: PHP-CS-Fixer executable not found: {fixer_path}")
            print("Please ensure PHP-CS-Fixer is installed: composer require --dev friendsofphp/php-cs-fixer")
            return []
        except Exception as e:
            print(f"Error running PHP-CS-Fixer check: {e}")
            return []

    def _parse_fixer_json(self, output: str) -> list[Violation]:
        """Parse PHP-CS-Fixer JSON output into violations.

        PHP-CS-Fixer JSON format:
        {
            "files": [
                {
                    "name": "path/to/file.php",
                    "appliedFixers": ["braces", "indentation_type", ...]
                }
            ]
        }
        """
        violations = []

        if not output or not output.strip():
            return violations

        try:
            data = json.loads(output)
            files = data.get('files', [])

            for file_info in files:
                file_path = file_info.get('name', 'unknown')
                fixers = file_info.get('appliedFixers', [])

                try:
                    rel_path = self._get_relative_path(Path(file_path))
                except Exception:
                    rel_path = file_path

                # Create one violation per file listing all fixers that would be applied
                if fixers:
                    fixer_list = ', '.join(fixers)
                    message = f"Code style issues found. Would apply fixers: {fixer_list}"

                    violation = Violation(
                        file_path=rel_path,
                        rule_name='php_cs_fixer',
                        severity=Severity.WARNING,
                        message=message
                    )
                    violations.append(violation)

        except json.JSONDecodeError as e:
            print(f"Error parsing PHP-CS-Fixer JSON output: {e}")
            print(f"Output was: {output[:200]}...")
        except Exception as e:
            print(f"Error processing PHP-CS-Fixer results: {e}")

        return violations

    def _write_csv_output(self, output_file: Path, json_content: str):
        """Write PHP-CS-Fixer results to CSV file."""
        try:
            data = json.loads(json_content)
            files = data.get('files', [])

            if not files:
                return

            all_violations = []

            for file_info in files:
                file_path = file_info.get('name', 'unknown')
                fixers = file_info.get('appliedFixers', [])

                try:
                    rel_path = self._get_relative_path(Path(file_path))
                except Exception:
                    rel_path = file_path

                if fixers:
                    all_violations.append({
                        'file': rel_path,
                        'severity': 'warning',
                        'fixers': ', '.join(fixers),
                        'fixer_count': len(fixers)
                    })

            # Apply max_errors limit
            if self.max_errors and len(all_violations) > self.max_errors:
                all_violations = all_violations[:self.max_errors]

            if not all_violations:
                return

            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['file', 'severity', 'fixers', 'fixer_count'])

                for v in all_violations:
                    writer.writerow([v['file'], v['severity'], v['fixers'], v['fixer_count']])

            print(f"PHP-CS-Fixer report saved to: {output_file}")

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON for CSV output: {e}")
        except Exception as e:
            print(f"Error writing PHP-CS-Fixer CSV file: {e}")
