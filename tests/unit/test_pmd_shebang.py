"""Shebang sanitization for PMD CPD (ecmascript lexer chokes on #! lines).

sanitize_shebang_files must copy shebang-led files to temp copies with the
shebang replaced by an empty line (preserving all other line numbers) and
leave non-shebang files alone.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rules.pmd_base import sanitize_shebang_files

logger = logging.getLogger(__name__)


def _cleanup(temps):
    for t in temps:
        t.unlink(missing_ok=True)


def test_shebang_file_sanitized_and_line_numbers_preserved(tmp_path):
    src = tmp_path / "main.js"
    src.write_text("#!/usr/bin/env bun\nconst a = 1;\nconst b = 2;\n", encoding="utf-8")

    mapping, temps = sanitize_shebang_files([src], logger)
    try:
        assert len(temps) == 1
        assert mapping == {str(temps[0]): str(src.resolve())}
        assert temps[0].suffix == ".js"
        lines = temps[0].read_text(encoding="utf-8").splitlines()
        assert lines == ["", "const a = 1;", "const b = 2;"]
    finally:
        _cleanup(temps)


def test_non_shebang_file_untouched(tmp_path):
    src = tmp_path / "plain.js"
    src.write_text("const a = 1;\n", encoding="utf-8")

    mapping, temps = sanitize_shebang_files([src], logger)
    assert mapping == {}
    assert temps == []
