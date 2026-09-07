"""Path utilities shared across the analyzer."""

from collections.abc import Iterable
from pathlib import Path


def resolve_exclude_patterns(exclude_config, languages: Iterable[str]) -> list[str]:
    """Flatten a rules.json `exclude_patterns` value into a plain pattern list.

    The config accepts two shapes: a flat list applying to every language, or a
    dict keyed by language name. Iterating the dict form directly yields its
    KEYS ("python"), which match no file — so every consumer must come through
    here rather than looping over the raw config.
    """
    if not exclude_config:
        return []
    if isinstance(exclude_config, dict):
        merged: list[str] = []
        for language in languages:
            for pattern in exclude_config.get(language.lower(), []):
                if pattern not in merged:
                    merged.append(pattern)
        return merged
    return list(exclude_config)


def dir_paths_to_patterns(exclude_paths: Iterable[str] | None) -> list[str]:
    """Turn bare directory paths (`.dart_tool`, `vendor`) into `dir/**` globs.

    `exclude_paths` is the human-friendly form used by PMD and the global
    config; FileDiscovery only understands glob patterns, so every consumer
    converts through here.
    """
    if not exclude_paths:
        return []
    return [f"{Path(p).as_posix().rstrip('/')}/**" for p in exclude_paths]


def to_relative_posix(path: Path | str, base: Path | str) -> str:
    """Resolve `path`, make it relative to `base`, return forward-slash string.

    If `path` is not under `base`, returns the resolved absolute path as posix.
    """
    p = Path(path).resolve()
    b = Path(base).resolve()
    try:
        rel = p.relative_to(b)
    except ValueError:
        rel = p
    return str(rel).replace('\\', '/')
