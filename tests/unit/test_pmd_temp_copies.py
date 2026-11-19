"""Tests for source copies PMD needs to recognize by extension."""

import logging
from pathlib import Path

from rules.pmd_base import copy_as_typescript, copy_ino_as_cpp


def test_ino_files_are_copied_as_cpp_with_original_paths_mapped(tmp_path: Path) -> None:
    sketch = tmp_path / "sketch.ino"
    source = "void setup() {\n  pinMode(LED_BUILTIN, OUTPUT);\n}\n"
    sketch.write_text(source, encoding="utf-8")
    regular_cpp = tmp_path / "library.cpp"
    regular_cpp.write_text("void loop() {}\n", encoding="utf-8")
    header = tmp_path / "library.h"
    header.write_text("void loop();\n", encoding="utf-8")

    mapping, temps = copy_ino_as_cpp([sketch, regular_cpp, header], logging.getLogger(__name__))
    try:
        assert len(temps) == 1
        assert temps[0].suffix == ".cpp"
        assert temps[0].read_text(encoding="utf-8") == source
        assert mapping == {str(temps[0]): str(sketch.resolve())}
    finally:
        for temp in temps:
            temp.unlink(missing_ok=True)


def test_javascript_family_is_copied_as_typescript_with_original_paths_mapped(tmp_path: Path) -> None:
    sources = {
        "view.tsx": "export const A = () => <b>{1}</b>;\n",
        "plain.js": "module.exports = 1;\n",
        "cli.mjs": "#!/usr/bin/env node\nconst a = 1;\n",
    }
    paths = []
    for name, source in sources.items():
        path = tmp_path / name
        path.write_text(source, encoding="utf-8")
        paths.append(path)
    already_ts = tmp_path / "model.ts"
    already_ts.write_text("export const b = 2;\n", encoding="utf-8")

    mapping, temps = copy_as_typescript([*paths, already_ts], logging.getLogger(__name__))
    try:
        assert len(temps) == 3
        assert all(temp.suffix == ".ts" for temp in temps)
        by_original = {original: temporary for temporary, original in mapping.items()}
        assert str(already_ts.resolve()) not in by_original
        view_copy = Path(by_original[str(paths[0].resolve())])
        assert view_copy.read_text(encoding="utf-8") == sources["view.tsx"]
        # A shebang line is blanked, so every other line keeps its number.
        cli_copy = Path(by_original[str(paths[2].resolve())])
        assert cli_copy.read_text(encoding="utf-8").splitlines() == ["", "const a = 1;"]
    finally:
        for temp in temps:
            temp.unlink(missing_ok=True)
