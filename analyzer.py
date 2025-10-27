"""
Main code analyzer
"""

from typing import List
from pathlib import Path
from config import Config
from file_discovery import FileDiscovery
from rules import MaxLinesRule
from models import Violation


class CodeAnalyzer:
    """Main analyzer that orchestrates the analysis workflow"""

    def __init__(self, language: str, path: str, rules_file: str):
        self.language = language
        self.path = path
        self.base_path = Path(path).resolve()
        self.config = Config(rules_file)
        self.violations: List[Violation] = []
        self.files: List[Path] = []

    def analyze(self):
        """Run the analysis"""
        # Discover files
        discovery = FileDiscovery(self.language, self.path)
        self.files = discovery.discover()

        if not self.files:
            print(f"No files found to analyze in '{self.path}'")
            return

        # Run rules on each file
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
