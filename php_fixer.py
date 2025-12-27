#!/usr/bin/env python3
"""PHP Fixer - Auto-fix PHP code style issues using PHP-CS-Fixer with settings from rules JSON"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from settings import Settings


def load_php_cs_fixer_config(rules_file: str) -> dict:
    """Load PHP-CS-Fixer configuration from rules JSON file."""
    rules_path = Path(rules_file)
    if not rules_path.exists():
        print(f"Warning: Rules file not found: {rules_file}")
        return {}

    try:
        with open(rules_path, encoding='utf-8') as f:
            config = json.load(f)
        return config.get('php_cs_fixer', {})
    except json.JSONDecodeError as e:
        print(f"Error parsing rules file: {e}")
        return {}


def get_php_cs_fixer_path() -> str | None:
    """Get PHP-CS-Fixer executable path."""
    import shutil

    # First check bundled php/vendor/bin folder (priority)
    script_dir = Path(__file__).parent
    bundled_paths = [
        script_dir / 'php' / 'vendor' / 'bin' / 'php-cs-fixer.bat',
        script_dir / 'php' / 'vendor' / 'bin' / 'php-cs-fixer',
    ]
    for bundled_fixer in bundled_paths:
        if bundled_fixer.exists():
            return str(bundled_fixer)

    # Check if php-cs-fixer is in PATH
    fixer_in_path = shutil.which('php-cs-fixer')
    if fixer_in_path:
        return fixer_in_path

    # Check other common vendor locations
    vendor_paths = [
        script_dir / 'vendor' / 'bin' / 'php-cs-fixer',
        script_dir / 'vendor' / 'bin' / 'php-cs-fixer.bat',
    ]
    for vendor_fixer in vendor_paths:
        if vendor_fixer.exists():
            return str(vendor_fixer)

    # Check settings
    settings = Settings()
    fixer_path = settings.get_php_cs_fixer_path()
    if fixer_path and Path(fixer_path).exists():
        return fixer_path

    # Prompt user (only if running interactively)
    if sys.stdin.isatty():
        return settings.prompt_and_save_php_cs_fixer_path()

    print("Error: PHP-CS-Fixer not found. Please install with: composer require --dev friendsofphp/php-cs-fixer")
    return None


def run_php_cs_fixer(path: str, fixer_config: dict, dry_run: bool = False) -> int:
    """Run PHP-CS-Fixer on the specified path.

    Args:
        path: Path to fix
        fixer_config: PHP-CS-Fixer configuration from rules JSON
        dry_run: If True, show what would be fixed without making changes

    Returns:
        Number of files fixed (or would be fixed in dry-run mode)
    """
    fixer_path = get_php_cs_fixer_path()
    if not fixer_path:
        print("Error: PHP-CS-Fixer executable not found")
        return -1

    # Build command
    cmd = [fixer_path, 'fix']

    if dry_run:
        cmd.append('--dry-run')
        cmd.append('--diff')

    # Add verbose flag for more output
    cmd.append('--verbose')

    # Add rules configuration if specified
    rules = fixer_config.get('rules', '@PSR12')
    if rules:
        cmd.extend(['--rules', rules])

    # Add path to fix
    cmd.append(path)

    print(f"Running: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            check=False
        )

        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        # Parse the output to count fixed files
        output = result.stdout or ''

        # Count files that were fixed or would be fixed
        # PHP-CS-Fixer outputs lines like "1) path/to/file.php"
        file_count = len(re.findall(r'^\s*\d+\)', output, re.MULTILINE))

        return file_count

    except FileNotFoundError:
        print(f"Error: PHP-CS-Fixer executable not found: {fixer_path}")
        return -1
    except Exception as e:
        print(f"Error running PHP-CS-Fixer: {e}")
        return -1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Auto-fix PHP code style issues using PHP-CS-Fixer with settings from rules JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python php_fixer.py --path .
  python php_fixer.py --path src/ --rules code_analysis_rules.json
  python php_fixer.py --path . --dry-run
        """
    )

    parser.add_argument(
        '--path',
        required=True,
        help='Path to the code directory or file to fix'
    )

    parser.add_argument(
        '--rules',
        default='code_analysis_rules.json',
        help='Path to the rules JSON file (default: code_analysis_rules.json)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be fixed without making changes'
    )

    args = parser.parse_args()

    # Validate path exists
    if not Path(args.path).exists():
        print(f"Error: Path '{args.path}' does not exist")
        sys.exit(1)

    # Load PHP-CS-Fixer config from rules file
    fixer_config = load_php_cs_fixer_config(args.rules)

    if not fixer_config:
        print("Warning: No php_cs_fixer configuration found in rules file")
        print("Using default PHP-CS-Fixer settings\n")

    # Run PHP-CS-Fixer
    if args.dry_run:
        print("=== DRY RUN MODE - No changes will be made ===\n")

    result = run_php_cs_fixer(args.path, fixer_config, args.dry_run)

    if result < 0:
        sys.exit(1)
    elif result == 0:
        print("\nNo issues to fix!")
    else:
        if args.dry_run:
            print(f"\n{result} file(s) would be fixed")
        else:
            print(f"\nFixed {result} file(s)")

    sys.exit(0)


if __name__ == '__main__':
    main()
