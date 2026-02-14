"""
Main code analyzer
"""

from pathlib import Path

from config import Config
from file_discovery import FileDiscovery
from models import LogLevel, Violation
from rules import (
    DartAnalyzeRule,
    DartCodeLinterRule,
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
    MaxLinesRule,
    PHPCSFixerAnalyzeRule,
    PHPStanAnalyzeRule,
    PMDDuplicatesRule,
    RuffAnalyzeRule,
)


class CodeAnalyzer:
    """Main analyzer that orchestrates the analysis workflow"""

    def __init__(self, language: str, path: str, rules_file: str, output_folder: Path | None = None, cli_log_level: LogLevel | None = None, max_errors: int | None = None):
        self.language = language
        self.path = path
        self.base_path = Path(path).resolve()
        self.config = Config(rules_file)
        self.rules_file = self.config.rules_file
        self.violations: list[Violation] = []
        self.files: list[Path] = []
        self.output_folder = output_folder
        self.cli_log_level = cli_log_level  # CLI-provided log level (highest priority)
        self.max_errors = max_errors

    def analyze(self):
        """Run the analysis"""
        # Get exclude patterns from max_lines_per_file config if available
        exclude_patterns = None
        if self.config.is_rule_enabled('max_lines_per_file'):
            rule_config = self.config.get_rule('max_lines_per_file')
            exclude_patterns = rule_config.get('exclude_patterns')

        # Discover files
        discovery = FileDiscovery(self.language, self.path, exclude_patterns)
        self.files = discovery.discover()

        if not self.files:
            print(f"No files found to analyze in '{self.path}'")
            return

        # Run PMD duplicates check (once per analysis, not per file)
        if self.config.is_rule_enabled('pmd_duplicates'):
            rule_config = self.config.get_rule('pmd_duplicates')
            pmd_log_level = self._resolve_log_level('pmd_duplicates')
            pmd_rule = PMDDuplicatesRule(
                rule_config,
                self.base_path,
                self.language,
                self.output_folder,
                pmd_log_level,
                self.max_errors,
                self.rules_file
            )
            # PMD analyzes the entire directory, so we just call it once with any file
            if self.files:
                violations = pmd_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run dart analyze check (once per analysis, not per file)
        if self.config.is_rule_enabled('dart_analyze'):
            rule_config = self.config.get_rule('dart_analyze')
            dart_log_level = self._resolve_log_level('dart_analyze')
            dart_rule = DartAnalyzeRule(
                rule_config,
                self.base_path,
                self.output_folder,
                dart_log_level,
                self.max_errors,
                self.rules_file
            )
            # Dart analyze analyzes the entire project, so we just call it once with any file
            if self.files:
                violations = dart_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run dart_code_linter check (once per analysis, not per file)
        if self.config.is_rule_enabled('dart_code_linter'):
            rule_config = self.config.get_rule('dart_code_linter')
            dcm_log_level = self._resolve_log_level('dart_code_linter')
            dcm_rule = DartCodeLinterRule(
                rule_config,
                self.base_path,
                self.output_folder,
                dcm_log_level,
                self.max_errors,
                self.rules_file
            )
            # Dart Code Linter analyzes the entire project, so we just call it once with any file
            if self.files:
                violations = dcm_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run flutter analyze check (once per analysis, not per file)
        if self.config.is_rule_enabled('flutter_analyze'):
            rule_config = self.config.get_rule('flutter_analyze')
            flutter_log_level = self._resolve_log_level('flutter_analyze')
            flutter_rule = FlutterAnalyzeRule(
                rule_config,
                self.base_path,
                self.output_folder,
                flutter_log_level,
                self.max_errors,
                self.rules_file
            )
            # Flutter analyze analyzes the entire project, so we just call it once with any file
            if self.files:
                violations = flutter_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run ruff analyze check (once per analysis, not per file)
        if self.config.is_rule_enabled('ruff_analyze'):
            rule_config = self.config.get_rule('ruff_analyze')
            ruff_log_level = self._resolve_log_level('ruff_analyze')
            ruff_rule = RuffAnalyzeRule(
                rule_config,
                self.base_path,
                self.output_folder,
                ruff_log_level,
                self.max_errors,
                self.rules_file
            )
            # Ruff analyzes the entire project, so we just call it once with any file
            if self.files:
                violations = ruff_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run ESLint analyze check (once per analysis, not per file)
        if self.config.is_rule_enabled('eslint_analyze'):
            rule_config = self.config.get_rule('eslint_analyze')
            eslint_log_level = self._resolve_log_level('eslint_analyze')
            eslint_rule = ESLintAnalyzeRule(
                rule_config,
                self.base_path,
                self.output_folder,
                eslint_log_level,
                self.max_errors,
                self.rules_file
            )
            # ESLint analyzes the entire project, so we just call it once with any file
            if self.files:
                violations = eslint_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run PHPStan analyze check (once per analysis, not per file)
        if self.config.is_rule_enabled('phpstan_analyze'):
            rule_config = self.config.get_rule('phpstan_analyze')
            phpstan_log_level = self._resolve_log_level('phpstan_analyze')
            phpstan_rule = PHPStanAnalyzeRule(
                rule_config,
                self.base_path,
                self.output_folder,
                phpstan_log_level,
                self.max_errors,
                self.rules_file
            )
            # PHPStan analyzes the entire project, so we just call it once with any file
            if self.files:
                violations = phpstan_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run PHP-CS-Fixer check (once per analysis, not per file)
        if self.config.is_rule_enabled('php_cs_fixer'):
            rule_config = self.config.get_rule('php_cs_fixer')
            fixer_log_level = self._resolve_log_level('php_cs_fixer')
            fixer_rule = PHPCSFixerAnalyzeRule(
                rule_config,
                self.base_path,
                self.output_folder,
                fixer_log_level,
                self.max_errors,
                self.rules_file
            )
            # PHP-CS-Fixer analyzes the entire project, so we just call it once with any file
            if self.files:
                violations = fixer_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run Intelephense analyze check (once per analysis, not per file)
        if self.config.is_rule_enabled('intelephense_analyze'):
            rule_config = self.config.get_rule('intelephense_analyze')
            intelephense_log_level = self._resolve_log_level('intelephense_analyze')
            intelephense_rule = IntelephenseAnalyzeRule(
                rule_config,
                self.base_path,
                self.output_folder,
                intelephense_log_level,
                self.max_errors,
                self.rules_file
            )
            # Intelephense analyzes the entire project, so we just call it once with any file
            if self.files:
                violations = intelephense_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run dotnet analyze check (once per analysis, not per file)
        if self.config.is_rule_enabled('dotnet_analyze'):
            rule_config = self.config.get_rule('dotnet_analyze')
            dotnet_log_level = self._resolve_log_level('dotnet_analyze')
            dotnet_rule = DotnetAnalyzeRule(
                rule_config,
                self.base_path,
                self.output_folder,
                dotnet_log_level,
                self.max_errors,
                self.rules_file
            )
            # Dotnet analyzes the entire project, so we just call it once with any file
            if self.files:
                violations = dotnet_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run dart unused files check (once per analysis, not per file)
        if self.config.is_rule_enabled('dart_unused_files'):
            rule_config = self.config.get_rule('dart_unused_files')
            rule_log_level = self._resolve_log_level('dart_unused_files')
            rule = DartUnusedFilesRule(
                rule_config,
                self.base_path,
                self.output_folder,
                rule_log_level,
                self.max_errors,
                self.rules_file
            )
            if self.files:
                violations = rule.check(self.files[0])
                self.violations.extend(violations)

        # Run dart unused dependencies check (once per analysis, not per file)
        if self.config.is_rule_enabled('dart_unused_dependencies'):
            rule_config = self.config.get_rule('dart_unused_dependencies')
            rule_log_level = self._resolve_log_level('dart_unused_dependencies')
            rule = DartUnusedDependenciesRule(
                rule_config,
                self.base_path,
                self.output_folder,
                rule_log_level,
                self.max_errors,
                self.rules_file
            )
            if self.files:
                violations = rule.check(self.files[0])
                self.violations.extend(violations)

        # Run dart import rules check (once per analysis, not per file)
        if self.config.is_rule_enabled('dart_import_rules'):
            rule_config = self.config.get_rule('dart_import_rules')
            rule_log_level = self._resolve_log_level('dart_import_rules')
            rule = DartImportRulesRule(
                rule_config,
                self.base_path,
                self.output_folder,
                rule_log_level,
                self.max_errors,
                self.rules_file
            )
            if self.files:
                violations = rule.check(self.files[0])
                self.violations.extend(violations)

        # Run dart unused code check (once per analysis, not per file)
        if self.config.is_rule_enabled('dart_unused_code'):
            rule_config = self.config.get_rule('dart_unused_code')
            rule_log_level = self._resolve_log_level('dart_unused_code')
            rule = DartUnusedCodeRule(
                rule_config,
                self.base_path,
                self.output_folder,
                rule_log_level,
                self.max_errors,
                self.rules_file
            )
            if self.files:
                violations = rule.check(self.files[0])
                self.violations.extend(violations)

        # Run dart missing dispose check (once per analysis, not per file)
        if self.config.is_rule_enabled('dart_missing_dispose'):
            rule_config = self.config.get_rule('dart_missing_dispose')
            rule_log_level = self._resolve_log_level('dart_missing_dispose')
            rule = DartMissingDisposeRule(
                rule_config,
                self.base_path,
                self.output_folder,
                rule_log_level,
                self.max_errors,
                self.rules_file
            )
            if self.files:
                violations = rule.check(self.files[0])
                self.violations.extend(violations)

        # Run dart test coverage check (once per analysis, not per file)
        if self.config.is_rule_enabled('dart_test_coverage'):
            rule_config = self.config.get_rule('dart_test_coverage')
            rule_log_level = self._resolve_log_level('dart_test_coverage')
            rule = DartTestCoverageRule(
                rule_config,
                self.base_path,
                self.output_folder,
                rule_log_level,
                self.max_errors,
                self.rules_file
            )
            if self.files:
                violations = rule.check(self.files[0])
                self.violations.extend(violations)

        # Run per-file rules on each file
        for file_path in self.files:
            self._check_file(file_path)

    def get_analyzed_file_paths(self) -> list[str]:
        """Get relative paths of all analyzed files."""
        paths = []
        for file_path in self.files:
            relative = file_path.relative_to(self.base_path) if file_path.is_relative_to(self.base_path) else file_path
            paths.append(str(relative))
        return paths

    def _check_file(self, file_path: Path):
        """Check a single file against all enabled rules"""
        # Check max lines rule
        if self.config.is_rule_enabled('max_lines_per_file'):
            rule_config = self.config.get_rule('max_lines_per_file')
            max_lines_log_level = self._resolve_log_level('max_lines_per_file')
            rule = MaxLinesRule(rule_config, self.base_path, max_lines_log_level, self.max_errors, self.rules_file)
            violations = rule.check(file_path)
            self.violations.extend(violations)

    def get_violations(self) -> list[Violation]:
        """Get all violations found"""
        return self.violations

    def get_file_count(self) -> int:
        """Get number of files analyzed"""
        return len(self.files)

    def _resolve_log_level(self, rule_name: str) -> LogLevel:
        """Resolve log level for a rule using precedence: CLI > per-rule > global > default.

        Args:
            rule_name: Name of the rule

        Returns:
            Resolved LogLevel enum value
        """
        # 1. CLI flag has highest priority
        if self.cli_log_level is not None:
            return self.cli_log_level

        # 2. Per-rule log level from rules.json
        rule_log_level_str = self.config.get_rule_log_level(rule_name)
        if rule_log_level_str:
            try:
                return LogLevel(rule_log_level_str)
            except ValueError:
                print(f"Warning: Invalid log_level '{rule_log_level_str}' for rule '{rule_name}', using default")

        # 3. Global log level from rules.json
        global_log_level_str = self.config.get_global_log_level()
        if global_log_level_str:
            try:
                return LogLevel(global_log_level_str)
            except ValueError:
                print(f"Warning: Invalid global log_level '{global_log_level_str}', using default")

        # 4. Default to ALL
        return LogLevel.ALL
