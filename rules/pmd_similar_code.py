"""PMD similar code detection rule"""

import xml.etree.ElementTree as ET
from pathlib import Path

from models import RuleResult, Severity, Violation
from rules.pmd_base import PMDCpdRule, run_cpd


class PMDSimilarCodeRule(PMDCpdRule):
    """Rule to detect structurally similar code using PMD CPD with identifier/literal normalization"""

    rule_name = 'pmd_similar_code'

    def _run(self, _file_path: Path) -> RuleResult:
        prep = self._prepare_cpd("\nChecking for similar code patterns...")
        if isinstance(prep, RuleResult):
            return prep
        return self._run_pmd_cpd(prep.pmd_path, prep.pmd_language, self.base_path, prep.minimum_tokens,
                                 prep.exclude_paths, prep.exclude_patterns,
                                 self.config.get('ignore_identifiers', True),
                                 self.config.get('ignore_literals', True),
                                 self.config.get('ignore_annotations', False),
                                 prep.filtered)

    def _run_pmd_cpd(self, pmd_path: str, language: str, directory: Path, minimum_tokens: int,
                      exclude_paths: list[str], exclude_patterns: list[str],
                      ignore_identifiers: bool, ignore_literals: bool, ignore_annotations: bool,
                      filtered: list[Path] | None = None) -> RuleResult:
        """Execute PMD CPD with similarity flags and return a typed result (see pmd_base.run_cpd)."""
        cmd_base = [pmd_path, 'cpd', '-l', language, '-f', 'xml',
                    '--minimum-tokens', str(minimum_tokens), '--encoding', 'utf-8']
        if ignore_identifiers:
            cmd_base.append('--ignore-identifiers')
        if ignore_literals:
            cmd_base.append('--ignore-literals')
        if ignore_annotations:
            cmd_base.append('--ignore-annotations')
        return run_cpd(self, cmd_base, directory, exclude_paths, exclude_patterns, filtered)

    def _result_from_pmd_stdout(self, stdout: str) -> RuleResult:
        """Turn PMD CPD XML stdout into a RuleResult, guarding the parse invariant.

        If the output contains <duplication markers but none parse, that is a
        parser/schema mismatch (FAILED), not a clean "no similar code".
        """
        if not self._has_results_in_xml(stdout):
            self.logger.info("No similar code patterns found.")
            return self._ok([])
        violations = self._parse_xml_output(stdout)
        if not violations:
            return self._failed(
                "PMD reported similar code but none parsed — likely XML schema/namespace mismatch"
            )
        return self._ok(self._filter_violations_by_log_level(violations))

    def _has_results_in_xml(self, xml_content: str) -> bool:
        """Check if XML output contains duplication elements."""
        if not xml_content or not xml_content.strip():
            return False
        return '<duplication' in xml_content

    def _parse_xml_output(self, xml_content: str) -> list[Violation]:
        """Parse PMD CPD XML output string into violations with actual file paths."""
        violations = []
        try:
            root = ET.fromstring(xml_content)
            # PMD 7.x emits a default namespace; match namespace-agnostically.
            duplications = root.findall('{*}duplication')

            if duplications:
                total_lines = sum(int(d.get('lines', 0)) for d in duplications)
                self.logger.info(f"\n{'='*80}\nSIMILAR CODE DETECTION RESULTS\n{'='*80}")
                self.logger.info(f"Total similar pattern groups found: {len(duplications)}")
                self.logger.info(f"Total similar code lines: {total_lines}\n{'='*80}\n")

            for dup in duplications:
                lines = dup.get('lines', 'N/A')
                tokens = dup.get('tokens', 'N/A')
                files = dup.findall('{*}file')
                occurrences = len(files)

                for i, file_elem in enumerate(files):
                    file_path = file_elem.get('path', 'unknown')
                    line_num = int(file_elem.get('line', 0)) or None

                    # Make path relative to base_path
                    try:
                        rel_path = str(Path(file_path).relative_to(self.base_path))
                    except ValueError:
                        rel_path = file_path

                    # Build list of other files in this duplication
                    other_files = []
                    for j, other in enumerate(files):
                        if i != j:
                            other_path = other.get('path', 'unknown')
                            other_line = other.get('line', '?')
                            try:
                                other_rel = str(Path(other_path).relative_to(self.base_path))
                            except ValueError:
                                other_rel = other_path
                            other_files.append(f"{other_rel}:{other_line}")

                    also_in = ', '.join(other_files)
                    msg = f"Similar code found: {lines} lines, {tokens} tokens, {occurrences} occurrences — also in: {also_in}"
                    violations.append(Violation(
                        file_path=rel_path,
                        rule_name='pmd_similar_code',
                        severity=Severity.WARNING,
                        message=msg,
                        line=line_num,
                    ))
        except ET.ParseError as e:
            self.logger.error(f"Error parsing PMD XML output: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing PMD XML output: {e}")

        if self.max_errors and len(violations) > self.max_errors:
            def get_lines(v):
                parts = v.message.split()
                return int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
            violations.sort(key=get_lines, reverse=True)
            violations = violations[:self.max_errors]

        return violations
