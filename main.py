#!/usr/bin/env python3
"""
CLI Code Analyzer - Analyze code files based on configurable rules
"""

import argparse
import sys
from pathlib import Path
from analyzer import CodeAnalyzer
from reporter import Reporter
from models import OutputLevel, LogLevel


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Analyze code files based on configurable rules',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --language flutter --path src/ --rules rules.json
  python main.py --language flutter --path . --rules rules.json --verbosity minimal
  python main.py --language flutter --path lib/ --verbosity verbose
  python main.py --language flutter --path src/ --loglevel error
  python main.py --language flutter --path lib/ --output reports/
        """
    )

    parser.add_argument(
        '--language',
        required=True,
        help='Programming language to analyze. Line counting: flutter, python. Duplicate detection (PMD): dart, python, java, javascript, typescript'
    )

    parser.add_argument(
        '--path',
        required=True,
        help='Path to the code directory (analyzes recursively) or single file to analyze'
    )

    parser.add_argument(
        '--rules',
        default='rules.json',
        help='Path to the rules JSON file (default: rules.json)'
    )

    parser.add_argument(
        '--verbosity',
        default='normal',
        choices=['minimal', 'normal', 'verbose'],
        help='Output verbosity level (default: normal)'
    )

    parser.add_argument(
        '--output',
        default=None,
        help='Path to output folder for reports (if set, saves reports to files instead of console)'
    )

    parser.add_argument(
        '--loglevel',
        default='all',
        choices=['error', 'warning', 'all'],
        help='Filter violations by severity level (default: all)'
    )

    parser.add_argument(
        '--maxamountoferrors',
        type=int,
        default=None,
        help='Maximum number of violations to include in CSV reports (default: unlimited)'
    )

    args = parser.parse_args()

    # Validate path exists
    if not Path(args.path).exists():
        print(f"Error: Path '{args.path}' does not exist")
        sys.exit(1)

    # Convert verbosity string to enum
    output_level = OutputLevel(args.verbosity)

    # Determine if --loglevel was explicitly provided by user
    # If not provided, pass None to let CodeAnalyzer use config values
    cli_log_level = None
    if '--loglevel' in sys.argv:
        cli_log_level = LogLevel(args.loglevel)

    # Validate and create output folder if specified
    output_folder = None
    if args.output:
        output_folder = Path(args.output)
        output_folder.mkdir(parents=True, exist_ok=True)

        # Clean up old report files
        (output_folder / 'line_count_report.csv').unlink(missing_ok=True)
        (output_folder / 'line_count_report.txt').unlink(missing_ok=True)  # Legacy format
        (output_folder / 'duplicate_code.csv').unlink(missing_ok=True)
        (output_folder / 'dart_analyze.csv').unlink(missing_ok=True)
        (output_folder / 'dart_code_linter.csv').unlink(missing_ok=True)

    # Run analysis
    try:
        analyzer = CodeAnalyzer(args.language, args.path, args.rules, output_folder, cli_log_level, args.maxamountoferrors)
        analyzer.analyze()

        # Generate report
        # For reporter, use CLI log level if provided, otherwise use 'all' as default
        # (violations are already filtered by rules, reporter filtering is redundant but kept for backward compatibility)
        reporter_log_level = cli_log_level if cli_log_level else LogLevel.ALL
        reporter = Reporter(
            analyzer.get_violations(),
            analyzer.get_file_count(),
            output_level,
            reporter_log_level,
            output_folder,
            args.maxamountoferrors
        )
        has_errors = reporter.report()

        # Exit with error code if violations found
        sys.exit(1 if has_errors else 0)

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
