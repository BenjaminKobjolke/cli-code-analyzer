"""Registry of project-wide analyzers and their filter-mode behavior.

Separated from analyzer.py to keep the orchestrator focused. PROJECT_WIDE_ANALYZERS
maps each project-wide analyzer name to its rule class; FILTER_INCAPABLE lists the
ones that cannot be scoped to a file subset and are skipped under --only-changed /
--file (see CodeAnalyzer.analyze).
"""

from rules import (
    AutoHotkeyAnalyzeRule,
    DartAnalyzeRule,
    DartCodeLinterRule,
    DartCrapScoreRule,
    DartImportRulesRule,
    DartMissingDisposeRule,
    DartTestCoverageRule,
    DartUnusedCodeRule,
    DartUnusedDependenciesRule,
    DartUnusedFilesRule,
    DotnetAnalyzeRule,
    ESLintAnalyzeRule,
    FlutterAnalyzeRule,
    IntelephenseAnalyzeRule,
    PHPCSFixerAnalyzeRule,
    PHPStanAnalyzeRule,
    PyscnAnalyzeRule,
    PythonCrapScoreRule,
    PythonTestCoverageRule,
    RuffAnalyzeRule,
    SvelteCheckRule,
    TscAnalyzeRule,
)

PROJECT_WIDE_ANALYZERS = [
    ('autohotkey_analyze', AutoHotkeyAnalyzeRule),
    ('dart_analyze', DartAnalyzeRule),
    ('dart_code_linter', DartCodeLinterRule),
    ('flutter_analyze', FlutterAnalyzeRule),
    ('ruff_analyze', RuffAnalyzeRule),
    ('pyscn_analyze', PyscnAnalyzeRule),
    ('eslint_analyze', ESLintAnalyzeRule),
    ('svelte_check', SvelteCheckRule),
    ('tsc_analyze', TscAnalyzeRule),
    ('phpstan_analyze', PHPStanAnalyzeRule),
    ('php_cs_fixer', PHPCSFixerAnalyzeRule),
    ('intelephense_analyze', IntelephenseAnalyzeRule),
    ('dotnet_analyze', DotnetAnalyzeRule),
    ('dart_unused_files', DartUnusedFilesRule),
    ('dart_unused_dependencies', DartUnusedDependenciesRule),
    ('dart_import_rules', DartImportRulesRule),
    ('dart_unused_code', DartUnusedCodeRule),
    ('dart_missing_dispose', DartMissingDisposeRule),
    ('dart_test_coverage', DartTestCoverageRule),
    ('dart_crap_score', DartCrapScoreRule),
    ('python_test_coverage', PythonTestCoverageRule),
    ('python_crap_score', PythonCrapScoreRule),
]

# Project-wide analyzers that cannot be meaningfully scoped to a file subset
# (cross-file/whole-graph analysis, project/solution-based tools, or whole-suite
# coverage). Under --only-changed / --file these are skipped rather than run over
# the whole project. The scopeable ones (dart_analyze, flutter_analyze,
# ruff_analyze, eslint_analyze, phpstan_analyze, and PMD) accept a file list and
# are scoped instead — see BaseRule._scope_args / PMD --file-list.
FILTER_INCAPABLE = {
    'dart_code_linter', 'pyscn_analyze', 'svelte_check', 'tsc_analyze',
    'php_cs_fixer', 'intelephense_analyze', 'dotnet_analyze',
    'dart_unused_files', 'dart_unused_dependencies', 'dart_import_rules',
    'dart_unused_code', 'dart_missing_dispose',
    'dart_test_coverage', 'dart_crap_score',
    'python_test_coverage', 'python_crap_score',
}
