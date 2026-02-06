#!/usr/bin/env python3
"""
CLI Code Analyzer - Analyze code files based on configurable rules
"""

import argparse
import sys
from pathlib import Path


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
        '--list-analyzers',
        metavar='LANGUAGE',
        nargs='?',
        const='all',
        help='List available analyzers for a language (or all languages if not specified)'
    )

    parser.add_argument(
        '--language',
        required=False,
        help='Programming language to analyze. Line counting: flutter, python, php, csharp, javascript. Duplicate detection (PMD): dart, python, java, javascript, typescript, php, csharp. Static analysis: php (PHPStan, PHP-CS-Fixer), python (Ruff), javascript/typescript (ESLint), csharp (dotnet build)'
    )

    parser.add_argument(
        '--path',
        required=False,
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

    # Handle --list-analyzers before other validation
    if args.list_analyzers:
        from analyzer_registry import list_analyzers
        list_analyzers(args.list_analyzers)
        sys.exit(0)

    # Validate required arguments for analysis mode
    if not args.language:
        parser.error("--language is required for analysis")
    if not args.path:
        parser.error("--path is required for analysis")

    # Validate path exists
    if not Path(args.path).exists():
        print(f"Error: Path '{args.path}' does not exist")
        sys.exit(1)

    # Import analysis modules (deferred to avoid loading when using --list-analyzers)
    from analyzer import CodeAnalyzer
    from models import LogLevel, OutputLevel
    from reporter import Reporter

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
        (output_folder / 'dotnet_analyze.csv').unlink(missing_ok=True)
        (output_folder / 'eslint_analyze.csv').unlink(missing_ok=True)
        (output_folder / 'dart_unused_files.csv').unlink(missing_ok=True)
        (output_folder / 'dart_unused_dependencies.csv').unlink(missing_ok=True)
        (output_folder / 'dart_import_rules.csv').unlink(missing_ok=True)
        (output_folder / 'dart_unused_code.csv').unlink(missing_ok=True)
        (output_folder / 'dart_missing_dispose.csv').unlink(missing_ok=True)
        (output_folder / 'dart_test_coverage.csv').unlink(missing_ok=True)

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
