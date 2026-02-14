"""
Rules module
"""

from rules.base import BaseRule
from rules.dart_analyze import DartAnalyzeRule
from rules.dart_code_linter import DartCodeLinterRule
from rules.dart_import_rules import DartImportRulesRule
from rules.dart_missing_dispose import DartMissingDisposeRule
from rules.dart_test_coverage import DartTestCoverageRule
from rules.dart_unused_code import DartUnusedCodeRule
from rules.dart_unused_dependencies import DartUnusedDependenciesRule
from rules.dart_unused_files import DartUnusedFilesRule
from rules.dotnet_analyze import DotnetAnalyzeRule
from rules.eslint_analyze import ESLintAnalyzeRule
from rules.flutter_analyze import FlutterAnalyzeRule
from rules.intelephense_analyze import IntelephenseAnalyzeRule
from rules.max_lines import MaxLinesRule
from rules.php_cs_fixer_analyze import PHPCSFixerAnalyzeRule
from rules.phpstan_analyze import PHPStanAnalyzeRule
from rules.pmd_duplicates import PMDDuplicatesRule
from rules.ruff_analyze import RuffAnalyzeRule
from rules.svelte_check import SvelteCheckRule

__all__ = [
    'BaseRule',
    'DartAnalyzeRule',
    'DartCodeLinterRule',
    'DartImportRulesRule',
    'DartMissingDisposeRule',
    'DartTestCoverageRule',
    'DartUnusedCodeRule',
    'DartUnusedDependenciesRule',
    'DartUnusedFilesRule',
    'DotnetAnalyzeRule',
    'ESLintAnalyzeRule',
    'FlutterAnalyzeRule',
    'IntelephenseAnalyzeRule',
    'MaxLinesRule',
    'PHPCSFixerAnalyzeRule',
    'PHPStanAnalyzeRule',
    'PMDDuplicatesRule',
    'RuffAnalyzeRule',
    'SvelteCheckRule',
]
