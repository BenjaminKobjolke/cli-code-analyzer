"""
Centralized registry of available analyzers per language.
"""

import json
from typing import List, Tuple, Optional


# Registry format: (analyzer_name, description, requires)
# requires = None means no external tool required
ANALYZER_REGISTRY = {
    'php': [
        ('max_lines_per_file', 'File length checks', None),
        ('pmd_duplicates', 'Duplicate code detection', 'PMD'),
        ('phpstan_analyze', 'Static analysis', 'PHPStan (composer)'),
        ('php_cs_fixer', 'Code style checking', 'PHP-CS-Fixer (composer)'),
        ('intelephense_analyze', 'LSP diagnostics', 'Intelephense (npm)'),
    ],
    'python': [
        ('max_lines_per_file', 'File length checks', None),
        ('pmd_duplicates', 'Duplicate code detection', 'PMD'),
        ('ruff_analyze', 'Linting and style', 'Ruff (pip)'),
    ],
    'flutter': [
        ('max_lines_per_file', 'File length checks', None),
        ('pmd_duplicates', 'Duplicate code detection', 'PMD'),
        ('dart_analyze', 'Dart static analysis', 'Dart SDK'),
        ('flutter_analyze', 'Flutter analysis', 'Flutter SDK'),
        ('dart_code_linter', 'Code metrics', 'DCM'),
        ('dart_unused_files', 'Unused file detection', None),
        ('dart_unused_dependencies', 'Unused dependency detection', None),
        ('dart_import_rules', 'Architecture layer enforcement', None),
        ('dart_unused_code', 'Unused code detection', 'dart-lsp-mcp'),
        ('dart_missing_dispose', 'Missing dispose detection', 'dart-lsp-mcp'),
        ('dart_test_coverage', 'Test coverage checking', 'Flutter SDK'),
    ],
    'csharp': [
        ('max_lines_per_file', 'File length checks', None),
        ('pmd_duplicates', 'Duplicate code detection', 'PMD'),
        ('dotnet_analyze', '.NET analysis', '.NET SDK'),
    ],
    'javascript': [
        ('max_lines_per_file', 'File length checks', None),
        ('pmd_duplicates', 'Duplicate code detection', 'PMD'),
        ('eslint_analyze', 'Linting and style', 'ESLint (npm)'),
        ('tsc_analyze', 'TypeScript type checking', 'TypeScript (npm)'),
    ],
    'svelte': [
        ('max_lines_per_file', 'File length checks', None),
        ('pmd_duplicates', 'Duplicate code detection', 'PMD'),
        ('eslint_analyze', 'Linting and style', 'ESLint (npm) + eslint-plugin-svelte'),
        ('svelte_check', 'TypeScript/Svelte type checking', 'svelte-check (npm)'),
    ],
}

# Shorthand and alternative language names that map to canonical names above
LANGUAGE_ALIASES = {
    'typescript': 'javascript',
    'ts': 'javascript',
    'js': 'javascript',
    'dart': 'flutter',
    'cs': 'csharp',
    'py': 'python',
}


def get_analyzers_for_language(lang: str) -> List[Tuple[str, str, Optional[str]]]:
    """
    Get the list of available analyzers for a language.

    Args:
        lang: Language name (php, python, flutter, csharp)

    Returns:
        List of (name, description, requires) tuples
    """
    return ANALYZER_REGISTRY.get(lang.lower(), [])


def get_supported_languages() -> List[str]:
    """
    Get list of supported language names.

    Returns:
        List of language names
    """
    return list(ANALYZER_REGISTRY.keys())


def format_analyzers_output(lang: str, output_format: str = 'text') -> str:
    """
    Format analyzer information for output.

    Args:
        lang: Language name or 'all' for all languages
        output_format: 'text' or 'json'

    Returns:
        Formatted string
    """
    if output_format == 'json':
        if lang == 'all':
            data = {
                language: [
                    {'name': name, 'description': desc, 'requires': req}
                    for name, desc, req in analyzers
                ]
                for language, analyzers in ANALYZER_REGISTRY.items()
            }
        else:
            analyzers = get_analyzers_for_language(lang)
            if not analyzers:
                return json.dumps({'error': f"Unknown language: {lang}"}, indent=2)
            data = {
                lang: [
                    {'name': name, 'description': desc, 'requires': req}
                    for name, desc, req in analyzers
                ]
            }
        return json.dumps(data, indent=2)

    # Text format
    lines = []

    if lang == 'all':
        lines.append("Available analyzers by language:")
        lines.append("")
        for language in sorted(ANALYZER_REGISTRY.keys()):
            lines.append(f"{language}:")
            lines.extend(_format_analyzer_list(ANALYZER_REGISTRY[language]))
            lines.append("")
    else:
        analyzers = get_analyzers_for_language(lang)
        if not analyzers:
            return f"Unknown language: {lang}\n\nSupported languages: {', '.join(sorted(get_supported_languages()))}"

        lines.append(f"Available analyzers for {lang}:")
        lines.append("")
        lines.extend(_format_analyzer_list(analyzers))

    return '\n'.join(lines)


def _format_analyzer_list(analyzers: List[Tuple[str, str, Optional[str]]]) -> List[str]:
    """Format a list of analyzers as aligned text lines."""
    lines = []

    # Calculate column widths
    max_name = max(len(name) for name, _, _ in analyzers)
    max_desc = max(len(desc) for _, desc, _ in analyzers)

    for name, desc, requires in analyzers:
        if requires:
            lines.append(f"  {name:<{max_name}}  {desc:<{max_desc}}  Requires: {requires}")
        else:
            lines.append(f"  {name:<{max_name}}  {desc}")

    return lines


def list_analyzers(lang: str, output_format: str = 'text') -> None:
    """
    Print available analyzers for the given language.

    Args:
        lang: Language name or 'all' for all languages
        output_format: 'text' or 'json'
    """
    print(format_analyzers_output(lang, output_format))
