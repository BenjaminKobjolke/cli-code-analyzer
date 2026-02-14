"""PMD duplicate code detection rule"""

import contextlib
import csv
import tempfile
from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings

# Default exclude patterns per language (glob patterns)
DEFAULT_EXCLUDE_PATTERNS = {
    'dart': ['*.g.dart', '*.freezed.dart'],
    'python': ['**/__pycache__/**', '*.pyc'],
    'java': ['**/target/**', '**/build/**'],
    'javascript': ['**/node_modules/**', '**/dist/**', '**/build/**'],
    'typescript': ['**/node_modules/**', '**/dist/**', '**/build/**'],
    'php': ['**/vendor/**', '**/node_modules/**'],
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


class PMDDuplicatesRule(BaseRule):
    """Rule to detect duplicate code using PMD CPD"""

    def __init__(self, config: dict, base_path: Path | None = None, language: str | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        """Initialize PMD duplicates rule with config and output settings."""
        super().__init__(config, base_path, log_level, max_errors, rules_file_path)
        self.language = language
        self.output_folder = output_folder
        self.settings = Settings()
        self._pmd_executed = False

    def check(self, _file_path: Path) -> list[Violation]:
        """Run PMD CPD on the entire directory (executes once, returns empty for subsequent calls)."""
        if self._pmd_executed:
            return []
        self._pmd_executed = True

        print("\nChecking for duplicate code...")

        pmd_path = self._get_tool_path('pmd', self.settings.get_pmd_path, self.settings.prompt_and_save_pmd_path)
        if not pmd_path:
            return []

        pmd_language = self._get_pmd_language()
        if not pmd_language:
            print(f"Warning: Language '{self.language}' not supported by PMD CPD")
            return []

        minimum_tokens = self.config.get('minimum_tokens', 100)
        max_results = self.config.get('max_results', None)
        if max_results and not self.max_errors:
            self.max_errors = max_results
        exclude_paths = self._get_exclude_paths()
        exclude_patterns = self._get_exclude_patterns()
        output_format = 'csv' if self.output_folder else 'text'
        output_file = self.output_folder / 'duplicate_code.csv' if self.output_folder else None

        violations = self._run_pmd_cpd(pmd_path, pmd_language, self.base_path, minimum_tokens,
                                        exclude_paths, exclude_patterns, output_format, output_file)
        return self._filter_violations_by_log_level(violations)

    def _get_pmd_language(self) -> str | None:
        """Map analyzer language to PMD language code."""
        return LANGUAGE_TO_PMD.get(self.language.lower())

    def _get_exclude_paths(self) -> list[str]:
        """Get directory paths to exclude from config."""
        return self.config.get('exclude_paths', [])

    def _get_exclude_patterns(self) -> list[str]:
        """Get file patterns to exclude from config or defaults for current language."""
        lang = self.language.lower() if self.language else None
        pmd_lang = self._get_pmd_language()
        if 'exclude_patterns' in self.config:
            exclude_config = self.config['exclude_patterns']
            if isinstance(exclude_config, dict):
                return exclude_config.get(lang, exclude_config.get(pmd_lang, []))
            if isinstance(exclude_config, list):
                return exclude_config
        return DEFAULT_EXCLUDE_PATTERNS.get(lang, DEFAULT_EXCLUDE_PATTERNS.get(pmd_lang, []))

    def _generate_exclude_file_list(self, exclude_patterns: list[str]) -> Path | None:
        """Generate temp file with paths matching exclude patterns."""
        if not exclude_patterns or not self.base_path:
            return None

        excluded_files = set()
        for pattern in exclude_patterns:
            if pattern.endswith('/**'):
                pattern = pattern + '/*'
            try:
                for file_path in self.base_path.rglob(pattern):
                    if file_path.is_file():
                        excluded_files.add(file_path.resolve())
            except Exception as e:
                print(f"Warning: Could not process pattern '{pattern}': {e}")

        if not excluded_files:
            return None

        try:
            fd, temp_path = tempfile.mkstemp(suffix='.txt', prefix='pmd_exclude_')
            with open(fd, 'w', encoding='utf-8') as f:
                for file_path in sorted(excluded_files):
                    f.write(f"{file_path}\n")
            return Path(temp_path)
        except Exception as e:
            print(f"Warning: Could not create exclude file list: {e}")
            return None

    def _filter_pmd_stderr(self, stderr: str) -> str:
        """Filter out stderr lines about Windows reserved device names (nul, con, etc.)."""
        if not stderr:
            return stderr
        lines = stderr.strip().splitlines()
        filtered = [line for line in lines
                     if not any(name in line.lower() for name in WINDOWS_RESERVED_NAMES
                                if f'\\{name}' in line.lower() or line.lower().endswith(name))]
        return '\n'.join(filtered)

    def _run_pmd_cpd(self, pmd_path: str, language: str, directory: Path, minimum_tokens: int,
                      exclude_paths: list[str], exclude_patterns: list[str], output_format: str, output_file: Path | None) -> list[Violation]:
        """Execute PMD CPD and return parsed violations."""
        exclude_file_list = self._generate_exclude_file_list(exclude_patterns)
        cmd = [pmd_path, 'cpd', '-l', language, '-d', str(directory), '-f', output_format,
               '--minimum-tokens', str(minimum_tokens), '--encoding', 'utf-8']

        # Add directory exclusions using --exclude flag
        for path in exclude_paths:
            exclude_dir = directory / path
            if exclude_dir.exists():
                cmd.extend(['--exclude', str(exclude_dir)])

        if exclude_file_list:
            cmd.extend(['--exclude-file-list', str(exclude_file_list)])

        try:
            result = self._run_subprocess(cmd)
            if result.returncode != 0 and result.stderr:
                filtered_stderr = self._filter_pmd_stderr(result.stderr)
                if filtered_stderr:
                    print(f"PMD CPD warning: {filtered_stderr}")

            if output_file:
                if self._has_duplicates_in_csv(result.stdout):
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(result.stdout)
                    print(f"Duplicate code report saved to: {output_file}")
                    return self._parse_csv_output(output_file)
                print("No duplicate code found.")
                return []

            if result.stdout:
                print("\n" + "="*80 + "\nDUPLICATE CODE DETECTION RESULTS (PMD CPD)\n" + "="*80)
                print(result.stdout)
                print("="*80 + "\n")
            return self._parse_text_output(result.stdout)
        except Exception as e:
            print(f"Error running PMD CPD: {e}")
            return []
        finally:
            if exclude_file_list and exclude_file_list.exists():
                with contextlib.suppress(Exception):
                    exclude_file_list.unlink()

    def _has_duplicates_in_csv(self, csv_content: str) -> bool:
        """Check if CSV output has data rows (header + at least one data row)."""
        if not csv_content or not csv_content.strip():
            return False
        return len(csv_content.strip().split('\n')) > 1

    def _parse_csv_output(self, csv_file: Path) -> list[Violation]:
        """Parse PMD CPD CSV output into violations and print statistics."""
        violations = []
        try:
            with open(csv_file, encoding='utf-8') as f:
                rows = list(csv.DictReader(f))

            if rows:
                total_lines = sum(int(r.get('lines', 0)) for r in rows if r.get('lines', '').isdigit())
                print(f"\n{'='*80}\nDUPLICATE CODE DETECTION RESULTS\n{'='*80}")
                print(f"Total CSV lines (duplicates found): {len(rows)}")
                print(f"Total duplicate code lines: {total_lines}\n{'='*80}\n")

            for row in rows:
                msg = f"Duplicate code found: {row.get('lines', 'N/A')} lines, {row.get('tokens', 'N/A')} tokens, {row.get('occurrences', 'N/A')} occurrences"
                violations.append(Violation(file_path='multiple files', rule_name='pmd_duplicates',
                                            severity=Severity.WARNING, message=msg))
        except Exception as e:
            print(f"Error parsing PMD CSV output: {e}")

        if self.max_errors and len(violations) > self.max_errors:
            def get_lines(v):
                parts = v.message.split()
                return int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
            violations.sort(key=get_lines, reverse=True)
            violations = violations[:self.max_errors]

        return violations

    def _parse_text_output(self, text_output: str) -> list[Violation]:
        """Parse PMD CPD text output into violations from 'Found...duplicate' lines."""
        violations = []
        if text_output and 'Found' in text_output:
            for line in text_output.strip().split('\n'):
                if 'Found' in line and 'duplicate' in line.lower():
                    violations.append(Violation(file_path='multiple files', rule_name='pmd_duplicates',
                                                severity=Severity.WARNING, message=line.strip()))
        return violations
