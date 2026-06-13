#!/usr/bin/env python3
"""
CLI Code Analyzer - Analyze code files based on configurable rules
"""

import argparse
import sys
from pathlib import Path

from analyzer_registry import LANGUAGE_ALIASES, list_analyzers
from file_discovery import FileDiscovery
from logger import Logger


def _clean_report_files(output_folder: Path) -> None:
    """Remove all CSV and TXT report files from the output folder."""
    for f in output_folder.iterdir():
        if f.is_file() and f.suffix in ('.csv', '.txt'):
            f.unlink()


def _resolve_reporter_log_level(cli_log_level, rules_file: str):
    """Resolve the log level for the reporter.

    Uses CLI flag if provided, otherwise falls back to the global log_level
    from rules.json, defaulting to ALL.
    """
    from config import Config
    from models import LogLevel

    if cli_log_level:
        return cli_log_level
    config = Config(rules_file)
    global_ll = config.get_global_log_level()
    if global_ll:
        try:
            return LogLevel(global_ll)
        except ValueError:
            pass
    return LogLevel.ALL


def main():
    """Main entry point"""
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
        """
    )

    parser.add_argument(
        '-a', '--list-analyzers',
        metavar='LANGUAGE',
        nargs='?',
        const='all',
        help='List available analyzers for a language (or all languages if not specified)'
    )

    parser.add_argument(
        '-l', '--language',
        required=False,
        nargs='+',
        help='Programming language(s) to analyze (space-separated or comma-separated). Supported: flutter, python, php, csharp, javascript, svelte. Aliases: typescript/ts/js -> javascript, dart -> flutter, cs -> csharp, py -> python'
    )

    parser.add_argument(
        '-p', '--path',
        required=False,
        help='Path to the code directory (analyzes recursively) or single file to analyze'
    )

    parser.add_argument(
        '-r', '--rules',
        default='rules.json',
        help='Path to the rules JSON file (default: rules.json)'
    )

    parser.add_argument(
        '-v', '--verbosity',
        default='normal',
        choices=['minimal', 'normal', 'verbose'],
        help='Output verbosity level (default: normal)'
    )

    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Path to output folder for reports (if set, saves reports to files instead of console)'
    )

    parser.add_argument(
        '-L', '--loglevel',
        default='all',
        choices=['error', 'warning', 'all'],
        help='Filter violations by severity level (default: all)'
    )

    parser.add_argument(
        '-m', '--maxamountoferrors',
        type=int,
        default=None,
        help='Maximum number of violations to include in CSV reports (default: unlimited)'
    )

    parser.add_argument(
        '-F', '--file',
        default=None,
        help='Filter violations to a single file (requires --path for project root). Defaults --maxamountoferrors to 5.'
    )

    parser.add_argument(
        '--only-changed',
        action='store_true',
        default=False,
        help='Analyze only files new or modified in git (vs HEAD, includes untracked, skips deletes). Mutually exclusive with --file.'
    )

    parser.add_argument(
        '-f', '--list-files',
        action='store_true',
        default=False,
        help='List all analyzed file paths after analysis completes'
    )

    parser.add_argument(
        '--format',
        default='text',
        choices=['text', 'json'],
        help='Output format for the report (default: text)'
    )

    parser.add_argument(
        '--build-cache',
        action='store_true',
        default=False,
        help='Build a violation cache in the output folder. Requires --output.'
    )

    parser.add_argument(
        '--cache-max-age',
        type=int,
        default=60,
        help='Maximum cache age in minutes before it is considered stale (default: 60)'
    )

    args = parser.parse_args()

    # Handle --list-analyzers before other validation
    if args.list_analyzers:
        lang_arg = LANGUAGE_ALIASES.get(args.list_analyzers.lower(), args.list_analyzers)
        list_analyzers(lang_arg)
        sys.exit(0)

    # Validate required arguments for analysis mode
    if not args.language:
        parser.error("--language is required for analysis")
    if not args.path:
        parser.error("--path is required for analysis")

    # Mutually exclusive flags
    if args.file and args.only_changed:
        parser.error("--file and --only-changed cannot be used together")

    # Create logger — quiet when --file is used (suppress progress output for clean JSON)
    logger = Logger(quiet=bool(args.file))

    # Normalize languages: support both space-separated and comma-separated
    languages = []
    for lang in args.language:
        languages.extend(part.strip() for part in lang.split(',') if part.strip())

    # Resolve language aliases
    languages = [LANGUAGE_ALIASES.get(l.lower(), l) for l in languages]
    languages = list(dict.fromkeys(languages))  # deduplicate, preserve order

    # Validate path exists
    if not Path(args.path).exists():
        logger.error(f"Error: Path '{args.path}' does not exist")
        sys.exit(1)

    # Validate --file argument
    if args.file:
        if not args.path:
            logger.error("Error: --file requires --path to be set (project root)")
            sys.exit(1)
        file_path = Path(args.file).resolve()
        base_path = Path(args.path).resolve()
        if not file_path.exists():
            logger.error(f"Error: File '{args.file}' does not exist")
            sys.exit(1)
        if not file_path.is_relative_to(base_path):
            logger.error(f"Error: File '{args.file}' is not inside path '{args.path}'")
            sys.exit(1)
        # Default max_errors to 5 when --file is used, unless explicitly provided
        if args.maxamountoferrors is None and '-m' not in sys.argv and '--maxamountoferrors' not in sys.argv:
            args.maxamountoferrors = 5

    # Validate --build-cache requires --output
    if args.build_cache and not args.output:
        parser.error("--build-cache requires --output to be set")

    # -----------------------------------------------------------
    # Resolve filter_files (set of base-relative posix paths)
    # Drives both --file (1-element set) and --only-changed (N-element set).
    # -----------------------------------------------------------
    from path_utils import to_relative_posix

    filter_files: set[str] | None = None
    base_path_resolved = Path(args.path).resolve()

    if args.file:
        filter_files = {to_relative_posix(args.file, base_path_resolved)}

    if args.only_changed:
        from git_changes import GitNotAvailableError, find_repo_root, get_changed_files

        repo_root = find_repo_root(base_path_resolved)
        if repo_root is None:
            print(f"Error: --only-changed requires a git repo; '{args.path}' is not inside one", file=sys.stderr)
            sys.exit(1)
        try:
            changed = get_changed_files(repo_root)
        except GitNotAvailableError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        # Reuse FileDiscovery for extension + exclusion filtering.
        discovery = FileDiscovery(languages, args.path)
        discovered_set = {p.resolve() for p in discovery.discover()}

        matching = changed & discovered_set
        if not matching:
            # Bypass logger (quiet mode swallows info) — user needs to see this.
            print(f"No changed files for language(s) {', '.join(languages)} under {args.path}", file=sys.stderr)
            sys.exit(0)

        filter_files = {to_relative_posix(p, base_path_resolved) for p in matching}
        # Default max_errors to 5 when filtering, unless explicitly provided
        if args.maxamountoferrors is None and '-m' not in sys.argv and '--maxamountoferrors' not in sys.argv:
            args.maxamountoferrors = 5

    # Import analysis modules (deferred to avoid loading when using --list-analyzers)
    from analyzer import AnalyzerConfig, CodeAnalyzer
    from models import LogLevel, OutputLevel
    from reporter import Reporter
    from violation_cache import ViolationCache

    # Convert verbosity string to enum
    output_level = OutputLevel(args.verbosity)

    # Determine if --loglevel was explicitly provided by user
    # If not provided, pass None to let CodeAnalyzer use config values
    cli_log_level = None
    if '--loglevel' in sys.argv or '-L' in sys.argv:
        cli_log_level = LogLevel(args.loglevel)

    # Validate and create output folder if specified
    output_folder = None
    if args.output:
        output_folder = Path(args.output)
        output_folder.mkdir(parents=True, exist_ok=True)
        _clean_report_files(output_folder)

    # -----------------------------------------------------------
    # Cache support
    # -----------------------------------------------------------
    rules_hash = ViolationCache.compute_rules_hash(args.rules)
    cache = None
    if output_folder:
        cache = ViolationCache(output_folder / '_violations_cache.db', logger=logger)

    # --build-cache: build cache and exit
    if args.build_cache:
        if cache.is_valid(args.cache_max_age, rules_hash):
            logger.info("Cache is fresh, skipping rebuild")
            sys.exit(0)
        # Run full analysis and save to cache
        analyzer = CodeAnalyzer(AnalyzerConfig(
            languages=languages,
            path=args.path,
            rules_file=args.rules,
            output_folder=output_folder,
            cli_log_level=cli_log_level,
            max_errors=args.maxamountoferrors,
            filter_files=filter_files,
            logger=logger,
        ))
        analyzer.analyze()
        all_violations = analyzer.get_violations()
        cache.save(all_violations, rules_hash, languages, args.path, analyzer.get_analyzed_file_paths())
        logger.info("Cache built successfully")
        sys.exit(0)

    # Filter with cache: try cache first (covers --file and --only-changed)
    if filter_files and cache and cache.is_valid(args.cache_max_age, rules_hash):
        all_violations = cache.load_for_files(filter_files)

        reporter_log_level = _resolve_reporter_log_level(cli_log_level, args.rules)
        reporter = Reporter(
            all_violations,
            0,
            output_level,
            reporter_log_level,
            output_folder,
            args.maxamountoferrors,
            logger=logger,
        )
        if args.format == 'json':
            has_errors = reporter.report_json()
        else:
            has_errors = reporter.report()
        sys.exit(1 if has_errors else 0)

    # -----------------------------------------------------------
    # Normal analysis flow
    # -----------------------------------------------------------
    try:
        # Tool-run failures from this analysis (empty when results come from cache;
        # a failure that occurred during a cached run survives as an ERROR violation).
        failures = []
        # Check cache first for normal runs
        if cache and cache.is_valid(args.cache_max_age, rules_hash):
            logger.info("Using cached results")
            all_violations, all_file_paths = cache.load_all_with_paths()
            total_file_count = len(all_file_paths)
        else:
            # Collect all extensions for the requested languages
            all_extensions = []
            for lang in languages:
                for ext in FileDiscovery.LANGUAGE_EXTENSIONS.get(lang.lower(), []):
                    if ext not in all_extensions:
                        all_extensions.append(ext)
            ext_str = ", ".join(all_extensions) if all_extensions else "unknown"
            lang_str = ", ".join(languages)

            logger.info(f"\n{'=' * 60}")
            logger.info("  CLI Code Analyzer")
            logger.info(f"  Path: {args.path}")
            if filter_files:
                if len(filter_files) == 1:
                    logger.info(f"  File filter: {next(iter(filter_files))}")
                else:
                    logger.info(f"  File filter: {len(filter_files)} file(s) (--only-changed)")
            logger.info(f"  Language: {lang_str}")
            logger.info(f"  Extensions: {ext_str}")
            logger.info(f"{'=' * 60}")

            analyzer = CodeAnalyzer(AnalyzerConfig(
                languages=languages,
                path=args.path,
                rules_file=args.rules,
                output_folder=output_folder,
                cli_log_level=cli_log_level,
                max_errors=args.maxamountoferrors,
                filter_files=filter_files,
                logger=logger,
            ))
            analyzer.analyze()

            all_violations = analyzer.get_violations()
            total_file_count = analyzer.get_file_count()
            all_file_paths = analyzer.get_analyzed_file_paths()
            failures = analyzer.get_failures()

            # Save to cache whenever output folder is set (keeps cache fresh for --file queries)
            if cache:
                logger.info("Saving results to violation cache...")
                cache.save(all_violations, rules_hash, languages, args.path, all_file_paths)

        # Generate report
        reporter_log_level = _resolve_reporter_log_level(cli_log_level, args.rules)
        reporter = Reporter(
            all_violations,
            total_file_count,
            output_level,
            reporter_log_level,
            output_folder,
            args.maxamountoferrors,
            logger=logger,
            failures=failures,
        )
        if args.format == 'json':
            has_errors = reporter.report_json()
        else:
            has_errors = reporter.report()

        # Show analyzed files summary (always) and list (if requested)
        found_extensions = sorted(set(Path(fp).suffix for fp in all_file_paths if Path(fp).suffix))
        found_ext_str = ", ".join(found_extensions)
        logger.info(f"\nAnalyzed files ({len(all_file_paths)}) [{found_ext_str}]")
        if args.list_files:
            for fp in all_file_paths:
                logger.info(f"- {fp}")

        # Exit with error code if violations found
        sys.exit(1 if has_errors else 0)

    except ValueError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
