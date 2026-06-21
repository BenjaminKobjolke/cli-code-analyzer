"""Integration specs wiring AutoHotkey into the analyzer pipeline.

No real AHK interpreter: autohotkey_analyze's tool lookup is stubbed to None so
it skips cleanly. Asserts language registration, file discovery (.ahk/.ah2/.ahk2),
the `ahk` alias, and that the language-agnostic max_lines_per_file fires on .ahk.
"""
import json

from analyzer import AnalyzerConfig, CodeAnalyzer
from analyzer_registry import LANGUAGE_ALIASES, get_analyzers_for_language
from file_discovery import FileDiscovery
from logger import Logger


def test_autohotkey_registered_and_aliased():
    names = [n for n, _d, _r in get_analyzers_for_language("autohotkey")]
    assert "autohotkey_analyze" in names
    assert "max_lines_per_file" in names
    assert LANGUAGE_ALIASES["ahk"] == "autohotkey"


def test_discovery_finds_all_ahk_extensions(tmp_path):
    for name in ("a.ahk", "b.ah2", "c.ahk2", "ignore.txt"):
        (tmp_path / name).write_text("ExitApp\n", encoding="utf-8")
    found = {p.name for p in FileDiscovery(["autohotkey"], str(tmp_path)).discover()}
    assert found == {"a.ahk", "b.ah2", "c.ahk2"}


def test_max_lines_fires_on_ahk_and_validate_skips(tmp_path, monkeypatch):
    # No interpreter -> autohotkey_analyze skips, but max_lines still runs.
    from rules.autohotkey_analyze import AutoHotkeyAnalyzeRule
    monkeypatch.setattr(AutoHotkeyAnalyzeRule, "_get_tool_path", lambda *a, **k: None)

    big = tmp_path / "big.ahk"
    big.write_text("\n".join(f"; line {i}" for i in range(600)) + "\n", encoding="utf-8")

    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps({
        "max_lines_per_file": {"enabled": True, "warning": 300, "error": 500},
        "autohotkey_analyze": {"enabled": True},
    }), encoding="utf-8")

    analyzer = CodeAnalyzer(AnalyzerConfig(
        languages="autohotkey",
        path=str(tmp_path),
        rules_file=str(rules_file),
        logger=Logger(quiet=True),
    ))
    analyzer.analyze()

    assert analyzer.get_file_count() == 1
    assert any(v.rule_name == "max_lines_per_file" for v in analyzer.violations)
    # autohotkey_analyze skipped (no interpreter) -> not a hard failure
    assert not any("autohotkey_analyze" in f.rule_name for f in analyzer.get_failures())
