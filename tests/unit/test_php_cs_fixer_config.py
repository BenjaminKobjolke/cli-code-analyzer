import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from logger import Logger
from rules.context import RuleContext
from rules.php_cs_fixer_analyze import (
    GENERATED_FIXER_CONFIG,
    PHPCSFixerAnalyzeRule,
    git_normalizes_line_endings,
)
from rules.php_cs_fixer_report import drop_fixer_from_json

CRLF = '->setLineEnding("\\r\\n")'
LF = '->setLineEnding("\\n")'


def _rule(tmp_path: Path, config: dict | None = None) -> PHPCSFixerAnalyzeRule:
    return PHPCSFixerAnalyzeRule(
        RuleContext(config=config or {}, base_path=tmp_path, logger=Logger(quiet=True))
    )


def _git_settings(monkeypatch: pytest.MonkeyPatch, **values: str) -> None:
    monkeypatch.setattr(
        "rules.php_cs_fixer_analyze._git_config",
        lambda _base, key: values.get(key.replace("core.", ""), ""),
    )


def _generated(tmp_path: Path, config: dict | None = None) -> str:
    return _rule(tmp_path, config)._ensure_fixer_config().read_text(encoding="utf-8")


def _fixer_output(*files: tuple[str, list[str]]) -> str:
    return json.dumps({"files": [{"name": name, "appliedFixers": fixers} for name, fixers in files]})


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ({"autocrlf": "true"}, True),
        ({"autocrlf": "input"}, True),
        ({"eol": "crlf"}, True),
        ({"autocrlf": "false", "eol": "lf"}, False),
        ({}, False),
    ],
)
def test_git_normalizes_line_endings_follows_git_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings: dict, expected: bool
):
    _git_settings(monkeypatch, **settings)

    assert git_normalizes_line_endings(tmp_path) is expected


@pytest.mark.skipif(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                    reason="git is required")
def test_git_normalizes_line_endings_reads_real_repo_config(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "true"], cwd=tmp_path, check=True)

    assert git_normalizes_line_endings(tmp_path) is True


def test_git_normalizes_line_endings_is_false_without_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def missing_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("rules.php_cs_fixer_analyze.subprocess.run", missing_git)

    assert git_normalizes_line_endings(tmp_path) is False


@pytest.mark.parametrize(
    ("config", "git", "php_value", "reported"),
    [
        ({}, {"autocrlf": "true"}, LF, False),
        ({}, {}, LF, True),
        ({"line_ending": "crlf"}, {"autocrlf": "true"}, CRLF, True),
        ({"line_ending": "LF"}, {"autocrlf": "true"}, LF, True),
        ({"line_ending": "mac"}, {"autocrlf": "true"}, LF, False),
    ],
)
def test_line_ending_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: dict, git: dict, php_value: str, reported: bool
):
    _git_settings(monkeypatch, **git)
    rule = _rule(tmp_path, config)

    content = rule._ensure_fixer_config().read_text(encoding="utf-8")

    assert php_value in content
    # The line_ending fixer always stays enabled so the other fixers see normalized content
    assert "'line_ending' => false" not in content
    assert rule._reports_line_ending() is reported


def test_drop_fixer_from_json_removes_fixer_and_empty_files():
    output = _fixer_output(("a.php", ["line_ending"]), ("b.php", ["line_ending", "braces_position"]))

    assert json.loads(drop_fixer_from_json(output, "line_ending"))["files"] == [
        {"name": "b.php", "appliedFixers": ["braces_position"]}
    ]


def test_drop_fixer_from_json_keeps_unparsable_output():
    assert drop_fixer_from_json("not json", "line_ending") == "not json"


@pytest.mark.parametrize(("git", "expected"), [
    ({"autocrlf": "true"}, ["b.php"]),
    ({}, ["a.php", "b.php"]),
])
def test_line_ending_only_files_are_not_reported_when_git_normalizes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git: dict, expected: list[str]
):
    _git_settings(monkeypatch, **git)
    rule = _rule(tmp_path)
    monkeypatch.setattr(rule, "_ensure_fixer_config", lambda: tmp_path / GENERATED_FIXER_CONFIG)
    output = _fixer_output(
        (str(tmp_path / "a.php"), ["line_ending"]),
        (str(tmp_path / "b.php"), ["line_ending", "braces_position"]),
    )
    monkeypatch.setattr(rule, "_run_subprocess", lambda *_args: SimpleNamespace(stdout=output, stderr=""))

    result = rule._run_fixer_check("php-cs-fixer")

    assert [violation.file_path for violation in result.violations] == expected


def test_generated_config_is_written_to_dist_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _git_settings(monkeypatch)

    assert _rule(tmp_path)._ensure_fixer_config() == tmp_path / GENERATED_FIXER_CONFIG


def test_changed_rules_regenerate_generated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _git_settings(monkeypatch)
    _generated(tmp_path, {"rules": "@PSR12"})

    content = _generated(tmp_path, {"rules": "@PSR2"})

    assert "['@PSR2' => true]" in content
    assert "@PSR12" not in content


def test_changed_line_ending_regenerates_generated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _git_settings(monkeypatch)
    _generated(tmp_path, {"line_ending": "lf"})

    assert CRLF in _generated(tmp_path, {"line_ending": "crlf"})


def test_unchanged_settings_do_not_rewrite_generated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _git_settings(monkeypatch)
    rule = _rule(tmp_path)
    config_path = rule._ensure_fixer_config()
    # A CRLF checkout of a committed config must not count as a change
    config_path.write_bytes(config_path.read_bytes().replace(b"\n", b"\r\n"))

    assert rule._update_fixer_config(config_path, rule._generate_fixer_config(
        rule._get_exclude_paths(), rule._get_rules(), rule._get_line_ending()
    )) is False


def test_user_config_without_generated_marker_is_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _git_settings(monkeypatch)
    user_config = tmp_path / ".php-cs-fixer.php"
    user_config.write_text("<?php\nreturn (new PhpCsFixer\\Config())->setRules(['@Symfony' => true]);\n",
                           encoding="utf-8")

    assert _rule(tmp_path, {"rules": "@PSR2"})._ensure_fixer_config() == user_config
    assert "@Symfony" in user_config.read_text(encoding="utf-8")
