"""
Semgrep pattern-scanning rule (project-wide, multi-language)
"""

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import yaml

from models import RuleResult, RuleStatus, Violation
from rules.base import ProjectWideRule
from rules.filter_scope import ToolOutputError

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

        try:
            with self._bundled_config_context() as config_ref:
                cmd = [semgrep_path, 'scan', '--json', '--metrics=off', '--quiet',
                       '--disable-version-check', '--config', config_ref]
                for pattern in self.config.get('exclude_patterns', []):
                    cmd.extend(['--exclude', pattern])

                commands = self._scoped_commands(cmd, SEMGREP_EXTENSIONS, [str(self.base_path)])
                if commands is None:
                    return self._ok([])
                data = {'results': [], 'errors': []}
                for document in self._run_json('Semgrep', commands, self.base_path, {0, 1}):
                    if not isinstance(document, dict):
                        raise ToolOutputError('Semgrep returned unexpected JSON structure')
                    if not isinstance(document.get('results'), list) or not isinstance(document.get('errors'), list):
                        raise ToolOutputError('Semgrep returned unexpected JSON structure')
                    data['results'].extend(document['results'])
                    data['errors'].extend(document['errors'])
        except FileNotFoundError:
            return self._failed(f"Semgrep executable not found: {semgrep_path}")
        except ToolOutputError as e:
            self.logger.error(str(e))
            return self._failed(str(e))

        data['results'] = [result for result in data['results'] if self._php_rule_enabled(result)]
        self._apply_php_rule_severity(data['results'])
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

        if data['errors']:
            error_messages = [
                str(error.get('message', error)) if isinstance(error, dict) else str(error)
                for error in data['errors']
            ]
            return RuleResult(
                rule_name=self._result_name(),
                status=RuleStatus.FAILED,
                violations=violations,
                message='Semgrep reported errors: ' + '; '.join(error_messages),
            )

        return self._ok(violations)

    @contextmanager
    def _bundled_config_context(self) -> Iterator[str]:
        """Create a temporary bundled config when PHP rule patterns are customized."""
        if self.config.get('config'):
            yield self._config_ref()
            return

        receiver_patterns = self.config.get('repository_receiver_patterns')
        method_patterns = self.config.get('repository_method_patterns')
        if not receiver_patterns and not method_patterns:
            yield str(BUNDLED_RULES_DIR)
            return

        with tempfile.TemporaryDirectory(prefix='cli-analyzer-semgrep-') as directory:
            target_dir = Path(directory)
            shutil.copytree(BUNDLED_RULES_DIR, target_dir, dirs_exist_ok=True)
            php_config = target_dir / 'php_function_patterns.yaml'
            document = yaml.safe_load(php_config.read_text(encoding='utf-8'))
            for rule in document.get('rules', []):
                for pattern_group in rule.get('patterns', []):
                    matcher = pattern_group.get('metavariable-regex', {})
                    metavariable = matcher.get('metavariable')
                    configured_patterns = (
                        receiver_patterns if metavariable == '$RECEIVER'
                        else method_patterns if metavariable == '$METHOD'
                        else None
                    )
                    if configured_patterns:
                        matcher['regex'] = '(?i)(?:' + '|'.join(configured_patterns) + ')'
            php_config.write_text(yaml.safe_dump(document, sort_keys=False), encoding='utf-8')
            yield str(target_dir)

    def _php_rule_enabled(self, result: dict) -> bool:
        """Honor per-rule PHP switches while leaving other bundled rules untouched."""
        check_id = str(result.get('check_id', ''))
        php_rule = check_id.rsplit('.', 1)[-1]
        if not php_rule.startswith('php-'):
            return True
        selected_languages = self.config.get('_selected_languages')
        if selected_languages is not None and 'php' not in selected_languages:
            return False
        if self._php_path_excluded(result.get('path', '')):
            return False
        enabled = self.config.get('php_rules', {}).get(php_rule, True)
        return enabled is not False

    def _php_path_excluded(self, file_path: str) -> bool:
        """Apply PHP-only exclusions without excluding other languages in mixed scans."""
        normalized_path = str(file_path).replace('\\', '/')
        path_parts = normalized_path.split('/')
        return any(
            self._match_file_path(normalized_path, pattern.replace('\\', '/'))
            or any(self._match_file_path(part, pattern.replace('\\', '/')) for part in path_parts)
            for pattern in self.config.get('php_exclude_patterns', [])
        )

    def _apply_php_rule_severity(self, results: list[dict]) -> None:
        """Apply configured severities to bundled PHP findings before parsing."""
        severities = self.config.get('php_rule_severity', {})
        for result in results:
            check_id = str(result.get('check_id', '')).rsplit('.', 1)[-1]
            severity = severities.get(check_id)
            extra = result.get('extra')
            if severity and isinstance(extra, dict):
                extra['severity'] = str(severity).upper()

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
            metadata = extra.get('metadata', {})
            metadata = metadata if isinstance(metadata, dict) else {}
            file_path = res.get('path', 'unknown')
            metavars = extra.get('metavars', {})
            function_name = self._metadata_function_name(metadata, extra, metavars)
            confidence = metadata.get('confidence')
            if not isinstance(confidence, str) or confidence not in {'high', 'medium', 'low'}:
                confidence = None
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
                column=start.get('col', 0),
                function_name=function_name,
                confidence=confidence,
                evidence=metadata.get('evidence'),
                recommendation=metadata.get('recommendation'),
            ))
        for err in data.get('errors', []):
            message = err.get('message', err) if isinstance(err, dict) else err
            self.logger.warning(f"Semgrep error: {str(message)[:200]}")
        return violations

    @staticmethod
    def _metadata_function_name(metadata: dict, extra: dict, metavars: object) -> str | None:
        """Read function context when Semgrep metadata or metavariables provide it."""
        name = metadata.get('function_name') or extra.get('function_name')
        if isinstance(name, str) and name.strip():
            return name.strip()
        if not isinstance(metavars, dict):
            return None
        function = metavars.get('$FUNCTION') or metavars.get('FUNCTION')
        if isinstance(function, dict):
            function = function.get('abstract_content')
        return function.strip() if isinstance(function, str) and function.strip() else None
