"""
Semgrep pattern-scanning rule (project-wide, multi-language)
"""

import json
from pathlib import Path

from models import RuleResult, Violation
from rules.base import ProjectWideRule

SEMGREP_EXTENSIONS = ('.py', '.js', '.jsx', '.ts', '.tsx', '.php', '.cs', '.dart')
BUNDLED_RULES_DIR = Path(__file__).parent.parent / 'semgrep_rules'


class SemgrepAnalyzeRule(ProjectWideRule):
    """Rule to scan code patterns using semgrep"""

    rule_name = 'semgrep_analyze'

    def _run(self, _file_path: Path) -> RuleResult:
        self.logger.info("\nRunning semgrep scan...")

        semgrep_path = self._get_tool_path('semgrep')
        if not semgrep_path:
            return self._failed("Semgrep executable not found")

        cmd = [semgrep_path, 'scan', '--json', '--metrics=off', '--quiet',
               '--disable-version-check', '--config', self._config_ref()]
        for pattern in self.config.get('exclude_patterns', []):
            cmd.extend(['--exclude', pattern])

        scope = self._scope_args(SEMGREP_EXTENSIONS, [str(self.base_path)])
        if scope is None:
            return self._ok([])
        cmd += scope

        try:
            result = self._run_subprocess(cmd, self.base_path)
        except FileNotFoundError:
            return self._failed(f"Semgrep executable not found: {semgrep_path}")

        output = result.stdout
        # Nonzero exit with no output means semgrep died before scanning; never report clean.
        if result.returncode != 0 and not (output and output.strip()):
            stderr = (result.stderr or '').strip()
            self.logger.error(f"Semgrep failed without producing output: {stderr[:300]}")
            return self._failed(f"Semgrep failed without producing output: {stderr[:300]}")

        try:
            data = json.loads(output)
        except (json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Error parsing semgrep JSON output: {e}")
            return self._failed(f"could not parse semgrep JSON output: {e}")

        violations = self._parse_results(data)
        violations = self._filter_violations_by_log_level(violations)
        if self.max_errors and len(violations) > self.max_errors:
            violations = violations[:self.max_errors]

        if violations:
            self.logger.info(f"Semgrep found {len(violations)} issue(s)")
        else:
            self.logger.info("Semgrep: No issues found")

        if self.output_folder and violations:
            self._write_violations_csv(
                self.output_folder / 'semgrep_analyze.csv', violations,
                ['file', 'line', 'column', 'severity', 'message'],
                lambda v: [v.file_path, v.line, v.column, v.severity.value, v.message])

        return self._ok(violations)

    def _config_ref(self) -> str:
        """Resolve semgrep --config value: bundled rules dir, project-relative path,
        absolute path, or registry ref like 'p/default'."""
        ref = self.config.get('config')
        if not ref:
            return str(BUNDLED_RULES_DIR)
        path = Path(ref)
        if path.is_absolute():
            return ref
        project_path = self.base_path / path if self.base_path else None
        if project_path and project_path.exists():
            return str(project_path)
        return ref

    def _parse_results(self, data: dict) -> list[Violation]:
        """Parse semgrep JSON output ({"results": [...], "errors": [...]}) into violations."""
        violations = []
        for res in data.get('results', []):
            start = res.get('start', {})
            extra = res.get('extra', {})
            file_path = res.get('path', 'unknown')
            try:
                rel_path = self._get_relative_path(Path(file_path))
            except Exception:
                rel_path = file_path
            violations.append(Violation(
                file_path=rel_path,
                rule_name='semgrep_analyze',
                severity=self._map_severity(extra.get('severity', 'WARNING')),
                message=f"{extra.get('message', '').strip()} [{res.get('check_id', '')}]",
                line=start.get('line', 0),
                column=start.get('col', 0)
            ))
        for err in data.get('errors', []):
            message = err.get('message', err) if isinstance(err, dict) else err
            self.logger.warning(f"Semgrep error: {str(message)[:200]}")
        return violations
