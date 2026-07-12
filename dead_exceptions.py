"""Dead-exception scanner for the rules JSON.

An "exception" in the rules file raises a metric threshold for a specific `file`
(and, by convention, documents a `function`). When code is refactored the target
file can be deleted or a documented function renamed/moved, leaving the exception
**inert**: the analyzer matches exceptions on file path only, so a dead entry
suppresses nothing and just rots as cruft. Because a non-matching exception
suppresses nothing, removing a dead entry cannot change the analyzer's pass/fail
— it is a pure, safe cleanup.

This module finds such entries (`run_dead_exceptions`) and optionally prunes them
(`--fix`). Scanned exception arrays:

  - ``max_lines_per_file.exceptions[]``          (has ``file``)
  - ``pmd_duplicates.exceptions[]``              (has ``files`` and/or ``file`` / ``duplicate_of``)
  - ``dart_code_linter.metrics.<metric>.exceptions[]``  (has ``file`` + optional ``function``)
"""

import json
import re
from pathlib import Path

from config import Config
from logger import Logger
from models import Severity, Violation
from report_files import write_csv_reports

_GLOB_CHARS = set('*?[')


def _is_glob(value: str) -> bool:
    """A glob-valued file ref can't be judged dead by existence — treat as live."""
    return any(c in _GLOB_CHARS for c in value)


def _resolve(base_path: Path, rel: str) -> Path | None:
    """First existing on-disk path for a rules-relative file, or None.

    Tries the path as-is, then under ``lib/`` and ``test/`` (the common
    Flutter/Dart layouts where exception paths are recorded lib-relative).
    """
    for cand in (rel, f'lib/{rel}', f'test/{rel}'):
        p = base_path / cand
        if p.exists():
            return p
    return None


def _candidate_files(entry: dict) -> list[str]:
    """All file references an exception entry points at (any shape)."""
    refs: list[str] = []
    f = entry.get('file')
    if isinstance(f, str):
        refs.append(f)
    files = entry.get('files')
    if isinstance(files, list):
        refs.extend(x for x in files if isinstance(x, str))
    dup = entry.get('duplicate_of')
    if isinstance(dup, str):
        refs.append(dup)
    elif isinstance(dup, list):
        refs.extend(x for x in dup if isinstance(x, str))
    return refs


def _function_names(function_field: str) -> list[str]:
    """Identifiers to look for in the file for a `function` field.

    Handles the ``"ClassA.methodA / ClassB.methodB"`` multi-name form: split on
    ``/``, take the last dotted segment of each, strip any parenthesised args.
    """
    names = []
    for part in re.split(r'\s*/\s*', function_field):
        name = part.split('.')[-1].split('(')[0].strip()
        if name:
            names.append(name)
    return names


def _function_present(path: Path, function_field: str) -> bool:
    try:
        src = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return False
    return all(
        re.search(r'\b' + re.escape(name) + r'\b', src)
        for name in _function_names(function_field)
    )


def _primary_file(entry: dict) -> str:
    """Human-facing file label for an entry (for reports)."""
    refs = _candidate_files(entry)
    return ', '.join(refs) if refs else '?'


def _exception_lists(rules: dict):
    """Yield (label, list_obj) for every exceptions array we scan.

    The yielded list objects are the live containers inside ``rules`` — mutating
    them in place (``--fix``) is reflected when ``rules`` is re-serialized.
    """
    mlp = rules.get('max_lines_per_file', {})
    if isinstance(mlp, dict) and isinstance(mlp.get('exceptions'), list):
        yield ('max_lines_per_file', mlp['exceptions'])

    pmd = rules.get('pmd_duplicates', {})
    if isinstance(pmd, dict) and isinstance(pmd.get('exceptions'), list):
        yield ('pmd_duplicates', pmd['exceptions'])

    metrics = rules.get('dart_code_linter', {}).get('metrics', {})
    if isinstance(metrics, dict):
        for metric_id, metric in metrics.items():
            if isinstance(metric, dict) and isinstance(metric.get('exceptions'), list):
                yield (f'dart_code_linter/{metric_id}', metric['exceptions'])


def find_dead_exceptions(rules: dict, base_path: Path):
    """Return a list of (label, list_obj, entry, reason) for each dead exception."""
    dead = []
    for label, lst in _exception_lists(rules):
        for entry in lst:
            if not isinstance(entry, dict):
                continue
            checkable = [r for r in _candidate_files(entry) if not _is_glob(r)]
            missing = [r for r in checkable if _resolve(base_path, r) is None]
            if missing:
                dead.append((label, lst, entry,
                             f"file(s) no longer exist: {', '.join(missing)}"))
                continue
            fn = entry.get('function')
            if isinstance(fn, str) and fn:
                target = next((_resolve(base_path, r) for r in checkable
                               if _resolve(base_path, r)), None)
                if target and not _function_present(target, fn):
                    dead.append((label, lst, entry,
                                 f"function absent from {_primary_file(entry)}: {fn}"))
    return dead


def _apply_fix(rules_file: str, rules: dict, dead) -> int:
    """Remove dead entries by identity, then rewrite the rules JSON."""
    drop: dict[int, tuple] = {}
    for (_label, lst, entry, _reason) in dead:
        _lst, ids = drop.setdefault(id(lst), (lst, set()))
        ids.add(id(entry))
    removed = 0
    for lst, ids in drop.values():
        keep = [x for x in lst if id(x) not in ids]
        removed += len(lst) - len(keep)
        lst[:] = keep  # mutate in place so `rules` reflects the removal
    with open(rules_file, 'w', encoding='utf-8') as f:
        json.dump(rules, f, indent=2, ensure_ascii=True)
        f.write('\n')
    return removed


def run_dead_exceptions(rules_file: str, path: str | None,
                        output: str | None = None, fix: bool = False,
                        logger: Logger | None = None) -> int:
    """Scan for dead exceptions. Returns exit code (1 if any found, else 0)."""
    logger = logger or Logger()
    base_path = Path(path or '.').resolve()
    rules = Config(rules_file, logger=logger).rules
    dead = find_dead_exceptions(rules, base_path)

    violations = [
        Violation(file_path=_primary_file(entry), rule_name='dead_exception',
                  severity=Severity.WARNING, message=f"[{label}] {reason}")
        for (label, _lst, entry, reason) in dead
    ]

    if output:
        out = Path(output)
        out.mkdir(parents=True, exist_ok=True)
        write_csv_reports(violations, out, None, logger)
    elif not dead:
        logger.info("No dead exceptions found.")
    else:
        logger.info(f"Found {len(dead)} dead exception(s):")
        for (label, _lst, entry, reason) in dead:
            logger.info(f"  [{label}] {_primary_file(entry)} — {reason}")

    if fix and dead:
        removed = _apply_fix(rules_file, rules, dead)
        logger.info(f"Removed {removed} dead exception(s) from {rules_file}")

    return 1 if dead else 0


def demo() -> None:
    """Self-check: file-missing, function-missing, multi-name, and live non-flags."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        (base / 'lib').mkdir()
        (base / 'lib' / 'live.dart').write_text('class A { void keepMe() {} }',
                                                 encoding='utf-8')
        rules = {
            'max_lines_per_file': {'exceptions': [
                {'file': 'lib/live.dart'},                # live
                {'file': 'lib/gone.dart'},                # dead: file missing
                {'file': '*.g.dart'},                     # glob → never dead
            ]},
            'pmd_duplicates': {'exceptions': [
                {'files': ['lib/live.dart', 'lib/gone.dart']},  # dead: one gone
                {'files': ['lib/live.dart']},                    # live
            ]},
            'dart_code_linter': {'metrics': {
                'cyclomatic-complexity': {'exceptions': [
                    {'file': 'live.dart', 'function': 'A.keepMe'},          # live
                    {'file': 'live.dart', 'function': 'A.removedMe'},       # dead: fn gone
                    {'file': 'live.dart', 'function': 'A.keepMe / A.nope'}, # dead: one name gone
                ]},
            }},
        }
        dead = find_dead_exceptions(rules, base)
        reasons = [r for (_l, _lst, _e, r) in dead]
        assert len(dead) == 4, f"expected 4 dead, got {len(dead)}: {reasons}"
        assert any('gone.dart' in r for r in reasons)
        assert any('removedMe' in r for r in reasons)
        assert any('nope' in r for r in reasons)

        rf = base / 'rules.json'
        rf.write_text(json.dumps(rules), encoding='utf-8')
        rules2 = json.loads(rf.read_text(encoding='utf-8'))
        removed = _apply_fix(str(rf), rules2, find_dead_exceptions(rules2, base))
        assert removed == 4, removed
        remaining = find_dead_exceptions(json.loads(rf.read_text(encoding='utf-8')), base)
        assert remaining == [], f"still dead after fix: {remaining}"
        print("dead_exceptions self-check: OK")


if __name__ == '__main__':
    demo()
