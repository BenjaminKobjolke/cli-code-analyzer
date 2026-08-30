#!/usr/bin/env python3
"""
Ruff Fixer - Auto-fix Python code issues using Ruff with settings from rules JSON
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

# Ruff rules whose autofix deletes imports. Its unused-import analysis is
# single-file, so it cannot see a name re-exported to another module or a
# `from .x import *` whose only job is registering side effects — removing
# either leaves the project importable but broken at runtime. Reported by the
# analyzer, never fixed by the fixer.
UNSAFE_FIX_RULES = ('F401', 'F403', 'F405', 'F811')

# Windows consoles default to cp1252; tool output can contain characters outside
# that codec, making bare print() raise UnicodeEncodeError. Force utf-8 with
# replacement so the fixer does not die on an un-encodable byte.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from logger import Logger  # noqa: E402
from path_utils import resolve_exclude_patterns  # noqa: E402
from settings import Settings  # noqa: E402


def load_ruff_config(rules_file: str, logger: Logger) -> dict:
    rules_path = Path(rules_file)
    if not rules_path.exists():
        logger.warning(f"Warning: Rules file not found: {rules_file}")
        return {}

    try:
        with open(rules_path, encoding='utf-8') as f:
            config = json.load(f)
        return config.get('ruff_analyze', {})
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing rules file: {e}")
        return {}


def get_ruff_path(logger: Logger) -> str | None:
    ruff_in_path = shutil.which('ruff')
    if ruff_in_path:
        return ruff_in_path

    script_dir = Path(__file__).parent
    venv_paths = [
        script_dir / 'venv' / 'Scripts' / 'ruff.exe',
        script_dir / 'venv' / 'bin' / 'ruff',
        script_dir / '.venv' / 'Scripts' / 'ruff.exe',
        script_dir / '.venv' / 'bin' / 'ruff',
    ]
    for venv_ruff in venv_paths:
        if venv_ruff.exists():
            return str(venv_ruff)

    settings = Settings(logger=logger)
    ruff_path = settings.get_path("ruff")
    if ruff_path and Path(ruff_path).exists():
        return ruff_path

    if sys.stdin.isatty():
        return settings.prompt_and_save("ruff")

    logger.error("Error: Ruff not found. Please install with: pip install ruff")
    return None


def build_fix_command(ruff_path: str, path: str, ruff_config: dict,
                      dry_run: bool = False,
                      languages: Sequence[str] = ('python',)) -> list[str]:
    """Assemble the `ruff check` command line for a fix (or --diff preview) run."""
    cmd = [ruff_path, 'check']
    cmd.append('--diff' if dry_run else '--fix')

    if ruff_config.get('select'):
        cmd.extend(['--select', ','.join(ruff_config['select'])])

    # Never let ruff delete imports: its unused-import fixes cannot see through
    # re-exports, so they silently break packages that import for side effects.
    ignore = list(ruff_config.get('ignore') or [])
    ignore += [rule for rule in UNSAFE_FIX_RULES if rule not in ignore]
    cmd.extend(['--ignore', ','.join(ignore)])

    for pattern in resolve_exclude_patterns(ruff_config.get('exclude_patterns'), languages):
        cmd.extend(['--exclude', pattern])

    cmd.append(path)
    return cmd


def parse_fixed_count(output: str) -> int:
    """Read how many issues ruff actually fixed (or, under --diff, would fix).

    A --fix run prints "Found 1025 errors (186 fixed, 839 remaining)." — the
    count that matters is the 186, not the 1025 it merely found. A --diff run
    reports "Would fix 146 errors" instead and never emits a "(N fixed" clause.
    """
    match = re.search(r'\((\d+) fixed', output) or re.search(r'Would fix (\d+) error', output)
    return int(match.group(1)) if match else 0


def run_ruff_fix(path: str, ruff_config: dict, logger: Logger, dry_run: bool = False) -> int:
    ruff_path = get_ruff_path(logger)
    if not ruff_path:
        logger.error("Error: Ruff executable not found")
        return -1

    cmd = build_fix_command(ruff_path, path, ruff_config, dry_run)

    logger.info(
        f"Not auto-fixing (import removal is unsafe): {', '.join(UNSAFE_FIX_RULES)}"
    )
    logger.info(f"Running: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            check=False,
        )

        # Forward the fixer's output through the logger (single off switch).
        if result.stdout:
            logger.info(result.stdout)
        if result.stderr:
            logger.error(result.stderr)

        return parse_fixed_count(result.stderr or result.stdout)

    except FileNotFoundError:
        logger.error(f"Error: Ruff executable not found: {ruff_path}")
        return -1
    except Exception as e:
        logger.error(f"Error running ruff: {e}")
        return -1


def main():
    parser = argparse.ArgumentParser(
        description='Auto-fix Python code issues using Ruff with settings from rules JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ruff_fixer.py --path .
  python ruff_fixer.py --path src/ --rules code_analysis_rules.json
  python ruff_fixer.py --path . --dry-run
        """,
    )

    parser.add_argument('--path', required=True, help='Path to the code directory or file to fix')
    parser.add_argument('--rules', default='code_analysis_rules.json', help='Path to the rules JSON file (default: code_analysis_rules.json)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without making changes')

    args = parser.parse_args()
    logger = Logger()

    if not Path(args.path).exists():
        logger.error(f"Error: Path '{args.path}' does not exist")
        sys.exit(1)

    ruff_config = load_ruff_config(args.rules, logger)

    if not ruff_config:
        logger.warning("Warning: No ruff_analyze configuration found in rules file")
        logger.info("Using default ruff settings\n")

    if args.dry_run:
        logger.info("=== DRY RUN MODE - No changes will be made ===\n")

    result = run_ruff_fix(args.path, ruff_config, logger, args.dry_run)

    if result < 0:
        sys.exit(1)
    elif result == 0:
        logger.info("\nNothing auto-fixable — run the analyzer to see what remains.")
    elif args.dry_run:
        logger.info(f"\n{result} issue(s) would be fixed")
    else:
        logger.info(f"\nFixed {result} issue(s)")

    sys.exit(0)


if __name__ == '__main__':
    main()
