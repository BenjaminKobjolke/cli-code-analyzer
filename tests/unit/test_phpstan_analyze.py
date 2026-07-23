from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from rules.context import RuleContext
from rules.phpstan_analyze import PHPStanAnalyzeRule
from rules.phpstan_config import build_phpstan_config


def _rule(tmp_path: Path, config: dict, filter_files=None) -> PHPStanAnalyzeRule:
    return PHPStanAnalyzeRule(RuleContext(
        config=config,
        base_path=tmp_path,
        filter_files=filter_files,
        logger=Logger(quiet=True),
    ))


def test_build_phpstan_config_includes_project_config_and_excludes(tmp_path: Path):
    neon = build_phpstan_config(
        tmp_path / "phpstan.neon",
        [(tmp_path / "tools" / "phpstan-bootstrap.php").as_posix()],
        [(tmp_path / "vendor").as_posix()],
    )

    assert "includes:" in neon
    assert f"- {(tmp_path / 'phpstan.neon').as_posix()}" in neon
    assert "bootstrapFiles:" in neon
    assert f"- {(tmp_path / 'tools' / 'phpstan-bootstrap.php').as_posix()}" in neon
    assert "excludePaths:" in neon
    assert f"- {(tmp_path / 'vendor').as_posix()} (?)" in neon


def test_run_phpstan_uses_bootstrap_files_with_changed_file_scope(tmp_path: Path):
    bootstrap = tmp_path / "tools" / "phpstan-bootstrap.php"
    bootstrap.parent.mkdir()
    bootstrap.write_text("<?php\n", encoding="utf-8")
    changed = tmp_path / "src" / "Changed.php"
    changed.parent.mkdir()
    changed.write_text("<?php\n", encoding="utf-8")

    rule = _rule(
        tmp_path,
        {
            "level": 5,
            "bootstrap_files": ["tools/phpstan-bootstrap.php"],
            "exclude_patterns": ["vendor/**"],
        },
        filter_files={"src/Changed.php"},
    )

    seen = {}

    def fake_run(cmd, *_args, **_kwargs):
        seen["cmd"] = cmd
        config_path = Path(cmd[cmd.index("-c") + 1])
        seen["config"] = config_path.read_text(encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout='{"totals":{"errors":0,"file_errors":0},"files":[]}', stderr="")

    rule._run_subprocess = fake_run

    result = rule._run_phpstan_check("phpstan")

    assert result.violations == []
    assert "-c" in seen["cmd"]
    assert str(changed) in seen["cmd"]
    assert "bootstrapFiles:" in seen["config"]
    assert f"- {bootstrap.as_posix()}" in seen["config"]
    assert f"- {(tmp_path / 'vendor').as_posix()} (?)" in seen["config"]
