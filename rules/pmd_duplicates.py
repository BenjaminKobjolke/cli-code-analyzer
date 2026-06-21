"""PMD duplicate code detection rule"""

import xml.etree.ElementTree as ET
from pathlib import Path

from models import RuleResult, Severity, Violation
from rules.pmd_base import PMDCpdRule, run_cpd


class PMDDuplicatesRule(PMDCpdRule):
    """Rule to detect duplicate code using PMD CPD"""

    rule_name = 'pmd_duplicates'

    def _run(self, _file_path: Path) -> RuleResult:
        prep = self._prepare_cpd("\nChecking for duplicate code...")
        if isinstance(prep, RuleResult):
            return prep
        return self._run_pmd_cpd(prep.pmd_path, prep.pmd_language, self.base_path, prep.minimum_tokens,
                                 prep.exclude_paths, prep.exclude_patterns, prep.filtered)

    def _run_pmd_cpd(self, pmd_path: str, language: str, directory: Path, minimum_tokens: int,
                      exclude_paths: list[str], exclude_patterns: list[str],
                      filtered: list[Path] | None = None) -> RuleResult:
        """Execute PMD CPD and return a typed result (see pmd_base.run_cpd)."""
        cmd_base = [pmd_path, 'cpd', '-l', language, '-f', 'xml',
                    '--minimum-tokens', str(minimum_tokens), '--encoding', 'utf-8']
        return run_cpd(self, cmd_base, directory, exclude_paths, exclude_patterns, filtered)

    def _result_from_pmd_stdout(self, stdout: str) -> RuleResult:
        """Turn PMD CPD XML stdout into a RuleResult.

        Invariant guard: if the output clearly contains <duplication markers but
        none parse into violations, the result is NOT clean — it's a parser/schema
        mismatch (the exact failure mode of the original namespace bug). Surface it
        as FAILED instead of a false "no duplicates".
        """
        if not self._has_duplicates_in_xml(stdout):
            self.logger.info("No duplicate code found.")
            return self._ok([])

        violations = self._parse_xml_output(stdout)
        if not violations:
            return self._failed(
                "PMD reported duplications but none parsed — likely XML schema/namespace mismatch"
            )
        return self._ok(self._filter_violations_by_log_level(violations))

    def _has_duplicates_in_xml(self, xml_content: str) -> bool:
        """Check if XML output contains duplication elements."""
        if not xml_content or not xml_content.strip():
            return False
        return '<duplication' in xml_content

    def _parse_xml_output(self, xml_content: str) -> list[Violation]:
        """Parse PMD CPD XML output string into violations with actual file paths.

        Applies configured per-pair / per-file ``exceptions`` (see
        :meth:`_load_exceptions`): an occurrence is suppressed when an exception
        matches its file and — for pair-scoped exceptions — one of its partner
        files. Detection still runs for everything else, so a brand new
        duplication involving an excepted file is still reported.
        """
        violations: list[Violation] = []
        try:
            root = ET.fromstring(xml_content)
            # PMD 7.x emits a default namespace on the report; match tags
            # namespace-agnostically so findall does not silently return nothing.
            duplications = root.findall('{*}duplication')
        except ET.ParseError as e:
            self.logger.error(f"Error parsing PMD XML output: {e}")
            return violations
        except Exception as e:
            self.logger.error(f"Error parsing PMD XML output: {e}")
            return violations

        exceptions = self._load_exceptions()
        suppressed_reasons: list[str] = []
        # Each survivor: (lines, tokens, occurrences, [(rel_raw, line, [(other_raw, other_line)])])
        survivors: list[tuple] = []

        for dup in duplications:
            lines = dup.get('lines', 'N/A')
            tokens = dup.get('tokens', 'N/A')
            files = dup.findall('{*}file')
            occurrences = len(files)

            # (raw OS-sep path for display, forward-slash path for matching, line)
            rels = []
            for file_elem in files:
                raw = self._to_relative_raw(file_elem.get('path', 'unknown'))
                rels.append((raw, raw.replace('\\', '/'), int(file_elem.get('line', 0)) or None))

            emit = []
            for i, (raw, norm, line_num) in enumerate(rels):
                other_norms = [rels[j][1] for j in range(len(rels)) if j != i]
                exc = self._exception_for(norm, other_norms, exceptions)
                if exc is None:
                    others_display = [(rels[j][0], rels[j][2]) for j in range(len(rels)) if j != i]
                    emit.append((raw, line_num, others_display))
                else:
                    suppressed_reasons.append(exc['reason'])
            if emit:
                survivors.append((lines, tokens, occurrences, emit))

        if survivors:
            total_lines = sum(self._safe_int(s[0]) for s in survivors)
            self.logger.info(f"\n{'='*80}\nDUPLICATE CODE DETECTION RESULTS\n{'='*80}")
            self.logger.info(f"Total CSV lines (duplicates found): {len(survivors)}")
            self.logger.info(f"Total duplicate code lines: {total_lines}\n{'='*80}\n")

        if suppressed_reasons:
            unique = sorted(set(suppressed_reasons))
            self.logger.info(
                f"Suppressed {len(suppressed_reasons)} duplicate finding(s) via exceptions "
                f"({len(unique)} reason(s)):"
            )
            for reason in unique:
                self.logger.info(f"  - {reason}")

        for lines, tokens, occurrences, emit in survivors:
            for raw, line_num, others_display in emit:
                also_in = ', '.join(
                    f"{other_raw}:{other_line if other_line is not None else '?'}"
                    for other_raw, other_line in others_display
                )
                msg = f"Duplicate code found: {lines} lines, {tokens} tokens, {occurrences} occurrences — also in: {also_in}"
                violations.append(Violation(
                    file_path=raw,
                    rule_name='pmd_duplicates',
                    severity=Severity.WARNING,
                    message=msg,
                    line=line_num,
                ))

        if self.max_errors and len(violations) > self.max_errors:
            def get_lines(v):
                parts = v.message.split()
                return int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
            violations.sort(key=get_lines, reverse=True)
            violations = violations[:self.max_errors]

        return violations

    def _to_relative_raw(self, file_path_str: str) -> str:
        """Path relative to base_path (OS separators), or the input unchanged."""
        if self.base_path:
            try:
                return str(Path(file_path_str).relative_to(self.base_path))
            except (ValueError, TypeError):
                pass
        return str(file_path_str)

    @staticmethod
    def _safe_int(value) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def _load_exceptions(self) -> list[dict]:
        """Normalize the configured ``exceptions`` into matchable entries.

        Each entry yields ``{'file': <glob>, 'duplicate_of': [<glob>...],
        'reason': <str>}``. ``duplicate_of`` may be omitted (file-level
        suppression) or a string / list of globs (pair-scoped). Entries missing
        ``file`` or ``reason`` are dropped with a warning so suppression is never
        silent or undocumented.
        """
        raw = self.config.get('exceptions', [])
        if isinstance(raw, dict):
            raw = [{'file': k, **(v if isinstance(v, dict) else {})} for k, v in raw.items()]
        if not isinstance(raw, list):
            return []

        result: list[dict] = []
        for exc in raw:
            if not isinstance(exc, dict):
                continue
            file_pat = exc.get('file')
            reason = exc.get('reason')
            if not file_pat:
                self.logger.warning("pmd_duplicates exception ignored: missing 'file'")
                continue
            if not reason:
                self.logger.warning(
                    f"pmd_duplicates exception for '{file_pat}' ignored: missing 'reason'"
                )
                continue
            dup_of = exc.get('duplicate_of')
            if dup_of is None:
                dup_list = []
            elif isinstance(dup_of, str):
                dup_list = [dup_of]
            else:
                dup_list = [str(d) for d in dup_of]
            result.append({
                'file': file_pat.replace('\\', '/'),
                'duplicate_of': [d.replace('\\', '/') for d in dup_list],
                'reason': reason,
            })
        return result

    def _exception_for(self, rel_path: str, other_paths: list[str], exceptions: list[dict]) -> dict | None:
        """Return the first exception that suppresses this occurrence, else None.

        Matches both directions so a single pair-scoped entry silences both
        occurrences of an A<->B duplication.
        """
        if not exceptions:
            return None
        for exc in exceptions:
            file_pat = exc['file']
            dup_of = exc['duplicate_of']
            if self._path_matches(rel_path, file_pat) and (
                not dup_of or any(self._matches_any(o, dup_of) for o in other_paths)
            ):
                return exc
            if dup_of and self._matches_any(rel_path, dup_of) and any(
                self._path_matches(o, file_pat) for o in other_paths
            ):
                return exc
        return None

    def _matches_any(self, rel_path: str, patterns: list[str]) -> bool:
        return any(self._path_matches(rel_path, pattern) for pattern in patterns)

    def _path_matches(self, rel_path: str, pattern: str) -> bool:
        """Match a forward-slash relative path (or its basename) against a glob."""
        name = rel_path.rsplit('/', 1)[-1]
        return self._match_file_path(rel_path, pattern) or self._match_file_path(name, pattern)

