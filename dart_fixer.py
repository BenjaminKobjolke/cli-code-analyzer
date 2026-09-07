#!/usr/bin/env python3
"""Dart Fixer - Auto-fix Dart/Flutter lint issues using `dart fix --apply`.

`dart fix` applies the fixes for every lint enabled in the project's
analysis_options.yaml, so no rule config is read from the rules JSON; the
`--rules` flag is accepted only so every fix_issues.bat shares one call shape.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Windows consoles default to cp1252; tool output can contain characters outside
# that codec, making bare print() raise UnicodeEncodeError. Force utf-8 with
# replacement so the fixer does not die on an un-encodable byte.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from logger import Logger  # noqa: E402
from settings import Settings  # noqa: E402

# "2 fixes made in 1 file." (apply) / "3 proposed fixes in 2 files." (dry run)
_FIX_COUNT = re.compile(r'(\d+)\s+(?:proposed\s+)?fix(?:es)?(?:\s+made)?\s+in\s+\d+\s+files?', re.IGNORECASE)


def parse_fixed_count(output: str) -> int:
    """Return the number of fixes `dart fix` reports; 0 for "Nothing to fix!"."""
    match = _FIX_COUNT.search(output)
    return int(match.group(1)) if match else 0


def find_project_root(path: str) -> Path:
    """Walk up from [path] to the folder holding pubspec.yaml (falls back to path)."""
    base = Path(path).resolve()
    if base.is_file():
        base = base.parent
    for candidate in (base, *base.parents):
        if (candidate / 'pubspec.yaml').exists():
            return candidate
    return base


def get_dart_command(project_root: Path, logger: Logger) -> list[str] | None:
    """Mirror BaseRule._get_dart_command: FVM prefix when the project pins one."""
    fvm = shutil.which('fvm')
    if fvm and ((project_root / '.fvmrc').exists() or (project_root / '.fvm').is_dir()):
        # Resolved path: on Windows fvm is a .bat, which subprocess cannot start by bare name.
        return [fvm, 'dart']

    dart_in_path = shutil.which('dart')
    if dart_in_path:
        return [dart_in_path]

    settings = Settings(logger=logger)
    dart_path = settings.get_path('dart')
    if dart_path and Path(dart_path).exists():
        return [dart_path]

    if sys.stdin.isatty():
        prompted = settings.prompt_and_save('dart')
        return [prompted] if prompted else None

    logger.error("Error: dart executable not found. Install the Flutter/Dart SDK or set dart_path in settings.ini")
    return None


def run_dart_fix(path: str, logger: Logger, dry_run: bool = False) -> int:
    project_root = find_project_root(path)
    dart_cmd = get_dart_command(project_root, logger)
    if not dart_cmd:
        return -1

    cmd = [*dart_cmd, 'fix', '--dry-run' if dry_run else '--apply', str(Path(path).resolve())]
    logger.info(f"Running: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            check=False,
            cwd=project_root,
        )
    except FileNotFoundError:
        logger.error(f"Error: dart executable not found: {dart_cmd[0]}")
        return -1
    except Exception as e:
        logger.error(f"Error running dart fix: {e}")
        return -1

    if result.stdout:
        logger.info(result.stdout)
    if result.stderr:
        logger.error(result.stderr)
    if result.returncode != 0:
        logger.error(f"dart fix exited with code {result.returncode}")
        return -1

    return parse_fixed_count(result.stdout or '')


def main():
    parser = argparse.ArgumentParser(
        description='Auto-fix Dart/Flutter lint issues using dart fix',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dart_fixer.py --path .
  python dart_fixer.py --path lib/ --rules code_analysis_rules.json
  python dart_fixer.py --path . --dry-run
        """,
    )

    parser.add_argument('--path', required=True, help='Path to the code directory or file to fix')
    parser.add_argument('--rules', default='code_analysis_rules.json',
                        help='Accepted for bat-file symmetry; dart fix reads analysis_options.yaml instead')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without making changes')

    args = parser.parse_args()
    logger = Logger()

    if not Path(args.path).exists():
        logger.error(f"Error: Path '{args.path}' does not exist")
        sys.exit(1)

    if args.dry_run:
        logger.info("=== DRY RUN MODE - No changes will be made ===\n")

    result = run_dart_fix(args.path, logger, args.dry_run)

    if result < 0:
        sys.exit(1)
    elif result == 0:
        logger.info("\nNo issues to fix!")
    elif args.dry_run:
        logger.info(f"\n{result} fix(es) would be applied")
    else:
        logger.info(f"\nApplied {result} fix(es)")

    sys.exit(0)


if __name__ == '__main__':
    main()
