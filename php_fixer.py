#!/usr/bin/env python3
"""PHP Fixer - Auto-fix PHP code style issues using PHP-CS-Fixer with settings from rules JSON"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from logger import Logger
from settings import Settings


def load_php_cs_fixer_config(rules_file: str, logger: Logger) -> dict:
    rules_path = Path(rules_file)
    if not rules_path.exists():
        logger.warning(f"Warning: Rules file not found: {rules_file}")
        return {}

    try:
        with open(rules_path, encoding='utf-8') as f:
            config = json.load(f)
        return config.get('php_cs_fixer', {})
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing rules file: {e}")
        return {}


def get_php_cs_fixer_path(logger: Logger) -> str | None:
    script_dir = Path(__file__).parent
    bundled_paths = [
        script_dir / 'php' / 'vendor' / 'bin' / 'php-cs-fixer.bat',
        script_dir / 'php' / 'vendor' / 'bin' / 'php-cs-fixer',
    ]
    for bundled_fixer in bundled_paths:
        if bundled_fixer.exists():
            return str(bundled_fixer)

    fixer_in_path = shutil.which('php-cs-fixer')
    if fixer_in_path:
        return fixer_in_path

    vendor_paths = [
        script_dir / 'vendor' / 'bin' / 'php-cs-fixer',
        script_dir / 'vendor' / 'bin' / 'php-cs-fixer.bat',
    ]
    for vendor_fixer in vendor_paths:
        if vendor_fixer.exists():
            return str(vendor_fixer)

    settings = Settings(logger=logger)
    fixer_path = settings.get_php_cs_fixer_path()
    if fixer_path and Path(fixer_path).exists():
        return fixer_path

    if sys.stdin.isatty():
        return settings.prompt_and_save_php_cs_fixer_path()

    logger.error("Error: PHP-CS-Fixer not found. Please install with: composer require --dev friendsofphp/php-cs-fixer")
    return None


def find_fixer_config(path: str) -> Path | None:
    """Locate a PHP-CS-Fixer config in the target path so its Finder excludes
    (e.g. cache, vendor) are honored. Without a config the fixer only sees
    --rules and would rewrite every file under the path, including excluded
    dirs."""
    base = Path(path)
    if base.is_file():
        base = base.parent
    for config_name in ('.php-cs-fixer.dist.php', '.php-cs-fixer.php'):
        candidate = base / config_name
        if candidate.exists():
            return candidate
    return None


def run_php_cs_fixer(path: str, fixer_config: dict, logger: Logger, dry_run: bool = False) -> int:
    fixer_path = get_php_cs_fixer_path(logger)
    if not fixer_path:
        logger.error("Error: PHP-CS-Fixer executable not found")
        return -1

    cmd = [fixer_path, 'fix']

    if dry_run:
        cmd.append('--dry-run')
        cmd.append('--diff')

    cmd.append('--verbose')
    cmd.append('--no-interaction')

    config_path = find_fixer_config(path)
    if config_path:
        # Use the project config so its ->exclude([...]) Finder applies, and
        # intersection mode so the explicit path does not override those
        # excludes (default override mode discards the config's path filter).
        cmd.extend(['--config', str(config_path), '--path-mode=intersection'])
    else:
        if isinstance(fixer_config, str):
            rules = fixer_config
        else:
            rules = fixer_config.get('rules', '@PSR12')
        if rules:
            cmd.extend(['--rules', rules])

    cmd.append(path)

    logger.info(f"Running: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            check=False,
            cwd=path,
        )

        # External tool output forwarded verbatim — keep as print, not logger.
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        output = result.stdout or ''
        file_count = len(re.findall(r'^\s*\d+\)', output, re.MULTILINE))
        return file_count

    except FileNotFoundError:
        logger.error(f"Error: PHP-CS-Fixer executable not found: {fixer_path}")
        return -1
    except Exception as e:
        logger.error(f"Error running PHP-CS-Fixer: {e}")
        return -1


def main():
    parser = argparse.ArgumentParser(
        description='Auto-fix PHP code style issues using PHP-CS-Fixer with settings from rules JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python php_fixer.py --path .
  python php_fixer.py --path src/ --rules code_analysis_rules.json
  python php_fixer.py --path . --dry-run
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

    fixer_config = load_php_cs_fixer_config(args.rules, logger)

    if not fixer_config:
        logger.warning("Warning: No php_cs_fixer configuration found in rules file")
        logger.info("Using default PHP-CS-Fixer settings\n")

    if args.dry_run:
        logger.info("=== DRY RUN MODE - No changes will be made ===\n")

    result = run_php_cs_fixer(args.path, fixer_config, logger, args.dry_run)

    if result < 0:
        sys.exit(1)
    elif result == 0:
        logger.info("\nNo issues to fix!")
    elif args.dry_run:
        logger.info(f"\n{result} file(s) would be fixed")
    else:
        logger.info(f"\nFixed {result} file(s)")

    sys.exit(0)


if __name__ == '__main__':
    main()
