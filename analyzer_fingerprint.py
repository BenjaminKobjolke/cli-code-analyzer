"""Deterministic identity for production analyzer Python code."""

import hashlib
from pathlib import Path

ANALYZER_ROOT = Path(__file__).resolve().parent


def compute_analyzer_hash(source_root: Path = ANALYZER_ROOT) -> str:
    """Hash production analyzer module paths and contents deterministically."""
    source_files = [
        path for path in source_root.glob("*.py")
        if path.name != "conftest.py"
    ]
    rules_dir = source_root / "rules"
    if rules_dir.is_dir():
        source_files.extend(rules_dir.rglob("*.py"))

    digest = hashlib.sha256()
    for path in sorted(
        source_files,
        key=lambda item: item.relative_to(source_root).as_posix(),
    ):
        relative_path = path.relative_to(source_root).as_posix()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
