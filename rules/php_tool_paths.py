"""Resolve PHP tools bundled with the analyzer's Composer project."""

from pathlib import Path


def get_bundled_php_tool_path(tool_name: str, project_root: Path | None = None) -> str | None:
    """Return a bundled PHP executable path, preferring the Windows launcher."""
    root = project_root or Path(__file__).parent.parent
    bin_dir = root / "php" / "vendor" / "bin"
    for executable in (f"{tool_name}.bat", tool_name):
        path = bin_dir / executable
        if path.exists():
            return str(path)
    return None
