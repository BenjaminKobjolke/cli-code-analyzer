"""Tests for source copies PMD needs to recognize by extension."""

import logging
from pathlib import Path

from rules.pmd_base import copy_ino_as_cpp


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
