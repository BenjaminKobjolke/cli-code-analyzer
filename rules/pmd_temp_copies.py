"""Temporary source copies for PMD lexers that require adjusted inputs."""

import os
import tempfile
from collections.abc import Callable
from pathlib import Path


def _write_temp_copy(
    source_path: Path,
    content: str,
    prefix: str,
    suffix: str,
    logger,
) -> tuple[str, Path] | None:
    """Write one PMD input copy and return its path mapping and cleanup path."""
    temp_path: Path | None = None
    try:
        fd, raw_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        temp_path = Path(raw_path).resolve()
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(content)
    except OSError as error:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        logger.warning(f"Warning: Could not create PMD temp copy for {source_path}: {error}")
        return None
    return str(temp_path), temp_path


def _copy_files(
    scan_files: list[Path],
    logger,
    should_copy: Callable[[Path, str], bool],
    prefix: str,
    suffix_for: Callable[[Path], str],
    content_for: Callable[[str], str],
) -> tuple[dict[str, str], list[Path]]:
    mapping: dict[str, str] = {}
    temps: list[Path] = []
    for path in scan_files:
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            if not should_copy(path, source):
                continue
            result = _write_temp_copy(path, content_for(source), prefix, suffix_for(path), logger)
        except OSError as error:
            logger.warning(f"Warning: Could not read PMD source file {path}: {error}")
            continue
        if result is None:
            continue
        temp_path, cleanup_path = result
        mapping[temp_path] = str(path.resolve())
        temps.append(cleanup_path)
    return mapping, temps


def sanitize_shebang_files(scan_files: list[Path], logger) -> tuple[dict[str, str], list[Path]]:
    """Blank shebang lines for CPD's ecmascript lexer while preserving line numbers."""
    return _copy_files(
        scan_files,
        logger,
        should_copy=lambda _path, source: source.startswith("#!"),
        prefix="pmd_shebang_",
        suffix_for=lambda path: path.suffix,
        content_for=lambda source: "\n" + source.split("\n", maxsplit=1)[1]
        if "\n" in source else "\n",
    )


def copy_ino_as_cpp(scan_files: list[Path], logger) -> tuple[dict[str, str], list[Path]]:
    """Copy Arduino sketches with a .cpp suffix so PMD CPD includes them."""
    return _copy_files(
        scan_files,
        logger,
        should_copy=lambda path, _source: path.suffix.lower() == ".ino",
        prefix="pmd_ino_",
        suffix_for=lambda _path: ".cpp",
        content_for=lambda source: source,
    )
