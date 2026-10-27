#!/usr/bin/env python3
"""
CLI Code Analyzer - Analyze code files based on configurable rules
"""

import sys
from pathlib import Path

# Windows consoles default to cp1252; tool output (e.g. PMD CPD) can contain
# characters outside that codec, making bare print() raise UnicodeEncodeError.
# Force utf-8 with replacement so no analyzer dies on an un-encodable byte.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from analyzer_registry import LANGUAGE_ALIASES, list_analyzers  # noqa: E402
from cli_parser import build_parser  # noqa: E402
from logger import Logger  # noqa: E402


def main():
    """Main entry point"""
    parser = build_parser()
    args = parser.parse_args()

    # Handle --list-analyzers before other validation
    if args.list_analyzers:
        lang_arg = LANGUAGE_ALIASES.get(args.list_analyzers.lower(), args.list_analyzers)
        list_analyzers(lang_arg)
        sys.exit(0)

    # Handle --dead-exceptions (read-only rules-file audit) before other validation
    if args.dead_exceptions:
        from dead_exceptions import run_dead_exceptions
        sys.exit(run_dead_exceptions(args.rules, args.path, args.output, args.fix))

    if args.audit_dependencies:
        if not args.path:
            parser.error("--path is required for dependency auditing")
        from dependency_audit import run_dependency_audit
        sys.exit(run_dependency_audit(args.path, Logger(stream=sys.stderr)))

    if args.most_complex_function:
        if not args.path:
            parser.error("--path is required for --most-complex-function")
        if not args.files_from:
            parser.error("--files-from is required for --most-complex-function")
        from function_complexity import run_most_complex_function

        sys.exit(
            run_most_complex_function(
                args.path,
                args.files_from,
                Logger(stream=sys.stderr),
                args.diff_base,
            )
        )
    if args.files_from or args.diff_base:
        parser.error("--files-from and --diff-base require --most-complex-function")

    # Validate required arguments for analysis mode
    if not args.language:
        parser.error("--language is required for analysis")
    if not args.path:
        parser.error("--path is required for analysis")

    # Mutually exclusive flags
    if args.file and args.only_changed:
        parser.error("--file and --only-changed cannot be used together")

    # JSON must remain parseable even when analysis progress is being logged.
    logger = Logger(quiet=bool(args.file or args.format == 'json'))

    # Normalize languages: support both space-separated and comma-separated
    languages = []
    for lang in args.language:
        languages.extend(part.strip() for part in lang.split(',') if part.strip())

    # Resolve language aliases
    languages = [LANGUAGE_ALIASES.get(lang.lower(), lang) for lang in languages]
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

    # Validate --build-cache requires --output
    if args.build_cache and not args.output:
        parser.error("--build-cache requires --output to be set")

    # Normalize --only-analyzer: support both space- and comma-separated
    only_analyzers: set[str] | None = None
    if args.only_analyzer:
        only_analyzers = {
            part.strip() for name in args.only_analyzer for part in name.split(',') if part.strip()
        }
        if args.build_cache:
            parser.error("--only-analyzer and --build-cache cannot be used together")

    from cli_analysis import run_analysis
    run_analysis(args, languages, logger, only_analyzers)


if __name__ == '__main__':
    main()
