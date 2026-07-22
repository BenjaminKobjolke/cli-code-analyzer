"""PHPStan analyze rule for PHP code analysis"""

import csv
import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path

from models import RuleResult, Severity, Violation
from rules.base import ProjectWideRule


class PHPStanAnalyzeRule(ProjectWideRule):
    """Rule to analyze PHP code using PHPStan static analyzer"""

    rule_name = 'phpstan_analyze'

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

    def _run(self, _file_path: Path) -> RuleResult:
        self.logger.info("\nRunning PHPStan check...")

        # First check bundled php/vendor/bin folder
        phpstan_path = self._get_bundled_phpstan_path()
        if not phpstan_path:
            phpstan_path = self._get_tool_path('phpstan')
        if not phpstan_path:
            return self._failed("PHPStan executable not found")

        return self._run_phpstan_check(phpstan_path)

    def _run_phpstan_check(self, phpstan_path: str) -> RuleResult:
        """Execute PHPStan check and parse results."""
        cmd = [phpstan_path, 'analyse', '--error-format=json', '--no-progress']

        # Add analysis level if configured (0-9)
        level = self.config.get('level', 5)
        cmd.extend(['--level', str(level)])

        # PHPStan's default 128M memory limit crashes its parallel workers on
        # medium-sized projects; the limit propagates to workers via the CLI flag.
        memory_limit = self.config.get('memory_limit', '1G')
        cmd.extend(['--memory-limit', str(memory_limit)])

        # PHPStan's CLI has no --exclude option; excludes must go through a
        # config file. Write exclude_patterns to a temp neon as excludePaths.
        neon_path = None
        if self.config.get('exclude_patterns'):
            exclude_dirs = []
            for pattern in self.config['exclude_patterns']:
                if '**' in pattern:
                    pattern = pattern.replace('/**', '').replace('**/', '')
                exclude_dirs.append((self.base_path / pattern).as_posix())
            # "(?)" marks each path optional so a configured-but-absent dir
            # (e.g. node_modules in a pure PHP project) doesn't abort the run.
            neon = 'parameters:\n    excludePaths:\n'
            neon += ''.join(f'        - {d} (?)\n' for d in exclude_dirs)
            fd, neon_path = tempfile.mkstemp(suffix='.neon', text=True)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(neon)
            cmd.extend(['-c', neon_path])

        # Add paths to analyze: changed files when filtering, else the
        # configured analyze_path (a single path or a list of paths).
        analyze_path = self.config.get('analyze_path', str(self.base_path))
        paths = analyze_path if isinstance(analyze_path, list) else [analyze_path]
        paths = [p if Path(p).is_absolute() else str(self.base_path / p) for p in paths]
        scope = self._scope_args(('.php',), paths)
        if scope is None:
            return self._ok([])
        cmd += scope

        try:
            result = self._run_subprocess(cmd, self.base_path)
            output = result.stdout
        except FileNotFoundError:
            self.logger.error(f"Error: PHPStan executable not found: {phpstan_path}")
            self.logger.error("Please ensure PHPStan is installed: composer require --dev phpstan/phpstan")
            return self._failed(f"PHPStan executable not found: {phpstan_path}")
        except Exception as e:
            self.logger.error(f"Error running PHPStan check: {e}")
            return self._failed(f"error running PHPStan check: {e}")
        finally:
            if neon_path:
                with suppress(OSError):
                    os.unlink(neon_path)

        # Empty stdout with a nonzero exit means PHPStan died before analyzing
        # (bad CLI option, config error) — a real "errors found" run (exit 1)
        # always emits JSON on stdout. Never report this as clean.
        if result.returncode != 0 and not output.strip():
            stderr = (result.stderr or '').strip()
            self.logger.error(f"PHPStan failed without producing output: {stderr[:300]}")
            return self._failed(f"PHPStan failed without producing output: {stderr[:300]}")

        # Conservative guard: non-empty output that is not valid JSON means PHPStan
        # emitted a fatal/non-JSON message — treat as a failure, not "clean".
        if output and output.strip():
            try:
                json.loads(output)
            except json.JSONDecodeError as e:
                self.logger.error(f"Error parsing PHPStan JSON output: {e}")
                self.logger.error(f"Output was: {output[:200]}...")
                return self._failed(f"could not parse PHPStan JSON output: {e}")

        violations = self._parse_phpstan_json(output)
        violations = self._filter_violations_by_log_level(violations)

        if self.max_errors and len(violations) > self.max_errors:
            violations = violations[:self.max_errors]

        if violations:
            self.logger.info(f"PHPStan found {len(violations)} issue(s)")
        else:
            self.logger.info("PHPStan: No issues found")

        if self.output_folder and violations:
            output_file = self.output_folder / 'phpstan_analyze.csv'
            if self._write_csv_output(output_file, output):
                self.logger.info(f"PHPStan report saved to: {output_file}")

        return self._ok(violations)

    def _map_phpstan_severity(self, _level: str | int) -> Severity:
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
            self.logger.error(f"Error parsing PHPStan JSON output: {e}")
            self.logger.error(f"Output was: {output[:200]}...")
        except Exception as e:
            self.logger.error(f"Error processing PHPStan results: {e}")

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
            self.logger.error(f"Error parsing JSON for CSV output: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error writing PHPStan CSV file: {e}")
            return False
