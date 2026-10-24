"""Map listed source files to supported languages and prepare parser input."""

import re
from dataclasses import dataclass
from pathlib import Path

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".dart": "dart",
    ".php": "php",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".cs": "csharp",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".svelte": "svelte",
    ".ahk": "autohotkey",
    ".ino": "cpp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
}

_SCRIPT_TAG = re.compile(r"<script\b[^>]*>(.*?)</script\s*>", re.IGNORECASE | re.DOTALL)
_AHK_COMMENT = re.compile(r"(?m)(^|\s);[^\r\n]*")
_AHK_KEYWORDS = {
    "if": "if",
    "while": "while",
    "for": "for",
    "catch": "catch",
    "case": "case",
    "loop": "while",
    "until": "while",
    "and": "&&",
    "or": "||",
}


@dataclass(frozen=True)
class SourceFile:
    """A validated listed file, with its watcher-facing relative path."""

    path: Path
    file_path: str
    language: str


def read_paths(root: Path, files_from: Path) -> list[SourceFile]:
    """Read, normalize, filter and deduplicate the requested source paths."""
    root = root.resolve()
    paths: list[SourceFile] = []
    seen: set[str] = set()
    for raw_path in files_from.read_text(encoding="utf-8-sig").splitlines():
        value = raw_path.strip().replace("\\", "/")
        if not value:
            continue
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            resolved = candidate.resolve()
            relative_path = resolved.relative_to(root).as_posix()
        except (OSError, ValueError):
            continue
        language = LANGUAGE_BY_EXTENSION.get(resolved.suffix.lower())
        if language is None or not resolved.is_file() or relative_path in seen:
            continue
        seen.add(relative_path)
        paths.append(SourceFile(resolved, relative_path, language))
    return paths


def prepare_source(source: str, language: str) -> str:
    """Strip non-code Svelte markup and normalize AutoHotkey for C-like parsing."""
    if language == "svelte":
        masked = list("\n" if char == "\n" else " " for char in source)
        for match in _SCRIPT_TAG.finditer(source):
            body_start, body_end = match.span(1)
            masked[body_start:body_end] = source[body_start:body_end]
        return "".join(masked)
    if language == "autohotkey":
        # Regex mapping treats semicolons after whitespace as comments, even in strings;
        # hotkey and label blocks are not functions in the C-like fallback.
        source = _AHK_COMMENT.sub(lambda match: match.group(1), source)
        keyword_pattern = re.compile(
            r"\b(" + "|".join(_AHK_KEYWORDS) + r")\b", re.IGNORECASE
        )
        return keyword_pattern.sub(
            lambda match: _AHK_KEYWORDS[match.group(0).lower()], source
        )
    # The C-like fallback does not detect Dart arrow-bodied members.
    return source


def analyzer_filename(source_file: SourceFile) -> str:
    """Choose the parser extension, using TypeScript syntax for Svelte scripts."""
    if source_file.language == "svelte":
        stem = source_file.file_path[: -len(Path(source_file.file_path).suffix)]
        return f"{stem}.ts"
    return source_file.file_path
