"""Path utilities shared across the analyzer."""

from pathlib import Path


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
