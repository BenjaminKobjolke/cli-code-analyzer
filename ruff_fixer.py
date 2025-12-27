#!/usr/bin/env python3
"""
Ruff Fixer - Auto-fix Python code issues using Ruff with settings from rules JSON
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from settings import Settings


def load_ruff_config(rules_file: str) -> dict:
    """Load ruff configuration from rules JSON file.

    Args:
        rules_file: Path to the rules JSON file

    Returns:
        Ruff configuration dict, or empty dict if not found
    """
    rules_path = Path(rules_file)
    if not rules_path.exists():
        print(f"Warning: Rules file not found: {rules_file}")
        return {}

    try:
        with open(rules_path, encoding='utf-8') as f:
            config = json.load(f)
        return config.get('ruff_analyze', {})
    except json.JSONDecodeError as e:
        print(f"Error parsing rules file: {e}")
        return {}


def get_ruff_path() -> str | None:
    """Get ruff executable path.

    Returns:
        Path to ruff executable or None
    """
    import shutil

    # Check if ruff is in PATH
    ruff_in_path = shutil.which('ruff')
    if ruff_in_path:
        return ruff_in_path

    # Check common venv locations relative to script
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

    # Check settings
    settings = Settings()
    ruff_path = settings.get_ruff_path()
    if ruff_path and Path(ruff_path).exists():
        return ruff_path

    # Prompt user (only if running interactively)
    import sys
    if sys.stdin.isatty():
        return settings.prompt_and_save_ruff_path()

    print("Error: Ruff not found. Please install with: pip install ruff")
    return None


def run_ruff_fix(path: str, ruff_config: dict, dry_run: bool = False) -> int:
    """Run ruff fix on the specified path.

    Args:
        path: Path to fix
        ruff_config: Ruff configuration from rules JSON
        dry_run: If True, show what would be fixed without making changes

    Returns:
        Number of issues fixed (or would be fixed in dry-run mode)
    """
    ruff_path = get_ruff_path()
    if not ruff_path:
        print("Error: Ruff executable not found")
        return -1

    # Build command
    cmd = [ruff_path, 'check']

    if dry_run:
        cmd.append('--diff')
    else:
        cmd.append('--fix')

    # Add select rules if configured
    if ruff_config.get('select'):
        cmd.extend(['--select', ','.join(ruff_config['select'])])

    # Add ignore rules if configured
    if ruff_config.get('ignore'):
        cmd.extend(['--ignore', ','.join(ruff_config['ignore'])])

    # Add exclude patterns
    if ruff_config.get('exclude_patterns'):
        for pattern in ruff_config['exclude_patterns']:
            cmd.extend(['--exclude', pattern])

    # Add path to analyze
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

        # Parse the "Found X errors" message
        output = result.stderr or result.stdout
        if 'Found' in output and 'error' in output:
            # Extract number from "Found X errors (Y fixed, Z remaining)"
            import re
            match = re.search(r'Found (\d+) errors?', output)
            if match:
                return int(match.group(1))

        return 0

    except FileNotFoundError:
        print(f"Error: Ruff executable not found: {ruff_path}")
        return -1
    except Exception as e:
        print(f"Error running ruff: {e}")
        return -1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Auto-fix Python code issues using Ruff with settings from rules JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ruff_fixer.py --path .
  python ruff_fixer.py --path src/ --rules code_analysis_rules.json
  python ruff_fixer.py --path . --dry-run
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

    # Load ruff config from rules file
    ruff_config = load_ruff_config(args.rules)

    if not ruff_config:
        print("Warning: No ruff_analyze configuration found in rules file")
        print("Using default ruff settings\n")

    # Run ruff fix
    if args.dry_run:
        print("=== DRY RUN MODE - No changes will be made ===\n")

    result = run_ruff_fix(args.path, ruff_config, args.dry_run)

    if result < 0:
        sys.exit(1)
    elif result == 0:
        print("\nNo issues to fix!")
    else:
        if args.dry_run:
            print(f"\n{result} issue(s) would be fixed")
        else:
            print(f"\nFixed {result} issue(s)")

    sys.exit(0)


if __name__ == '__main__':
    main()
