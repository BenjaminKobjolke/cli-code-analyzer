"""Project-wide PHPMD analysis for PHP maintainability rules."""

import subprocess
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from file_discovery import DEFAULT_EXCLUDE_PATTERNS, FileDiscovery
from models import RuleResult, Severity, Violation
from path_utils import resolve_exclude_patterns
from rules.base import ProjectWideRule
from rules.filter_scope import ToolOutputError
from rules.php_tool_paths import get_bundled_php_tool_path

# Keep PHPMD exclusions aligned with discovery. PDepend matches raw OS paths, so each folder needs
# both separator forms.
_DEFAULT_EXCLUDES = tuple(
    f"*{sep}{pattern.removesuffix('/**')}{sep}*"
    for pattern in DEFAULT_EXCLUDE_PATTERNS['php']
    for sep in ('/', '\\')
)
_SUPPORTED_RULES = {
    'CyclomaticComplexity',
    'NPathComplexity',
    'ExcessiveMethodLength',
    'ExcessiveParameterList',
    'LongMethod',
    'LongParameterList',
    'CouplingBetweenObjects',
    'EmptyCatchBlock',
}
_RECOMMENDATIONS = {
    'CyclomaticComplexity': 'Simplify branching or extract focused decision logic.',
    'NPathComplexity': 'Reduce independent branch combinations or split the method.',
    'ExcessiveMethodLength': 'Split the method into focused steps with clear responsibilities.',
    'LongMethod': 'Split the method into focused steps with clear responsibilities.',
    'ExcessiveParameterList': 'Group related inputs behind a focused collaborator or value object.',
    'LongParameterList': 'Group related inputs behind a focused collaborator or value object.',
    'CouplingBetweenObjects': 'Reduce direct dependencies or split the class responsibilities.',
    'EmptyCatchBlock': 'Handle the exception or document why ignoring it is safe.',
}


class PHPMDAnalyzeRule(ProjectWideRule):
    """Run PHPMD and translate its XML findings into analyzer violations."""

    rule_name = 'phpmd_analyze'

    def _run(self, _file_path: Path) -> RuleResult:
        self.logger.info('\nRunning PHPMD check...')
        phpmd_path = get_bundled_php_tool_path('phpmd')
        if not phpmd_path:
            phpmd_path = self._get_tool_path('phpmd')
        if not phpmd_path:
            return self._failed('PHPMD executable not found')
        if not self.base_path:
            return self._failed('PHPMD cannot run without a project path')

        try:
            exclude_patterns = list(_DEFAULT_EXCLUDES)
            exclude_patterns.extend(resolve_exclude_patterns(
                self.config.get('exclude_patterns'), ('php',)
            ))
            exclude_patterns = list(dict.fromkeys(exclude_patterns))
            command = [phpmd_path, 'analyze']
            if self.filter_files is None:
                php_files = FileDiscovery(
                    'php', str(self.base_path), self.config.get('exclude_patterns')
                ).discover()
                commands = self._scoped_commands(
                    command, ('.php',), explicit_files=php_files
                )
            else:
                commands = self._scoped_commands(
                    command, ('.php',), [str(self.base_path)]
                )
            if commands is None:
                self.logger.info('Skipping PHPMD: no PHP files in the selected scope')
                return self._ok([])

            violations = []
            for command in commands:
                command.extend([
                    '--format', 'xml',
                    '--ruleset', 'codesize', '--ruleset', 'design',
                    '--suffixes', 'php',
                    '--exclude', ','.join(exclude_patterns),
                    '--ignore-violations-on-exit', '--no-progress',
                ])
                # PDepend's worker protocol shares stdout with its framed results. Keep
                # PHPMD in-process so worker diagnostics cannot corrupt the XML run output.
                command.append('--threads=1')
                try:
                    result = self._run_subprocess(command, self.base_path)
                except subprocess.TimeoutExpired as error:
                    return self._failed(
                        f'PHPMD timed out after {error.timeout} seconds'
                    )
                if result.returncode != 0:
                    raise ToolOutputError(
                        f"PHPMD failed (exit {result.returncode}): "
                        f"{(result.stderr or '').strip()[:300]}"
                    )
                if not result.stdout or not result.stdout.strip():
                    raise ToolOutputError('PHPMD returned empty XML output')
                violations.extend(self._parse_report(result.stdout))
        except FileNotFoundError:
            return self._failed(f'PHPMD executable not found: {phpmd_path}')
        except Exception as error:
            self.logger.error(f'Error running PHPMD check: {error}')
            return self._failed(f'error running PHPMD check: {error}')

        violations = self._filter_violations_by_log_level(violations)
        if self.max_errors and len(violations) > self.max_errors:
            violations = violations[:self.max_errors]
        self.logger.info(f'PHPMD found {len(violations)} issue(s)')
        return self._ok(violations)

    def _parse_report(self, output: str) -> list[Violation]:
        """Parse PHPMD XML and retain supported function-level rules."""
        xml_start = output.find('<?xml')
        if xml_start < 0:
            xml_start = output.find('<pmd')
        if xml_start > 0:
            # PHP can emit runtime deprecations on stdout before PHPMD's XML.
            preamble = output[:xml_start].splitlines()
            if any(
                line.strip()
                and not line.strip().lstrip('\ufeff').startswith(
                    ('Deprecated:', 'PHP Deprecated:')
                )
                for line in preamble
            ):
                raise ValueError('PHPMD returned unexpected text before its XML report')
            output = output[xml_start:]

        root = ElementTree.fromstring(output)
        if root.tag != 'pmd':
            raise ValueError('PHPMD returned an unexpected XML root element')

        violations = []
        for file_element in root.findall('file'):
            file_path = file_element.get('name')
            if not file_path:
                raise ValueError('PHPMD report contains a file without a name')
            for item in file_element.findall('violation'):
                rule_name = item.get('rule')
                if not rule_name:
                    raise ValueError('PHPMD report contains a violation without a rule')
                if rule_name not in _SUPPORTED_RULES:
                    continue

                line_text = item.get('beginline')
                if line_text is None:
                    raise ValueError(f'PHPMD {rule_name} finding has no source line')
                line = int(line_text)
                function_name = item.get('method') or item.get('function')
                class_name = item.get('class')
                owner = f'{class_name}::{function_name}' if class_name and function_name else (
                    function_name or class_name
                )
                message = rule_name
                if owner:
                    message += f' in {owner}'
                description = (item.text or '').strip()
                if description:
                    message += f': {description}'

                source_path = Path(file_path)
                if not source_path.is_absolute() and self.base_path:
                    source_path = self.base_path / source_path
                violations.append(Violation(
                    file_path=self._get_relative_path(source_path).replace('\\', '/'),
                    rule_name=self.rule_name,
                    severity=Severity.WARNING,
                    message=message,
                    line=line,
                    function_name=function_name,
                    confidence='high',
                    evidence=description or rule_name,
                    recommendation=_RECOMMENDATIONS[rule_name],
                ))
        return violations
