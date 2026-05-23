"""
Pyscn analyze rule for Python code analysis.

Wraps the pyscn binary (https://github.com/ludo-technologies/pyscn) to provide
cyclomatic complexity, CFG-based dead code detection, and class coupling (CBO)
+ circular dependency analysis for Python.

Uses `pyscn analyze --json` and applies our own thresholds via
_get_threshold_for_file so per-file exceptions work the same way as
dart_code_linter.
"""

import json
from pathlib import Path
from typing import Any

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings


# Mapping pyscn dead-code severity strings to our Severity enum
_DEAD_CODE_SEVERITY_MAP = {
    'critical': Severity.ERROR,
    'warning': Severity.WARNING,
    'info': Severity.INFO,
}


class PyscnAnalyzeRule(BaseRule):
    """Project-wide rule that runs pyscn and emits Violations for
    complexity, dead code, coupling (CBO), and circular dependencies."""

    def __init__(self, config: dict, base_path: Path | None = None,
                 output_folder: Path | None = None,
                 log_level: LogLevel = LogLevel.ALL,
                 max_errors: int | None = None,
                 rules_file_path: str | None = None,
                 logger=None):
        super().__init__(config=config, base_path=base_path,
                         log_level=log_level, max_errors=max_errors,
                         rules_file_path=rules_file_path, logger=logger)
        self.output_folder = output_folder
        self.settings = Settings()
        self._pyscn_executed = False

    def check(self, _file_path: Path) -> list[Violation]:
        if self._pyscn_executed:
            return []
        self._pyscn_executed = True

        self.logger.info("\nRunning pyscn analyze...")

        pyscn_path = self._get_tool_path(
            'pyscn',
            self.settings.get_pyscn_path,
            self.settings.prompt_and_save_pyscn_path,
        )
        if not pyscn_path:
            return []

        select = self.config.get('select', ['complexity', 'deadcode', 'deps'])
        cmd = [pyscn_path, 'analyze', '--json', '--select', ','.join(select),
               str(self.base_path)]

        try:
            result = self._run_subprocess(cmd, cwd=self.base_path)
        except FileNotFoundError:
            self.logger.error(f"Error: pyscn executable not found: {pyscn_path}")
            self.logger.error("Install with: pipx install pyscn")
            return []
        except Exception as e:
            self.logger.error(f"Error running pyscn: {e}")
            return []

        if not result.stdout or not result.stdout.strip():
            if result.stderr:
                self.logger.warning(f"pyscn stderr: {result.stderr.strip()}")
            self.logger.info("pyscn: no output.")
            return []

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing pyscn JSON: {e}")
            self.logger.error(f"Output snippet: {result.stdout[:200]}")
            return []

        violations: list[Violation] = []
        if 'complexity' in select:
            violations.extend(self._parse_complexity(data))
        if 'deadcode' in select:
            violations.extend(self._parse_dead_code(data))
        if 'deps' in select:
            violations.extend(self._parse_coupling(data))
            violations.extend(self._parse_circular(data))

        violations = self._filter_violations_by_log_level(violations)

        if violations:
            self.logger.info(f"pyscn found {len(violations)} issue(s)")
        else:
            self.logger.info("pyscn: no issues found")

        if self.max_errors and len(violations) > self.max_errors:
            severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
            violations.sort(key=lambda v: severity_order.get(v.severity, 3))
            violations = violations[:self.max_errors]

        if self.output_folder and violations:
            output_file = self.output_folder / 'pyscn_analyze.csv'
            self._write_csv(output_file, violations)

        return violations

    def _check_metric_threshold(self, file_path: Path, metric_name: str,
                                metric_value: float,
                                threshold_config: dict) -> tuple[Severity | None, float | None]:
        """Return (severity, threshold) for a metric value, or (None, None) if below all thresholds."""
        thresholds = self._get_threshold_for_file(file_path, threshold_config, metric_name)
        error_t = thresholds.get('error')
        warning_t = thresholds.get('warning')

        if error_t is not None and metric_value >= error_t:
            return Severity.ERROR, error_t
        if warning_t is not None and metric_value >= warning_t:
            return Severity.WARNING, warning_t
        return None, None

    def _to_rel_path(self, raw_path: str) -> str:
        try:
            return self._get_relative_path(Path(raw_path))
        except Exception:
            return raw_path

    def _parse_complexity(self, data: dict) -> list[Violation]:
        violations = []
        complexity_cfg = self.config.get('complexity', {})
        if not complexity_cfg:
            return violations

        complexity_section = data.get('complexity') or data.get('Complexity') or {}
        functions = complexity_section.get('Functions') or complexity_section.get('functions') or []

        for fn in functions:
            metrics = fn.get('Metrics') or fn.get('metrics') or {}
            cc = metrics.get('Complexity') or metrics.get('complexity')
            if cc is None:
                continue
            file_path = fn.get('FilePath') or fn.get('file_path') or ''
            name = fn.get('Name') or fn.get('name') or '<unknown>'
            start_line = fn.get('StartLine') or fn.get('start_line') or 0

            severity, threshold = self._check_metric_threshold(
                Path(file_path) if file_path else Path('.'),
                'complexity', cc, complexity_cfg,
            )
            if severity is None:
                continue

            violations.append(Violation(
                file_path=self._to_rel_path(file_path),
                rule_name='pyscn_analyze',
                severity=severity,
                message=f"[complexity] Function '{name}' complexity {cc} exceeds threshold {int(threshold)}",
                line=start_line or None,
            ))
        return violations

    def _parse_dead_code(self, data: dict) -> list[Violation]:
        violations = []
        dead_cfg = self.config.get('dead_code', {})
        if not dead_cfg:
            return violations

        fallback_severity_str = dead_cfg.get('severity', 'warning')
        fallback_severity = self._map_severity(fallback_severity_str)

        section = data.get('dead_code') or data.get('DeadCode') or {}
        files = section.get('files') or section.get('Files') or []

        for file_entry in files:
            file_path = file_entry.get('file_path') or file_entry.get('FilePath') or ''
            funcs = file_entry.get('functions') or file_entry.get('Functions') or []
            for func in funcs:
                findings = func.get('findings') or func.get('Findings') or []
                for finding in findings:
                    location = finding.get('location') or finding.get('Location') or {}
                    fp = location.get('file_path') or location.get('FilePath') or file_path
                    line = location.get('start_line') or location.get('StartLine') or 0
                    reason = finding.get('reason') or finding.get('Reason') or 'unreachable'
                    desc = finding.get('description') or finding.get('Description') or ''
                    pyscn_sev = (finding.get('severity') or finding.get('Severity') or '').lower()

                    severity = _DEAD_CODE_SEVERITY_MAP.get(pyscn_sev, fallback_severity)

                    msg = f"[deadcode] Unreachable code ({reason})"
                    if desc:
                        msg += f": {desc}"

                    violations.append(Violation(
                        file_path=self._to_rel_path(fp),
                        rule_name='pyscn_analyze',
                        severity=severity,
                        message=msg,
                        line=line or None,
                    ))
        return violations

    def _parse_coupling(self, data: dict) -> list[Violation]:
        violations = []
        coupling_cfg = self.config.get('coupling', {})
        if not coupling_cfg:
            return violations

        section = data.get('cbo') or data.get('CBO') or data.get('coupling') or {}
        classes = section.get('Classes') or section.get('classes') or []

        for cls in classes:
            metrics = cls.get('Metrics') or cls.get('metrics') or {}
            cbo = metrics.get('CouplingCount') or metrics.get('coupling_count')
            if cbo is None:
                continue
            file_path = cls.get('FilePath') or cls.get('file_path') or ''
            name = cls.get('Name') or cls.get('name') or '<unknown>'
            start_line = cls.get('StartLine') or cls.get('start_line') or 0

            severity, threshold = self._check_metric_threshold(
                Path(file_path) if file_path else Path('.'),
                'coupling', cbo, coupling_cfg,
            )
            if severity is None:
                continue

            violations.append(Violation(
                file_path=self._to_rel_path(file_path),
                rule_name='pyscn_analyze',
                severity=severity,
                message=f"[coupling] Class '{name}' CBO {cbo} exceeds threshold {int(threshold)}",
                line=start_line or None,
            ))
        return violations

    def _parse_circular(self, data: dict) -> list[Violation]:
        violations = []
        coupling_cfg = self.config.get('coupling', {})
        if not coupling_cfg.get('report_circular_deps', True):
            return violations

        severity = self._map_severity(coupling_cfg.get('circular_severity', 'error'))

        system = data.get('system') or data.get('System') or {}
        dep_analysis = system.get('DependencyAnalysis') or system.get('dependency_analysis') or {}
        circular = dep_analysis.get('CircularDependencies') or dep_analysis.get('circular_dependencies') or {}

        if not circular.get('HasCircularDependencies') and not circular.get('has_circular_dependencies'):
            return violations

        cycles = circular.get('CircularDependencies') or circular.get('cycles') or []
        for cycle in cycles:
            if isinstance(cycle, dict):
                modules = cycle.get('Modules') or cycle.get('modules') or cycle.get('Path') or cycle.get('path') or []
                if isinstance(modules, list) and modules:
                    cycle_str = ' -> '.join(str(m) for m in modules)
                    first_module = str(modules[0])
                else:
                    cycle_str = str(cycle)
                    first_module = ''
            elif isinstance(cycle, list):
                cycle_str = ' -> '.join(str(m) for m in cycle)
                first_module = str(cycle[0]) if cycle else ''
            else:
                cycle_str = str(cycle)
                first_module = ''

            violations.append(Violation(
                file_path=first_module or 'project',
                rule_name='pyscn_analyze',
                severity=severity,
                message=f"[circular] Circular dependency: {cycle_str}",
            ))
        return violations

    def _write_csv(self, output_file: Path, violations: list[Violation]) -> None:
        def row_mapper(v: Violation) -> list[Any]:
            subcheck = ''
            msg = v.message
            if msg.startswith('[') and ']' in msg:
                end = msg.index(']')
                subcheck = msg[1:end]
                msg = msg[end + 1:].strip()
            return [v.file_path, v.line or '', v.severity.value, subcheck, msg]

        self._write_violations_csv(
            output_file, violations,
            headers=['file', 'line', 'severity', 'subcheck', 'message'],
            row_mapper=row_mapper,
        )
