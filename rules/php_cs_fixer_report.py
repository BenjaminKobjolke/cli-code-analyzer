"""Parsing and CSV reporting for PHP-CS-Fixer JSON output.

Split out of php_cs_fixer_analyze.py to keep that module focused on config
generation and execution. Functions take a ``get_relative_path`` callable (the
rule's ``_get_relative_path``) and a ``logger`` rather than depending on the rule.
"""

import csv
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from logger import Logger
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


def report_fixer_output(
    json_content: str,
    get_relative_path: Callable[[Path], str],
    logger: Logger,
    filter_violations: Callable[[list[Violation]], list[Violation]],
    max_errors: int | None,
    output_folder: Path | None,
) -> list[Violation]:
    """Parse, filter, limit, and report PHP-CS-Fixer findings."""
    violations = filter_violations(parse_fixer_json(json_content, get_relative_path, logger))
    if max_errors and len(violations) > max_errors:
        violations = violations[:max_errors]

    if violations:
        logger.info(f"PHP-CS-Fixer found {len(violations)} issue(s)")
    else:
        logger.info("PHP-CS-Fixer: No issues found")

    if output_folder and violations:
        output_file = output_folder / 'php_cs_fixer.csv'
        write_fixer_csv(output_file, json_content, max_errors, get_relative_path, logger)

    return violations


def run_fixer_commands(
    commands: list[list[str]],
    run_subprocess: Callable[[list[str], Path], subprocess.CompletedProcess[str]],
    cwd: Path,
    filter_files: bool,
    logger: Logger,
) -> str:
    """Run scoped fixer commands and combine their JSON output when needed."""
    outputs = []
    scoped_files = []
    for command in commands:
        result = run_subprocess(command, cwd)
        output = result.stdout or ''
        outputs.append(output)

        if result.stderr and 'legend:' not in result.stderr.lower():
            stderr_lines = [
                line for line in result.stderr.strip().split('\n')
                if line.strip() and 'legend:' not in line.lower() and line.strip() != '.'
            ]
            for line in stderr_lines[:5]:
                logger.info(f"  {line}")

        if filter_files:
            if not output.strip():
                raise ValueError('PHP-CS-Fixer returned empty JSON output')
            data = json.loads(output)
            if not isinstance(data, dict) or not isinstance(data.get('files'), list):
                raise ValueError('PHP-CS-Fixer returned unexpected JSON structure')
            scoped_files.extend(data['files'])

    return json.dumps({'files': scoped_files}) if filter_files else outputs[0]
