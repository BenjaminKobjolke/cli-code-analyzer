"""
PMD duplicate code detection rule
"""

import contextlib
import csv
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
}


# Language mapping from analyzer to PMD
LANGUAGE_TO_PMD = {
    'flutter': 'dart',
    'dart': 'dart',
    'python': 'python',
    'java': 'java',
    'javascript': 'javascript',
    'js': 'javascript',
    'typescript': 'typescript',
    'ts': 'typescript',
}


class PMDDuplicatesRule(BaseRule):
    """Rule to detect duplicate code using PMD CPD"""

    def __init__(self, config: dict, base_path: Path | None = None, language: str | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        """Initialize PMD duplicates rule.

        Args:
            config: Rule configuration from rules.json
            base_path: Base path for analysis
            language: Programming language being analyzed
            output_folder: Optional folder for file output (None = console output)
            log_level: Log level for filtering violations
            max_errors: Optional limit on number of violations to include in CSV
            rules_file_path: Path to the rules.json file
        """
        super().__init__(config, base_path, log_level, max_errors, rules_file_path)
        self.language = language
        self.output_folder = output_folder
        self.settings = Settings()
        self._pmd_executed = False  # Track if PMD has been executed

    def check(self, _file_path: Path) -> list[Violation]:
        """Run PMD CPD on the entire directory (only once).

        Note: PMD CPD analyzes entire directories, not individual files.
        This method will execute PMD once on the first file and return empty for subsequent files.

        Args:
            file_path: Path to a file (used to determine base directory)

        Returns:
            List of violations found (only on first execution)
        """
        # Only execute PMD once per analysis run
        if self._pmd_executed:
            return []

        self._pmd_executed = True

        print("\nChecking for duplicate code...")

        # Get PMD path using base utility
        pmd_path = self._get_tool_path('pmd', self.settings.get_pmd_path, self.settings.prompt_and_save_pmd_path)
        if not pmd_path:
            return []

        # Get PMD language code
        pmd_language = self._get_pmd_language()
        if not pmd_language:
            print(f"Warning: Language '{self.language}' not supported by PMD CPD")
            return []

        # Get configuration
        minimum_tokens = self.config.get('minimum_tokens', 100)
        exclude_patterns = self._get_exclude_patterns()

        # Determine output format and file
        if self.output_folder:
            output_format = 'csv'
            output_file = self.output_folder / 'duplicate_code.csv'
        else:
            output_format = 'text'
            output_file = None

        # Run PMD CPD
        violations = self._run_pmd_cpd(
            pmd_path=pmd_path,
            language=pmd_language,
            directory=self.base_path,
            minimum_tokens=minimum_tokens,
            exclude_patterns=exclude_patterns,
            output_format=output_format,
            output_file=output_file
        )

        # Filter violations based on log level
        return self._filter_violations_by_log_level(violations)

    def _get_pmd_language(self) -> str | None:
        """Map analyzer language to PMD language code.

        Returns:
            PMD language code or None if not supported
        """
        return LANGUAGE_TO_PMD.get(self.language.lower())

    def _get_exclude_patterns(self) -> list[str]:
        """Get exclude patterns from config or defaults.

        Returns:
            List of exclude patterns
        """
        # Check if custom patterns are defined in config
        if 'exclude_patterns' in self.config:
            exclude_config = self.config['exclude_patterns']
            if isinstance(exclude_config, dict):
                pmd_language = self._get_pmd_language()
                return exclude_config.get(pmd_language, [])
            elif isinstance(exclude_config, list):
                return exclude_config

        # Use default patterns for the language
        pmd_language = self._get_pmd_language()
        return DEFAULT_EXCLUDE_PATTERNS.get(pmd_language, [])

    def _generate_exclude_file_list(self, exclude_patterns: list[str]) -> Path | None:
        """Generate a temporary file containing paths to exclude.

        Args:
            exclude_patterns: List of glob patterns (e.g., '*.g.dart')

        Returns:
            Path to temporary file, or None if no patterns
        """
        if not exclude_patterns or not self.base_path:
            return None

        # Find all files matching exclude patterns
        excluded_files = set()
        for pattern in exclude_patterns:
            # Ensure directory patterns match all files inside
            # venv/** should become venv/**/* to match files recursively
            if pattern.endswith('/**'):
                pattern = pattern + '/*'

            # Use rglob to find files matching the pattern
            try:
                for file_path in self.base_path.rglob(pattern):
                    if file_path.is_file():
                        excluded_files.add(file_path.resolve())
            except Exception as e:
                print(f"Warning: Could not process pattern '{pattern}': {e}")

        if not excluded_files:
            return None

        # Write excluded files to temporary file
        import tempfile
        try:
            # Create temp file that won't be auto-deleted
            fd, temp_path = tempfile.mkstemp(suffix='.txt', prefix='pmd_exclude_')
            with open(fd, 'w', encoding='utf-8') as f:
                for file_path in sorted(excluded_files):
                    f.write(f"{file_path}\n")
            return Path(temp_path)
        except Exception as e:
            print(f"Warning: Could not create exclude file list: {e}")
            return None

    def _run_pmd_cpd(
        self,
        pmd_path: str,
        language: str,
        directory: Path,
        minimum_tokens: int,
        exclude_patterns: list[str],
        output_format: str,
        output_file: Path | None
    ) -> list[Violation]:
        """Execute PMD CPD and parse results.

        Args:
            pmd_path: Path to PMD executable
            language: PMD language code
            directory: Directory to analyze
            minimum_tokens: Minimum tokens for duplicate detection
            exclude_patterns: List of exclude patterns
            output_format: Output format (csv or text)
            output_file: Output file path (None for stdout)

        Returns:
            List of violations
        """
        # Generate exclude file list from patterns
        exclude_file_list = self._generate_exclude_file_list(exclude_patterns)

        # Build command
        cmd = [
            pmd_path,
            'cpd',
            '-l', language,
            '-d', str(directory),
            '-f', output_format,
            '--minimum-tokens', str(minimum_tokens),
            '--encoding', 'utf-8'
        ]

        # Add exclude file list if generated
        if exclude_file_list:
            cmd.extend(['--exclude-file-list', str(exclude_file_list)])

        # Execute PMD using base utility
        try:
            if output_file:
                # First capture output to check if there are duplicates
                result = self._run_subprocess(cmd)

                if result.returncode != 0 and result.stderr:
                    print(f"PMD CPD warning: {result.stderr}")

                # Check if there are any duplicates in the output
                has_duplicates = self._has_duplicates_in_csv(result.stdout)

                if has_duplicates:
                    # Only write file if duplicates found
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(result.stdout)

                    print(f"Duplicate code report saved to: {output_file}")

                    # Print CSV content and statistics
                    self._print_csv_statistics(output_file)

                    # Parse CSV file to return violations
                    return self._parse_csv_output(output_file)
                else:
                    print("\nNo duplicate code found.")
                    return []
            else:
                # Output to console (text format)
                result = self._run_subprocess(cmd)

                if result.returncode != 0 and result.stderr:
                    print(f"PMD CPD warning: {result.stderr}")

                # Print text output directly
                if result.stdout:
                    print("\n" + "="*80)
                    print("DUPLICATE CODE DETECTION RESULTS (PMD CPD)")
                    print("="*80)
                    print(result.stdout)
                    print("="*80 + "\n")

                # Parse text output to return violations (for error counting)
                return self._parse_text_output(result.stdout)

        except Exception as e:
            print(f"Error running PMD CPD: {e}")
            return []
        finally:
            # Clean up temporary exclude file list
            if exclude_file_list and exclude_file_list.exists():
                try:
                    exclude_file_list.unlink()
                except Exception as e:
                    print(f"Warning: Could not delete temporary exclude file: {e}")

    def _has_duplicates_in_csv(self, csv_content: str) -> bool:
        """Check if CSV output contains any duplicate code.

        Args:
            csv_content: CSV content as string

        Returns:
            True if duplicates found, False otherwise
        """
        if not csv_content or not csv_content.strip():
            return False

        lines = csv_content.strip().split('\n')
        # CSV has header + data rows. If only header exists, no duplicates
        return len(lines) > 1

    def _print_csv_statistics(self, csv_file: Path) -> None:
        """Print duplicate code statistics.

        Args:
            csv_file: Path to CSV output file
        """
        try:
            with open(csv_file, encoding='utf-8') as f:
                reader = csv.reader(f)

                # Skip header row
                next(reader, None)

                # Process data rows
                rows = list(reader)

            if not rows:
                print("\nNo duplicate code found.")
                return

            print("\n" + "="*80)
            print("DUPLICATE CODE DETECTION RESULTS")
            print("="*80)

            # Calculate total duplicate lines
            total_lines = 0
            for row in rows:
                # Extract first column (lines) for total calculation
                if row:  # Ensure row is not empty
                    with contextlib.suppress(ValueError, IndexError):
                        total_lines += int(row[0])

            # Print statistics
            print(f"Total CSV lines (duplicates found): {len(rows)}")
            print(f"Total duplicate code lines: {total_lines}")
            print("="*80 + "\n")

        except Exception as e:
            print(f"Error reading duplicate code statistics: {e}")

    def _parse_csv_output(self, csv_file: Path) -> list[Violation]:
        """Parse PMD CPD CSV output into violations.

        Args:
            csv_file: Path to CSV output file

        Returns:
            List of violations
        """
        violations = []

        try:
            with open(csv_file, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    lines = row.get('lines', 'N/A')
                    tokens = row.get('tokens', 'N/A')
                    occurrences = row.get('occurrences', 'N/A')

                    message = f"Duplicate code found: {lines} lines, {tokens} tokens, {occurrences} occurrences"

                    # Create violation (treating duplicates as warnings)
                    violation = Violation(
                        file_path='multiple files',
                        rule_name='pmd_duplicates',
                        severity=Severity.WARNING,
                        message=message
                    )
                    violations.append(violation)
        except Exception as e:
            print(f"Error parsing PMD CSV output: {e}")

        # Apply max_errors filter if specified
        if self.max_errors and len(violations) > self.max_errors:
            # Sort by lines (higher = worse) and take first N
            # Extract line count from message like "Duplicate code found: 45 lines..."
            def get_lines(v):
                try:
                    # Message format: "Duplicate code found: X lines..."
                    parts = v.message.split()
                    if len(parts) >= 4:
                        return int(parts[3])
                except Exception:
                    return 0

            violations.sort(key=get_lines, reverse=True)
            violations = violations[:self.max_errors]

        return violations

    def _parse_text_output(self, text_output: str) -> list[Violation]:
        """Parse PMD CPD text output into violations.

        Args:
            text_output: Text output from PMD

        Returns:
            List of violations
        """
        violations = []

        # Count duplicate blocks in text output
        # PMD text format shows duplicate blocks separated by "="
        if text_output and 'Found' in text_output:
            lines = text_output.strip().split('\n')
            for line in lines:
                if 'Found' in line and 'duplicate' in line.lower():
                    # Extract duplicate info from summary line
                    violation = Violation(
                        file_path='multiple files',
                        rule_name='pmd_duplicates',
                        severity=Severity.WARNING,
                        message=line.strip()
                    )
                    violations.append(violation)

        return violations
