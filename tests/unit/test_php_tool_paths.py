from pathlib import Path

import pytest

from logger import Logger
from rules.context import RuleContext
from rules.php_cs_fixer_analyze import PHPCSFixerAnalyzeRule
from rules.php_tool_paths import get_bundled_php_tool_path
from rules.phpstan_analyze import PHPStanAnalyzeRule


def test_bundled_php_tool_path_prefers_windows_launcher(tmp_path: Path):
    bin_dir = tmp_path / "php" / "vendor" / "bin"
    bin_dir.mkdir(parents=True)
    windows_path = bin_dir / "phpmd.bat"
    unix_path = bin_dir / "phpmd"
    windows_path.touch()
    unix_path.touch()

    assert get_bundled_php_tool_path("phpmd", tmp_path) == str(windows_path)


def test_bundled_php_tool_path_finds_unix_launcher(tmp_path: Path):
    bin_dir = tmp_path / "php" / "vendor" / "bin"
    bin_dir.mkdir(parents=True)
    unix_path = bin_dir / "php-cs-fixer"
    unix_path.touch()

    assert get_bundled_php_tool_path("php-cs-fixer", tmp_path) == str(unix_path)


def test_bundled_php_tool_path_returns_none_when_missing(tmp_path: Path):
    assert get_bundled_php_tool_path("phpstan", tmp_path) is None


@pytest.mark.parametrize(
    ("module_name", "rule_type", "tool_name", "runner_name"),
    [
        ("rules.phpstan_analyze", PHPStanAnalyzeRule, "phpstan", "_run_phpstan_check"),
        ("rules.php_cs_fixer_analyze", PHPCSFixerAnalyzeRule, "php-cs-fixer", "_run_fixer_check"),
    ],
)
def test_php_analyzers_prefer_bundled_tools_to_global_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    rule_type: type,
    tool_name: str,
    runner_name: str,
):
    rule = rule_type(RuleContext(
        config={}, base_path=tmp_path, logger=Logger(quiet=True)
    ))
    bundled = f"bundled/{tool_name}"
    monkeypatch.setattr(
        f"{module_name}.get_bundled_php_tool_path", lambda name: bundled if name == tool_name else None
    )
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: pytest.fail("global lookup should not run"))
    monkeypatch.setattr(rule, runner_name, lambda path: path)

    assert rule._run(tmp_path / "src" / "Example.php") == bundled
