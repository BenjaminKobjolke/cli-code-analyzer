"""File and JSON output for the analyzer report.

Console formatting stays in `reporter.py`; this module owns the CSV files
written to the output folder and the JSON document printed to stdout.
"""
import csv
from collections import defaultdict
from pathlib import Path

from logger import Logger
from models import RuleResult, Severity, Violation

CSV_FILENAME_MAP = {
    'pmd_duplicates': 'duplicate_code.csv',
    'pmd_similar_code': 'similar_code.csv',
    'php_cs_fixer_analyze': 'php_cs_fixer.csv',
}

SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def parse_threshold(message: str) -> int:
    """Extract the threshold integer from a message like '... (limit: 500)'."""
    try:
        if "limit:" in message:
            return int(float(message.split("limit:")[-1].strip().rstrip(")")))
        if "warning:" in message:
            return int(float(message.split("warning:")[-1].strip().rstrip(")")))
    except (ValueError, TypeError):
        pass
    return 0


def _limit_by_severity(violations: list[Violation], max_errors: int | None) -> list[Violation]:
    sorted_v = sorted(violations, key=lambda v: SEVERITY_ORDER.get(v.severity, 3))
    if max_errors and len(sorted_v) > max_errors:
        return sorted_v[:max_errors]
    return sorted_v


def _limit_line_violations(violations: list[Violation], max_errors: int | None) -> list[Violation]:
    """Sort line-count violations by severity then by descending line count."""
    if not max_errors or len(violations) <= max_errors:
        return violations

    def key(v: Violation):
        value = v.line_count if v.line_count else 0
        return (SEVERITY_ORDER.get(v.severity, 999), -value)

    return sorted(violations, key=key)[:max_errors]


def write_csv_reports(violations: list[Violation], output_folder: Path,
                      max_errors: int | None, logger: Logger) -> bool:
    """Write the line-count CSV plus one CSV per rule. Returns True if any ERROR."""
    line_violations = _limit_line_violations(
        [v for v in violations if v.rule_name == 'max_lines_per_file'], max_errors)
    if line_violations:
        output_file = output_folder / 'line_count_report.csv'
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['file_path', 'line_count', 'threshold', 'severity'])
            for v in line_violations:
                writer.writerow([v.file_path, v.line_count, parse_threshold(v.message), v.severity.value])
        logger.info(f"Line count report saved to: {output_file}")
    else:
        logger.info("No line count violations found")

    by_rule: dict[str, list[Violation]] = defaultdict(list)
    for v in violations:
        if v.rule_name != 'max_lines_per_file':
            by_rule[v.rule_name].append(v)

    for rule_name, rule_violations in by_rule.items():
        output_file = output_folder / CSV_FILENAME_MAP.get(rule_name, f'{rule_name}.csv')
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['file_path', 'line', 'column', 'severity', 'message'])
            for v in _limit_by_severity(rule_violations, max_errors):
                writer.writerow([v.file_path, v.line or '', v.column or '', v.severity.value, v.message])
        logger.info(f"Report saved to: {output_file}")

    return any(v.severity == Severity.ERROR for v in violations)


def build_json(violations: list[Violation], failures: list[RuleResult]) -> dict:
    """Build the JSON document describing violations and tool failures."""
    counts = {sev: 0 for sev in Severity}
    violation_dicts = []
    for v in violations:
        counts[v.severity] += 1
        d = {
            "file_path": v.file_path,
            "rule_name": v.rule_name,
            "severity": v.severity.value,
            "message": v.message,
        }
        if v.line is not None:
            d["line"] = v.line
        if v.column is not None:
            d["column"] = v.column
        if v.line_count is not None:
            d["line_count"] = v.line_count
        violation_dicts.append(d)

    return {
        "violations": violation_dicts,
        "failures": [{"rule_name": f.rule_name, "message": f.message} for f in failures],
        "summary": {
            "total": len(violations),
            "errors": counts[Severity.ERROR],
            "warnings": counts[Severity.WARNING],
            "infos": counts[Severity.INFO],
            "failures": len(failures),
        },
    }
