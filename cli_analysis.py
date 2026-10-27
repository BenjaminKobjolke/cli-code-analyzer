"""Run analysis mode after the CLI entry point validates its arguments."""

import sys
from pathlib import Path

from cli_support import clean_report_files, resolve_reporter_log_level
from file_discovery import FileDiscovery


def run_analysis(args, languages, logger, only_analyzers):
    # -----------------------------------------------------------
    # Resolve filter_files (set of base-relative posix paths)
    # Drives both --file (1-element set) and --only-changed (N-element set).
    # -----------------------------------------------------------
    from path_utils import to_relative_posix

    filter_files: set[str] | None = None
    filter_mode: str | None = None
    base_path_resolved = Path(args.path).resolve()

    # Discovered source files, reused for cache mtime/file-set validation.
    discovered_files: list[Path] | None = None

    if args.file:
        filter_files = {to_relative_posix(args.file, base_path_resolved)}
        filter_mode = "file"

    if args.only_changed:
        from git_changes import (
            GitNotAvailableError,
            changed_since_from_env,
            find_repo_root,
            get_changed_files,
        )

        repo_root = find_repo_root(base_path_resolved)
        if repo_root is None:
            print(f"Error: --only-changed requires a git repo; '{args.path}' is not inside one", file=sys.stderr)
            sys.exit(1)
        try:
            changed = get_changed_files(repo_root, changed_since_from_env())
        except GitNotAvailableError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        # Reuse FileDiscovery for extension + exclusion filtering.
        discovery = FileDiscovery(languages, args.path)
        discovered_files = discovery.discover()
        discovered_set = {p.resolve() for p in discovered_files}

        matching = changed & discovered_set
        if not matching:
            # Bypass logger (quiet mode swallows info) — user needs to see this.
            print(f"No changed files for language(s) {', '.join(languages)} under {args.path}", file=sys.stderr)
            sys.exit(0)

        filter_files = {to_relative_posix(p, base_path_resolved) for p in matching}
        filter_mode = "only_changed"

    # -----------------------------------------------------------
    # Resolve the max-errors cap (violations reported per rule/analyzer).
    # Precedence: CLI --maxamountoferrors > rules.json "max_errors"
    #             > filter-mode default (5 for --file / --only-changed) > unlimited.
    # -----------------------------------------------------------
    cli_max_provided = '-m' in sys.argv or '--maxamountoferrors' in sys.argv
    from config import Config

    config = Config(args.rules)
    fail_on = config.get_global_fail_on()
    if not cli_max_provided:
        rules_max = config.get_global_max_errors()
        if rules_max is not None:
            args.maxamountoferrors = rules_max
        elif filter_files is not None:
            args.maxamountoferrors = 5

    # Import analysis modules (deferred to avoid loading when using --list-analyzers)
    from analyzer import AnalyzerConfig, CodeAnalyzer
    from models import LogLevel, OutputLevel
    from report_config import ReportConfig
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
        clean_report_files(output_folder)

    # -----------------------------------------------------------
    # Cache support
    # -----------------------------------------------------------
    rules_hash = ViolationCache.compute_rules_hash(args.rules)
    cache = None
    if output_folder and not only_analyzers:
        cache = ViolationCache(output_folder / '_violations_cache.db', logger=logger)

    # Discover source files once for cache validation (mtime / file-set checks).
    if cache and discovered_files is None:
        try:
            discovered_files = FileDiscovery(languages, args.path).discover()
        except ValueError:
            discovered_files = None  # unsupported language — surfaces in the analyzer run

    def cache_is_valid() -> bool:
        return cache.is_valid(args.cache_max_age, rules_hash,
                              current_files=discovered_files, base_path=args.path)

    # --build-cache: build cache and exit
    if args.build_cache:
        if cache_is_valid():
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
        failures = analyzer.get_failures()
        if failures:
            logger.info(f"Skipping violation cache: {len(failures)} tool(s) failed")
            reporter = Reporter(ReportConfig(
                violations=all_violations,
                file_count=analyzer.get_file_count(),
                output_level=output_level,
                log_level=resolve_reporter_log_level(cli_log_level, args.rules),
                output_folder=output_folder,
                max_errors=args.maxamountoferrors,
                logger=logger,
                failures=failures,
                fail_on_findings=args.fail_on_findings,
                fail_on=fail_on,
            ))
            reporter.report_json() if args.format == 'json' else reporter.report()
            sys.exit(1)
        cache.save(all_violations, rules_hash, languages, args.path, analyzer.get_analyzed_file_paths())
        logger.info("Cache built successfully")
        sys.exit(0)

    # Filter with cache: try cache first (covers --file and --only-changed)
    has_filter_and_cache = bool(filter_files) and bool(cache)
    can_use_violation_cache = has_filter_and_cache and cache_is_valid()
    if can_use_violation_cache:
        all_violations = cache.load_for_files(filter_files)

        reporter_log_level = resolve_reporter_log_level(cli_log_level, args.rules)
        reporter = Reporter(ReportConfig(
            violations=all_violations,
            file_count=0,
            output_level=output_level,
            log_level=reporter_log_level,
            output_folder=output_folder,
            max_errors=args.maxamountoferrors,
            logger=logger,
            fail_on_findings=args.fail_on_findings,
            fail_on_warnings=args.fail_on_warnings,
            fail_on=fail_on,
        ))
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
        if cache and cache_is_valid():
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
                filter_mode=filter_mode,
                logger=logger,
                only_analyzers=only_analyzers,
            ))
            analyzer.analyze()

            all_violations = analyzer.get_violations()
            total_file_count = analyzer.get_file_count()
            all_file_paths = analyzer.get_analyzed_file_paths()
            failures = analyzer.get_failures()

            # Save to cache whenever output folder is set (keeps cache fresh for --file queries)
            if cache and not failures:
                logger.info("Saving results to violation cache...")
                cache.save(all_violations, rules_hash, languages, args.path, all_file_paths)
            elif cache:
                logger.info(f"Skipping violation cache: {len(failures)} tool(s) failed")

        # Generate report
        reporter_log_level = resolve_reporter_log_level(cli_log_level, args.rules)
        reporter = Reporter(ReportConfig(
            violations=all_violations,
            file_count=total_file_count,
            output_level=output_level,
            log_level=reporter_log_level,
            output_folder=output_folder,
            max_errors=args.maxamountoferrors,
            logger=logger,
            failures=failures,
            fail_on_findings=args.fail_on_findings,
            fail_on_warnings=args.fail_on_warnings,
            fail_on=fail_on,
        ))
        if args.format == 'json':
            has_errors = reporter.report_json()
        else:
            has_errors = reporter.report()

        # Show analyzed files summary (always) and list (if requested)
        found_extensions = sorted({Path(fp).suffix for fp in all_file_paths if Path(fp).suffix})
        found_ext_str = ", ".join(found_extensions)
        logger.info(f"\nAnalyzed files ({len(all_file_paths)}) [{found_ext_str}]")
        if args.list_files:
            for fp in all_file_paths:
                logger.info(f"- {fp}")

        # Exit non-zero when reported findings meet the configured fail_on threshold.
        sys.exit(1 if has_errors else 0)

    except ValueError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
