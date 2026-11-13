"""Parsing and CSV reporting for PHP-CS-Fixer JSON output.

Split out of php_cs_fixer_analyze.py to keep that module focused on config
generation and execution. Functions take a ``get_relative_path`` callable (the
rule's ``_get_relative_path``) and a ``logger`` rather than depending on the rule.
"""

import csv
import json
from pathlib import Path

from models import Severity, Violation


def drop_fixer_from_json(output: str, fixer: str) -> str:
    """Remove one fixer from every file's appliedFixers (files left without fixers drop out).

    Output that is not the expected JSON is returned unchanged so the parser reports it.
    """
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return output
    if not isinstance(data, dict) or not isinstance(data.get('files'), list):
        return output
    files = []
    for file_info in data['files']:
        fixers = [name for name in file_info.get('appliedFixers', []) if name != fixer]
        if fixers:
            files.append({**file_info, 'appliedFixers': fixers})
    return json.dumps({**data, 'files': files})


def parse_fixer_json(output: str, get_relative_path, logger) -> list[Violation]:
    """Parse PHP-CS-Fixer JSON into one violation per file (listing the fixers)."""
    violations: list[Violation] = []
    if not output or not output.strip():
        return violations

    try:
        data = json.loads(output)
        for file_info in data.get('files', []):
            fixers = file_info.get('appliedFixers', [])
            if not fixers:
                continue
            try:
                rel_path = get_relative_path(Path(file_info.get('name', 'unknown')))
            except Exception:
                rel_path = file_info.get('name', 'unknown')
            violations.append(Violation(
                file_path=rel_path,
                rule_name='php_cs_fixer',
                severity=Severity.WARNING,
                message=f"Code style issues found. Would apply fixers: {', '.join(fixers)}",
            ))
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing PHP-CS-Fixer JSON output: {e}")
        logger.error(f"Output was: {output[:200]}...")
    except Exception as e:
        logger.error(f"Error processing PHP-CS-Fixer results: {e}")

    return violations


def write_fixer_csv(output_file: Path, json_content: str, max_errors: int | None,
                    get_relative_path, logger) -> None:
    """Write PHP-CS-Fixer results to CSV (one row per file with its fixers)."""
    try:
        data = json.loads(json_content)
        rows = []
        for file_info in data.get('files', []):
            fixers = file_info.get('appliedFixers', [])
            if not fixers:
                continue
            try:
                rel_path = get_relative_path(Path(file_info.get('name', 'unknown')))
            except Exception:
                rel_path = file_info.get('name', 'unknown')
            rows.append({'file': rel_path, 'severity': 'warning',
                         'fixers': ', '.join(fixers), 'fixer_count': len(fixers)})

        if max_errors and len(rows) > max_errors:
            rows = rows[:max_errors]
        if not rows:
            return

        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['file', 'severity', 'fixers', 'fixer_count'])
            for v in rows:
                writer.writerow([v['file'], v['severity'], v['fixers'], v['fixer_count']])

        logger.info(f"PHP-CS-Fixer report saved to: {output_file}")

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON for CSV output: {e}")
    except Exception as e:
        logger.error(f"Error writing PHP-CS-Fixer CSV file: {e}")
