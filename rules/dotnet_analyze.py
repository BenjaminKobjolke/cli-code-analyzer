"""Dotnet analyze rule for C# code analysis"""

import csv
import re
from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings


class DotnetAnalyzeRule(BaseRule):
    """Rule to analyze C# code using dotnet build with Roslyn analyzers"""

    # Regex to parse MSBuild diagnostic output
    # Example: D:\path\file.cs(10,5): warning CS0168: The variable 'x' is declared but never used
    MSBUILD_PATTERN = re.compile(
        r'^(?P<file>.+?)\((?P<line>\d+),(?P<col>\d+)\):\s*'
        r'(?P<severity>error|warning|info)\s+(?P<code>\w+):\s*(?P<message>.+)$',
        re.IGNORECASE
    )

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None,
                 log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None,
                 rules_file_path: str | None = None):
        super().__init__(config=config, base_path=base_path, log_level=log_level,
                        max_errors=max_errors, rules_file_path=rules_file_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._dotnet_executed = False

    def check(self, _file_path: Path) -> list[Violation]:
        """Run dotnet build on the entire project (only once)."""
        if self._dotnet_executed:
            return []

        self._dotnet_executed = True
        print("\nRunning dotnet build analysis...")

        # Get dotnet path using base utility
        dotnet_path = self._get_tool_path('dotnet', self.settings.get_dotnet_path,
                                           self.settings.prompt_and_save_dotnet_path)
        if not dotnet_path:
            return []

        violations = self._run_dotnet_build(dotnet_path)
        return violations

    def _run_dotnet_build(self, dotnet_path: str) -> list[Violation]:
        """Execute dotnet build and parse results."""
        # Build command - use build with no-restore for speed
        cmd = [dotnet_path, 'build', '--no-incremental']

        # Add configuration if specified
        config_type = self.config.get('configuration', 'Debug')
        cmd.extend(['-c', config_type])

        # Add verbosity for better output parsing
        cmd.extend(['-v', 'quiet'])

        # Add solution/project path if specified, otherwise use base_path
        target_path = self.config.get('solution_path') or self.config.get('project_path')
        if target_path:
            if not Path(target_path).is_absolute():
                target_path = str(self.base_path / target_path)
            cmd.append(target_path)

        try:
            result = self._run_subprocess(cmd, self.base_path)

            # Combine stdout and stderr - MSBuild outputs to both
            output = result.stdout + '\n' + result.stderr

            violations = self._parse_msbuild_output(output)

            # Filter by ignore_codes config
            ignore_codes = self.config.get('ignore_codes', [])
            if ignore_codes:
                violations = [v for v in violations if not any(code in v.message for code in ignore_codes)]

            violations = self._filter_violations_by_log_level(violations)

            if self.max_errors and len(violations) > self.max_errors:
                violations = violations[:self.max_errors]

            if violations:
                print(f"\nDotnet build found {len(violations)} issue(s)")
            else:
                print("\nDotnet build: No issues found")

            if self.output_folder and violations:
                output_file = self.output_folder / 'dotnet_analyze.csv'
                self._write_csv_output(output_file, violations)

            return violations

        except FileNotFoundError:
            print(f"Error: dotnet executable not found: {dotnet_path}")
            print("Please ensure .NET SDK is installed: https://dotnet.microsoft.com/download")
            return []
        except Exception as e:
            print(f"Error running dotnet build: {e}")
            return []

    def _map_severity(self, severity_str: str) -> Severity:
        """Map MSBuild severity to Severity enum."""
        severity_lower = severity_str.lower()
        if severity_lower == 'error':
            return Severity.ERROR
        elif severity_lower == 'warning':
            return Severity.WARNING
        else:
            return Severity.INFO

    def _parse_msbuild_output(self, output: str) -> list[Violation]:
        """Parse MSBuild diagnostic output into violations."""
        violations = []

        if not output or not output.strip():
            return violations

        for line in output.split('\n'):
            line = line.strip()
            match = self.MSBUILD_PATTERN.match(line)
            if match:
                file_path = match.group('file')
                line_num = match.group('line')
                col_num = match.group('col')
                severity_str = match.group('severity')
                code = match.group('code')
                message = match.group('message')

                # Get relative path
                try:
                    rel_path = self._get_relative_path(Path(file_path))
                except Exception:
                    rel_path = file_path

                # Build detailed message
                detailed_message = f"{message} ({code}) at line {line_num}, column {col_num}"

                violation = Violation(
                    file_path=rel_path,
                    rule_name='dotnet_analyze',
                    severity=self._map_severity(severity_str),
                    message=detailed_message
                )
                violations.append(violation)

        return violations

    def _write_csv_output(self, output_file: Path, violations: list[Violation]):
        """Write dotnet build results to CSV file."""
        if not violations:
            return

        try:
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['file', 'line', 'column', 'severity', 'code', 'message'])

                for v in violations:
                    # Parse message to extract components
                    msg = v.message
                    code_match = re.search(r'\((\w+)\)', msg)
                    code = code_match.group(1) if code_match else ''

                    line_match = re.search(r'at line (\d+)', msg)
                    line = line_match.group(1) if line_match else ''

                    col_match = re.search(r'column (\d+)', msg)
                    col = col_match.group(1) if col_match else ''

                    # Remove parsed parts from message for cleaner output
                    clean_msg = re.sub(r'\s*\(\w+\)\s*at line \d+, column \d+', '', msg).strip()

                    writer.writerow([v.file_path, line, col, v.severity.value, code, clean_msg])

            print(f"Dotnet analyze report saved to: {output_file}")

        except Exception as e:
            print(f"Error writing dotnet analyze CSV file: {e}")
