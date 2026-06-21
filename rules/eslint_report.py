"""Parsing and CSV reporting for ESLint JSON output.

Split out of eslint_analyze.py to keep that module focused on command building
and execution. The functions take a ``get_relative_path`` callable (the rule's
``_get_relative_path``) and a ``logger`` rather than depending on the rule.
"""

import csv
import json
from pathlib import Path

from models import LogLevel, Severity, Violation


def map_eslint_severity(severity: int) -> Severity:
    """Map ESLint severity (2=error, 1=warning) to internal Severity."""
    if severity == 2:
        return Severity.ERROR
    if severity == 1:
        return Severity.WARNING
    return Severity.INFO


def parse_eslint_json(output: str, get_relative_path, logger) -> list[Violation]:
    """Parse ESLint --format json output into violations."""
    violations: list[Violation] = []
    if not output or not output.strip():
        return violations

    try:
        data = json.loads(output)
        for file_result in data:
            file_path = file_result.get('filePath', 'unknown')
            for message in file_result.get('messages', []):
                rule_id = message.get('ruleId', 'unknown')
                msg = message.get('message', '')
                line_num = message.get('line', 0)
                col_num = message.get('column', 0)
                severity = map_eslint_severity(message.get('severity', 1))
                try:
                    rel_path = get_relative_path(Path(file_path))
                except Exception:
                    rel_path = file_path
                violations.append(Violation(
                    file_path=rel_path,
                    rule_name='eslint_analyze',
                    severity=severity,
                    message=f"{msg} ({rule_id}) at line {line_num}, column {col_num}",
                    line=line_num,
                    column=col_num,
                ))
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing eslint JSON output: {e}")
        logger.error(f"Output was: {output[:200]}...")
    except Exception as e:
        logger.error(f"Error processing eslint results: {e}")

    return violations


def write_eslint_csv(output_file: Path, json_content: str, log_level: LogLevel,
                     max_errors: int | None, get_relative_path, logger) -> None:
    """Write ESLint results to CSV, filtered by log level and limited by max_errors."""
    try:
        data = json.loads(json_content)
        if not data:
            return

        filtered_messages = []
        for file_result in data:
            file_path = file_result.get('filePath', 'unknown')
            for message in file_result.get('messages', []):
                severity = map_eslint_severity(message.get('severity', 1))
                if (log_level == LogLevel.ERROR and severity != Severity.ERROR) or \
                   (log_level == LogLevel.WARNING and severity not in (Severity.ERROR, Severity.WARNING)):
                    continue
                filtered_messages.append({'file_path': file_path, 'message': message, 'severity': severity})

        if max_errors and len(filtered_messages) > max_errors:
            severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
            filtered_messages.sort(key=lambda m: severity_order.get(m['severity'], 3))
            filtered_messages = filtered_messages[:max_errors]

        if not filtered_messages:
            return

        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['file', 'line', 'column', 'severity', 'rule', 'message'])
            for item in filtered_messages:
                message = item['message']
                try:
                    rel_path = get_relative_path(Path(item['file_path']))
                except Exception:
                    rel_path = item['file_path']
                writer.writerow([
                    rel_path, message.get('line', 0), message.get('column', 0),
                    item['severity'].value, message.get('ruleId', 'unknown'), message.get('message', ''),
                ])

        logger.info(f"ESLint report saved to: {output_file}")

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON for CSV output: {e}")
    except Exception as e:
        logger.error(f"Error writing eslint CSV file: {e}")
