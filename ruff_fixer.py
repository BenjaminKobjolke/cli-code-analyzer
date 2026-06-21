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
from pathlib import Path

from logger import Logger
from settings import Settings


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


def run_ruff_fix(path: str, ruff_config: dict, logger: Logger, dry_run: bool = False) -> int:
    ruff_path = get_ruff_path(logger)
    if not ruff_path:
        logger.error("Error: Ruff executable not found")
        return -1

    cmd = [ruff_path, 'check']
    cmd.append('--diff' if dry_run else '--fix')

    if ruff_config.get('select'):
        cmd.extend(['--select', ','.join(ruff_config['select'])])
    if ruff_config.get('ignore'):
        cmd.extend(['--ignore', ','.join(ruff_config['ignore'])])
    if ruff_config.get('exclude_patterns'):
        for pattern in ruff_config['exclude_patterns']:
            cmd.extend(['--exclude', pattern])

    cmd.append(path)

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

        output = result.stderr or result.stdout
        if 'Found' in output and 'error' in output:
            match = re.search(r'Found (\d+) errors?', output)
            if match:
                return int(match.group(1))

        return 0

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
        logger.info("\nNo issues to fix!")
    elif args.dry_run:
        logger.info(f"\n{result} issue(s) would be fixed")
    else:
        logger.info(f"\nFixed {result} issue(s)")

    sys.exit(0)


if __name__ == '__main__':
    main()
