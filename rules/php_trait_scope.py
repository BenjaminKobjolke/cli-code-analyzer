"""Resolve project traits needed to analyze changed PHP classes in context."""

import re
from pathlib import Path

_NAMESPACE = re.compile(r"^\s*namespace\s+([\w\\]+)\s*[;{]", re.MULTILINE)
_TRAIT = re.compile(r"^\s*trait\s+(\w+)\b", re.MULTILINE)
_FIRST_TYPE = re.compile(
    r"^\s*(?:(?:abstract|final|readonly)\s+)*(?:class|trait|enum)\s+\w+\b",
    re.MULTILINE,
)
_IMPORT = re.compile(r"^\s*use\s+([\w\\]+)(?:\s+as\s+(\w+))?\s*;", re.MULTILINE)
_TRAIT_USE = re.compile(
    r"\buse\s+(\\?\w[\w\\]*(?:\s*,\s*\\?\w[\w\\]*)*)\s*[;{]",
    re.MULTILINE,
)


def _read_php(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _trait_name(namespace: str, name: str) -> str:
    return "\\".join(part for part in (namespace.strip("\\"), name.strip("\\")) if part).lower()


def build_trait_index(files: list[Path]) -> dict[str, Path]:
    """Map lower-case fully qualified trait names to the files that declare them."""
    index: dict[str, Path] = {}
    for path in sorted(files, key=str):
        source = _read_php(path)
        namespace_match = _NAMESPACE.search(source)
        namespace = namespace_match.group(1) if namespace_match else ""
        for match in _TRAIT.finditer(source):
            index[_trait_name(namespace, match.group(1))] = path
    return index


def _file_traits(source: str) -> tuple[str, dict[str, str], list[str]]:
    """Return namespace, import aliases and trait uses in type bodies.

    Group imports and multiple namespace blocks intentionally use the first
    namespace and simple imports only; project trait files normally follow this
    layout, while unresolved forms are safely ignored.
    """
    # shortcut: Group imports and additional namespace blocks are not resolved.
    namespace_match = _NAMESPACE.search(source)
    namespace = namespace_match.group(1) if namespace_match else ""
    first_type = _FIRST_TYPE.search(source)
    header = source[:first_type.start()] if first_type else source
    body = source[first_type.start():] if first_type else ""
    imports: dict[str, str] = {}
    for match in _IMPORT.finditer(header):
        imported = match.group(1).strip("\\")
        alias = match.group(2) or imported.rsplit("\\", 1)[-1]
        imports[alias.lower()] = imported
    uses = [name.strip() for match in _TRAIT_USE.finditer(body)
            for name in match.group(1).split(",")]
    return namespace, imports, uses


def _resolve_name(name: str, namespace: str, imports: dict[str, str]) -> str:
    name = name.strip()
    if name.startswith("\\"):
        return name.strip("\\").lower()
    first, separator, rest = name.partition("\\")
    imported = imports.get(first.lower())
    if imported:
        return "\\".join(part for part in (imported, rest if separator else "") if part).lower()
    return _trait_name(namespace, name)


def resolve_used_trait_files(changed: list[Path], index: dict[str, Path]) -> list[Path]:
    """Return sorted trait files used directly or transitively by changed PHP files."""
    changed_ids = {path.resolve() for path in changed}
    visited: set[Path] = set()
    queued = list(changed)
    extra: set[Path] = set()
    while queued:
        path = queued.pop()
        identity = path.resolve()
        if identity in visited:
            continue
        visited.add(identity)
        namespace, imports, uses = _file_traits(_read_php(path))
        for name in uses:
            trait_path = index.get(_resolve_name(name, namespace, imports))
            if trait_path is None:
                continue
            trait_identity = trait_path.resolve()
            if trait_identity not in changed_ids:
                extra.add(trait_path)
            if trait_identity not in visited:
                queued.append(trait_path)
    return sorted(extra, key=str)
