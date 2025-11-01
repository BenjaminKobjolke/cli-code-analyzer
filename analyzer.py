"""
Main code analyzer
"""

from typing import List, Optional
from pathlib import Path
from config import Config
from file_discovery import FileDiscovery
from rules import MaxLinesRule, PMDDuplicatesRule, DartAnalyzeRule, DartCodeLinterRule
from models import Violation, LogLevel


class CodeAnalyzer:
    """Main analyzer that orchestrates the analysis workflow"""

    def __init__(self, language: str, path: str, rules_file: str, output_folder: Optional[Path] = None, log_level: LogLevel = LogLevel.ALL, max_errors: Optional[int] = None):
        self.language = language
        self.path = path
        self.base_path = Path(path).resolve()
        self.config = Config(rules_file)
        self.violations: List[Violation] = []
        self.files: List[Path] = []
        self.output_folder = output_folder
        self.log_level = log_level
        self.max_errors = max_errors

    def analyze(self):
        """Run the analysis"""
        # Discover files
        discovery = FileDiscovery(self.language, self.path)
        self.files = discovery.discover()

        if not self.files:
            print(f"No files found to analyze in '{self.path}'")
            return

        # Run PMD duplicates check (once per analysis, not per file)
        if self.config.is_rule_enabled('pmd_duplicates'):
            rule_config = self.config.get_rule('pmd_duplicates')
            pmd_rule = PMDDuplicatesRule(
                rule_config,
                self.base_path,
                self.language,
                self.output_folder,
                self.max_errors
            )
            # PMD analyzes the entire directory, so we just call it once with any file
            if self.files:
                violations = pmd_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run dart analyze check (once per analysis, not per file)
        if self.config.is_rule_enabled('dart_analyze'):
            rule_config = self.config.get_rule('dart_analyze')
            dart_rule = DartAnalyzeRule(
                rule_config,
                self.base_path,
                self.output_folder,
                self.log_level,
                self.max_errors
            )
            # Dart analyze analyzes the entire project, so we just call it once with any file
            if self.files:
                violations = dart_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run dart_code_linter check (once per analysis, not per file)
        if self.config.is_rule_enabled('dart_code_linter'):
            rule_config = self.config.get_rule('dart_code_linter')
            dcm_rule = DartCodeLinterRule(
                rule_config,
                self.base_path,
                self.output_folder,
                self.log_level,
                self.max_errors
            )
            # Dart Code Linter analyzes the entire project, so we just call it once with any file
            if self.files:
                violations = dcm_rule.check(self.files[0])
                self.violations.extend(violations)

        # Run per-file rules on each file
        for file_path in self.files:
            self._check_file(file_path)

    def _check_file(self, file_path: Path):
        """Check a single file against all enabled rules"""
        # Check max lines rule
        if self.config.is_rule_enabled('max_lines_per_file'):
            rule_config = self.config.get_rule('max_lines_per_file')
            rule = MaxLinesRule(rule_config, self.base_path)
            violations = rule.check(file_path)
            self.violations.extend(violations)

    def get_violations(self) -> List[Violation]:
        """Get all violations found"""
        return self.violations

    def get_file_count(self) -> int:
        """Get number of files analyzed"""
        return len(self.files)
