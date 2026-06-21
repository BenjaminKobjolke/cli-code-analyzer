"""Shared PMD CPD machinery for the duplicate- and similar-code rules.

Holds the constants, temp-file/command helpers and the ``PMDCpdRule`` base
class common to :class:`~rules.pmd_duplicates.PMDDuplicatesRule` and
:class:`~rules.pmd_similar_code.PMDSimilarCodeRule`.
"""

import contextlib
import tempfile
from dataclasses import dataclass
from pathlib import Path

from models import RuleResult
from rules.base import ProjectWideRule

# Default exclude patterns per language (glob patterns)
DEFAULT_EXCLUDE_PATTERNS = {
    'dart': ['*.g.dart', '*.freezed.dart'],
    'python': ['**/__pycache__/**', '*.pyc'],
    'java': ['**/target/**', '**/build/**'],
    'javascript': ['**/node_modules/**', '**/dist/**', '**/build/**'],
    'typescript': ['**/node_modules/**', '**/dist/**', '**/build/**'],
    'php': ['**/vendor/**', '**/node_modules/**', '**/.phpstan-cache/**'],
    'cs': ['**/bin/**', '**/obj/**', '**/.vs/**', '**/packages/**'],
}

# Language mapping from analyzer to PMD
LANGUAGE_TO_PMD = {
    'flutter': 'dart',
    'dart': 'dart',
    'python': 'python',
    'java': 'java',
    'javascript': 'ecmascript',
    'js': 'ecmascript',
    'typescript': 'typescript',
    'ts': 'typescript',
    'php': 'php',
    'csharp': 'cs',
    'svelte': 'ecmascript',
    'cs': 'cs',
}

# Windows reserved device names that cause errors when PMD tries to scan them
WINDOWS_RESERVED_NAMES = {'nul', 'con', 'prn', 'aux'}


def write_temp_path_list(paths, prefix: str, logger) -> Path | None:
    """Write a set/list of paths (one resolved absolute path per line) to a temp file.

    Shared by both the exclude-file-list and the --file-list builders. Returns
    None when there is nothing to write or the temp file cannot be created.
    """
    if not paths:
        return None
    try:
        fd, temp_path = tempfile.mkstemp(suffix='.txt', prefix=prefix)
        with open(fd, 'w', encoding='utf-8') as f:
            for p in sorted({Path(x).resolve() for x in paths}):
                f.write(f"{p}\n")
        return Path(temp_path)
    except Exception as e:
        logger.warning(f"Warning: Could not create temp path list: {e}")
        return None


def resolve_filtered_pmd_files(rule, exclude_patterns: list[str]) -> list[Path]:
    """Resolve a PMD rule's filter set to absolute files for its language.

    Drops files matching the language's exclude_patterns (e.g. *.g.dart) so a
    changed generated file is not fed to CPD. Caller must already know a filter
    is active (rule.filter_files is not None).
    """
    from file_discovery import FileDiscovery
    exts = tuple(FileDiscovery.LANGUAGE_EXTENSIONS.get((rule.language or '').lower(), []))
    kept: list[Path] = []
    for p in rule._filtered_paths(exts) or []:
        try:
            rel = str(p.relative_to(rule.base_path)).replace('\\', '/')
        except ValueError:
            rel = p.name
        name = rel.rsplit('/', 1)[-1]
        if any(rule._match_file_path(rel, pat) or rule._match_file_path(name, pat) for pat in exclude_patterns):
            continue
        kept.append(p)
    return kept


def get_exclude_patterns(config, language: str | None) -> list[str]:
    """Resolve file patterns to exclude from config or per-language defaults."""
    lang = language.lower() if language else None
    pmd_lang = LANGUAGE_TO_PMD.get(lang) if lang else None
    if 'exclude_patterns' in config:
        exclude_config = config['exclude_patterns']
        if isinstance(exclude_config, dict):
            return exclude_config.get(lang, exclude_config.get(pmd_lang, []))
        if isinstance(exclude_config, list):
            return exclude_config
    return DEFAULT_EXCLUDE_PATTERNS.get(lang, DEFAULT_EXCLUDE_PATTERNS.get(pmd_lang, []))


def generate_exclude_file_list(base_path, exclude_patterns: list[str], logger) -> Path | None:
    """Write a temp file listing every project file matching exclude_patterns."""
    if not exclude_patterns or not base_path:
        return None
    excluded_files = set()
    for pattern in exclude_patterns:
        if pattern.endswith('/**'):
            pattern = pattern + '/*'
        try:
            for file_path in base_path.rglob(pattern):
                if file_path.is_file():
                    excluded_files.add(file_path.resolve())
        except Exception as e:
            logger.warning(f"Warning: Could not process pattern '{pattern}': {e}")
    return write_temp_path_list(excluded_files, 'pmd_exclude_', logger)


def filter_pmd_stderr(stderr: str) -> str:
    """Drop stderr lines about Windows reserved device names (nul, con, prn, aux).

    PMD emits harmless, noisy warnings for paths containing those names.
    """
    if not stderr:
        return stderr
    filtered = []
    for line in stderr.strip().splitlines():
        line_lower = line.lower()
        if not any(f'\\{name}' in line_lower or line_lower.endswith(name) for name in WINDOWS_RESERVED_NAMES):
            filtered.append(line)
    return '\n'.join(filtered)


def run_cpd(rule, cmd_base: list[str], directory: Path, exclude_paths: list[str],
            exclude_patterns: list[str], filtered: list[Path] | None) -> RuleResult:
    """Append scan-source args to cmd_base, run PMD CPD, return a RuleResult.

    Shared by both CPD rules. When ``filtered`` is provided, scan exactly those
    files via --file-list (excludes are meaningless against a curated list);
    otherwise scan the whole directory with the configured excludes. Handles
    temp-file cleanup, stderr filtering, and delegates parsing to the rule's
    ``_result_from_pmd_stdout``.
    """
    cmd = list(cmd_base)
    temps: list[Path | None] = []
    if filtered is not None:
        file_list = write_temp_path_list(filtered, 'pmd_files_', rule.logger)
        temps.append(file_list)
        cmd.extend(['--file-list', str(file_list)])
    else:
        cmd.extend(['-d', str(directory)])
        for path in exclude_paths:
            exclude_dir = directory / path
            if exclude_dir.exists():
                cmd.extend(['--exclude', str(exclude_dir)])
        exclude_file_list = generate_exclude_file_list(directory, exclude_patterns, rule.logger)
        temps.append(exclude_file_list)
        if exclude_file_list:
            cmd.extend(['--exclude-file-list', str(exclude_file_list)])

    try:
        result = rule._run_subprocess(cmd)
        if result.returncode != 0 and result.stderr:
            filtered_stderr = filter_pmd_stderr(result.stderr)
            if filtered_stderr:
                rule.logger.warning(f"PMD CPD warning: {filtered_stderr}")
        return rule._result_from_pmd_stdout(result.stdout)
    except Exception as e:
        rule.logger.error(f"Error running PMD CPD: {e}")
        return rule._failed(f"error running PMD CPD: {e}")
    finally:
        for tmp in temps:
            if tmp and tmp.exists():
                with contextlib.suppress(Exception):
                    tmp.unlink()


@dataclass(frozen=True)
class CpdParams:
    """Resolved inputs for a CPD run, produced by PMDCpdRule._prepare_cpd."""
    pmd_path: str
    pmd_language: str
    minimum_tokens: int
    exclude_paths: list[str]
    exclude_patterns: list[str]
    filtered: list[Path] | None


class PMDCpdRule(ProjectWideRule):
    """Base for PMD CPD rules: shared language/exclude resolution and setup.

    Subclasses implement ``_run`` (calling ``_prepare_cpd`` then ``_run_pmd_cpd``)
    and ``_result_from_pmd_stdout`` / XML parsing.
    """

    def _get_pmd_language(self) -> str | None:
        """Map analyzer language to PMD language code."""
        return LANGUAGE_TO_PMD.get(self.language.lower())

    def _get_exclude_paths(self) -> list[str]:
        """Get directory paths to exclude from config."""
        return self.config.get('exclude_paths', [])

    def _get_exclude_patterns(self) -> list[str]:
        """Get file patterns to exclude from config or defaults for current language."""
        return get_exclude_patterns(self.config, self.language)

    def _prepare_cpd(self, start_message: str) -> "CpdParams | RuleResult":
        """Resolve common CPD inputs, or return a RuleResult to short-circuit.

        Returns a RuleResult when PMD is missing, the language is unsupported, or
        a filter leaves fewer than 2 files (CPD compares files against each other).
        Otherwise returns the CpdParams for ``_run_pmd_cpd``.
        """
        self.logger.info(start_message)

        pmd_path = self._get_tool_path('pmd', self.settings.get_pmd_path, self.settings.prompt_and_save_pmd_path)
        if not pmd_path:
            return self._failed("PMD executable not found")

        pmd_language = self._get_pmd_language()
        if not pmd_language:
            return self._skipped(f"language '{self.language}' not supported by PMD CPD")

        minimum_tokens = self.config.get('minimum_tokens', 100)
        max_results = self.config.get('max_results', None)
        if max_results and not self.max_errors:
            self.max_errors = max_results
        exclude_paths = self._get_exclude_paths()
        exclude_patterns = self._get_exclude_patterns()

        # When filtering (--only-changed / --file), scope CPD to the changed files.
        filtered = None
        if self.filter_files is not None:
            filtered = resolve_filtered_pmd_files(self, exclude_patterns)
            if len(filtered) < 2:
                self.logger.info("Skipping check: fewer than 2 changed files of this language.")
                return self._ok([])

        return CpdParams(pmd_path, pmd_language, minimum_tokens, exclude_paths, exclude_patterns, filtered)
