"""
Main code analyzer
"""

from pathlib import Path

from analyzer_registry import get_analyzers_for_language
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
    SvelteCheckRule,
    TscAnalyzeRule,
)


class CodeAnalyzer:
    """Main analyzer that orchestrates the analysis workflow"""

    _PROJECT_WIDE_ANALYZERS = [
        ('dart_analyze', DartAnalyzeRule),
        ('dart_code_linter', DartCodeLinterRule),
        ('flutter_analyze', FlutterAnalyzeRule),
        ('ruff_analyze', RuffAnalyzeRule),
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
    ]

    def __init__(self, languages: str | list[str], path: str, rules_file: str, output_folder: Path | None = None, cli_log_level: LogLevel | None = None, max_errors: int | None = None):
        if isinstance(languages, str):
            languages = [languages]
        self.languages = languages
        self.path = path
        self.base_path = Path(path).resolve()
        self.config = Config(rules_file)
        self.rules_file = self.config.rules_file
        self.violations: list[Violation] = []
        self.files: list[Path] = []
        self.output_folder = output_folder
        self.cli_log_level = cli_log_level  # CLI-provided log level (highest priority)
        self.max_errors = max_errors
        self._enabled_analyzers = self._get_enabled_analyzers()
        self._multi_language = len(self.languages) > 1
        self._last_language_header = None

    def _get_enabled_analyzers(self) -> set[str]:
        """Get the set of analyzer names valid for the requested languages."""
        analyzers = set()
        for lang in self.languages:
            for name, _desc, _req in get_analyzers_for_language(lang):
                analyzers.add(name)
        return analyzers

    def _should_run(self, analyzer_name: str) -> bool:
        """Check if an analyzer should run (in language set AND enabled in rules)."""
        return analyzer_name in self._enabled_analyzers and self.config.is_rule_enabled(analyzer_name)

    def _get_languages_for_analyzer(self, analyzer_name: str) -> list[str]:
        """Get which of the requested languages have a given analyzer registered."""
        langs = []
        for lang in self.languages:
            for name, _desc, _req in get_analyzers_for_language(lang):
                if name == analyzer_name:
                    langs.append(lang)
                    break
        return langs

    def _print_language_header(self, analyzer_name: str) -> None:
        """Print a language context header when running multiple languages.

        Only prints when the language differs from the last printed header.
        """
        if not self._multi_language:
            return
        langs = self._get_languages_for_analyzer(analyzer_name)
        lang_key = ', '.join(langs)
        if langs and lang_key != self._last_language_header:
            self._last_language_header = lang_key
            print(f"\n--- {lang_key} ---")

    def analyze(self):
        """Run the analysis"""
        # Get exclude patterns from max_lines_per_file config if available
        exclude_patterns = None
        if self.config.is_rule_enabled('max_lines_per_file'):
            rule_config = self.config.get_rule('max_lines_per_file')
            exclude_patterns = rule_config.get('exclude_patterns')

        # Discover files (single pass for all languages)
        print(f"\nDiscovering files...")
        discovery = FileDiscovery(self.languages, self.path, exclude_patterns)
        self.files = discovery.discover()
        print(f"Found {len(self.files)} file(s)")

        if not self.files:
            print(f"No files found to analyze in '{self.path}'")
            return

        # INVARIANT: self.files is non-empty beyond this point.
        # Project-wide analyzers receive self.files[0] as a dummy argument
        # (they ignore it and analyze the entire base_path instead).

        # Run PMD duplicates check (once per language that has it registered)
        if self._should_run('pmd_duplicates'):
            rule_config = self.config.get_rule('pmd_duplicates')
            pmd_log_level = self._resolve_log_level('pmd_duplicates')
            # PMD needs a language parameter, so run once per language that has it
            pmd_languages = self._get_languages_for_analyzer('pmd_duplicates')
            for pmd_lang in pmd_languages:
                if self._multi_language:
                    self._last_language_header = pmd_lang
                    print(f"\n--- {pmd_lang} ---")
                pmd_rule = PMDDuplicatesRule(
                    rule_config,
                    self.base_path,
                    pmd_lang,
                    self.output_folder,
                    pmd_log_level,
                    self.max_errors,
                    self.rules_file
                )
                violations = pmd_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run project-wide analyzers (each runs once, not per file)
        for analyzer_name, RuleClass in self._PROJECT_WIDE_ANALYZERS:
            if self._should_run(analyzer_name):
                self._print_language_header(analyzer_name)
                rule_config = self.config.get_rule(analyzer_name)
                log_level = self._resolve_log_level(analyzer_name)
                rule = RuleClass(
                    rule_config,
                    self.base_path,
                    self.output_folder,
                    log_level,
                    self.max_errors,
                    self.rules_file
                )
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
        if self._should_run('max_lines_per_file'):
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
