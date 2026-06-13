"""Cross-language integration tests for PMD duplicate detection.

PMD CPD is the one analyzer that runs for every supported language, and its
namespaced-XML parse was the original silent bug. These tests lock the `{*}`
namespace fix per language by running the real CLI against duplicated-code
fixtures and asserting duplicates are actually reported.

The whole PMD detection set skips cleanly when PMD is not configured, so a
machine without PMD never fails CI.

NOTE on coverage: native per-language tool runners (eslint/tsc for JS/TS,
svelte-check, dotnet build for C#) need npm install / project scaffolding and
are intentionally NOT added here — those languages' duplicate-detection path is
covered by the PMD cases below. Add native runners later with a provisioned
toolchain.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"


def _pmd_available() -> bool:
    if shutil.which("pmd"):
        return True
    from settings import Settings
    p = Settings().get_pmd_path()
    if not p:
        return False
    pp = Path(p)
    if not pp.is_absolute():
        pp = ROOT / p
    return pp.exists()


pmd_required = pytest.mark.skipif(not _pmd_available(), reason="PMD not configured/available")


def _ext_map(language: str) -> str:
    return {
        "php": "php", "python": "py", "flutter": "dart",
        "csharp": "cs", "javascript": "js", "svelte": "svelte",
    }[language]


def _run_pmd_json(language: str, fixture_dir: Path, focus_file: Path, tmp_path: Path):
    """Run the CLI with only pmd_duplicates enabled, returning parsed JSON.

    --file silences logger output (quiet mode) so stdout is pure JSON.
    """
    rules = {"pmd_duplicates": {"enabled": True, "minimum_tokens": 50}}
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(rules), encoding="utf-8")
    cmd = [
        sys.executable, str(ROOT / "main.py"),
        "--language", language,
        "--path", str(fixture_dir),
        "--rules", str(rules_file),
        "--format", "json",
        "--file", str(focus_file),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    # stdout is pure JSON under --file quiet mode; be defensive anyway.
    text = result.stdout.strip()
    start = text.find("{")
    assert start != -1, f"no JSON in stdout for {language}; stdout={result.stdout[:500]} stderr={result.stderr[:300]}"
    return json.loads(text[start:]), result


# php/python/dart/csharp/javascript all tokenize cleanly under CPD; svelte does not
# (CPD ecmascript can't parse .svelte script blocks), so it is tested separately.
DUP_LANGUAGES = ["php", "python", "flutter", "csharp", "javascript"]


@pmd_required
@pytest.mark.parametrize("language", DUP_LANGUAGES)
def test_pmd_detects_duplicates_per_language(language, tmp_path):
    fixture = FIXTURES / language
    focus = fixture / f"a.{_ext_map(language)}"
    data, result = _run_pmd_json(language, fixture, focus, tmp_path)

    dups = [v for v in data["violations"] if v["rule_name"] == "pmd_duplicates"]
    assert dups, (
        f"{language}: expected pmd_duplicates violations (namespace regression?); "
        f"violations={data['violations']} stderr={result.stderr[:300]}"
    )
    assert not data.get("failures"), f"{language}: unexpected tool failure {data.get('failures')}"


@pmd_required
def test_pmd_svelte_runs_without_tool_failure(tmp_path):
    """CPD cannot tokenize .svelte for duplication, but the rule must still run
    cleanly (status OK, no crash) — not report a false FAILED."""
    fixture = FIXTURES / "svelte"
    data, result = _run_pmd_json("svelte", fixture, fixture / "a.svelte", tmp_path)
    assert not data.get("failures"), f"svelte: unexpected tool failure {data.get('failures')}"


def test_pmd_missing_binary_surfaces_failure(tmp_path, monkeypatch):
    """When PMD cannot be resolved, the rule must FAIL (not silently pass).

    In-process so it does not depend on PMD being installed and does not mutate
    the shared settings.ini.
    """
    from analyzer import AnalyzerConfig, CodeAnalyzer
    from logger import Logger
    from models import Severity
    from rules.pmd_duplicates import PMDDuplicatesRule

    monkeypatch.setattr(PMDDuplicatesRule, "_get_tool_path", lambda *a, **k: None)

    (tmp_path / "a.php").write_text("<?php\n$a = 1;\n", encoding="utf-8")
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps({"pmd_duplicates": {"enabled": True}}), encoding="utf-8")

    analyzer = CodeAnalyzer(AnalyzerConfig(
        languages="php",
        path=str(tmp_path),
        rules_file=str(rules_file),
        logger=Logger(quiet=True),
    ))
    analyzer.analyze()

    failures = analyzer.get_failures()
    assert any(f.rule_name == "pmd_duplicates" for f in failures), "expected pmd_duplicates FAILED"
    assert any(
        v.severity == Severity.ERROR and "pmd_duplicates" in v.rule_name
        for v in analyzer.violations
    ), "expected a mirrored ERROR violation for the failure"
