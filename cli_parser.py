"""Command-line parser construction for CLI Code Analyzer."""

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description='Analyze code files based on configurable rules',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --language flutter --path src/ --rules rules.json
  python main.py --language flutter --path . --rules rules.json --verbosity minimal
  python main.py --language python javascript --path ./src --verbosity verbose
  python main.py --language python,javascript --path ./src --loglevel error
  python main.py --language flutter --path lib/ --output reports/
  python main.py --language python --path ./src --format json
  python main.py --language python --path ./src --output reports/ --build-cache
  python main.py --language python --path ./src --output reports/ --file src/app.py
        """,
    )

    parser.add_argument(
        '-a',
        '--list-analyzers',
        metavar='LANGUAGE',
        nargs='?',
        const='all',
        help='List available analyzers for a language (or all languages if not specified)',
    )
    parser.add_argument(
        '-l',
        '--language',
        required=False,
        nargs='+',
        help=(
            'Programming language(s) to analyze (space-separated or comma-separated). '
            'Supported: flutter, python, php, csharp, javascript, svelte. Aliases: '
            'typescript/ts/js -> javascript, dart -> flutter, cs -> csharp, py -> python'
        ),
    )
    parser.add_argument(
        '-p',
        '--path',
        required=False,
        help='Path to the code directory (analyzes recursively) or single file to analyze',
    )
    parser.add_argument(
        '-r',
        '--rules',
        default='rules.json',
        help='Path to the rules JSON file (default: rules.json)',
    )
    parser.add_argument(
        '-v',
        '--verbosity',
        default='normal',
        choices=['minimal', 'normal', 'verbose'],
        help='Output verbosity level (default: normal)',
    )
    parser.add_argument(
        '-o',
        '--output',
        default=None,
        help='Path to output folder for reports (if set, saves reports to files instead of console)',
    )
    parser.add_argument(
        '-L',
        '--loglevel',
        default='all',
        choices=['error', 'warning', 'all'],
        help='Filter violations by severity level (default: all)',
    )
    parser.add_argument(
        '-m',
        '--maxamountoferrors',
        type=int,
        default=None,
        help='Maximum number of violations to include in CSV reports (default: unlimited)',
    )
    parser.add_argument(
        '-F',
        '--file',
        default=None,
        help='Filter violations to a single file (requires --path for project root). Defaults --maxamountoferrors to 5.',
    )
    parser.add_argument(
        '--only-changed',
        action='store_true',
        default=False,
        help='Analyze only files new or modified in git (vs HEAD, includes untracked, skips deletes). Mutually exclusive with --file.',
    )
    parser.add_argument(
        '-f',
        '--list-files',
        action='store_true',
        default=False,
        help='List all analyzed file paths after analysis completes',
    )
    parser.add_argument(
        '--format',
        default='text',
        choices=['text', 'json'],
        help='Output format for the report (default: text)',
    )
    parser.add_argument(
        '--build-cache',
        action='store_true',
        default=False,
        help='Build a violation cache in the output folder. Requires --output.',
    )
    parser.add_argument(
        '--cache-max-age',
        type=int,
        default=60,
        help='Maximum cache age in minutes before it is considered stale (default: 60)',
    )
    return parser
