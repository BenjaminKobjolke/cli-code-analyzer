import csv
from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from models import RuleStatus
from rules.context import RuleContext
from rules.intelephense_analyze import IntelephenseAnalyzeRule


def _rule(
    tmp_path: Path,
    output_folder: Path | None = None,
    filter_files: set[str] | None = None,
    max_errors: int | None = None,
) -> IntelephenseAnalyzeRule:
    return IntelephenseAnalyzeRule(
        RuleContext(
            config={},
            base_path=tmp_path,
            output_folder=output_folder,
            filter_files=filter_files,
            max_errors=max_errors,
            logger=Logger(quiet=True),
        )
    )


def _diagnostics():
    return [
        SimpleNamespace(
            file_path=".php-cs-fixer.dist.php",
            line=6,
            column=10,
            severity="error",
            message="Undefined type 'PhpCsFixer\\Finder'.",
        ),
        SimpleNamespace(
            file_path="classes/xida/ai/apps/.php-cs-fixer.dist.php",
            line=10,
            column=10,
            severity="error",
            message="Undefined type 'PhpCsFixer\\Config'.",
        ),
        SimpleNamespace(
            file_path="src/Service.php",
            line=4,
            column=8,
            severity="error",
            message="Undefined variable '$service'.",
        ),
    ]


def test_generated_fixer_configs_are_excluded_from_violations(tmp_path: Path):
    rule = _rule(tmp_path)

    result = rule._run_intelephense_check(lambda **_kwargs: _diagnostics())

    assert result.status == RuleStatus.OK
    assert [violation.file_path for violation in result.violations] == ["src/Service.php"]


def test_generated_fixer_configs_are_excluded_from_csv(tmp_path: Path):
    output_folder = tmp_path / "reports"
    output_folder.mkdir()
    rule = _rule(tmp_path, output_folder)

    result = rule._run_intelephense_check(lambda **_kwargs: _diagnostics())

    assert result.status == RuleStatus.OK
    with (output_folder / "intelephense_analyze.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [row["file"] for row in rows] == ["src/Service.php"]


def test_filter_keeps_only_changed_php_diagnostics_before_limit_and_csv(tmp_path: Path):
    output_folder = tmp_path / "reports"
    output_folder.mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "src/Changed.php").write_text("<?php\n", encoding="utf-8")
    (tmp_path / "src/Other.php").write_text("<?php\n", encoding="utf-8")
    rule = _rule(
        tmp_path,
        output_folder,
        filter_files={"src/Changed.php"},
        max_errors=1,
    )
    diagnostics = [
        SimpleNamespace(
            file_path="src/Other.php",
            line=1,
            column=1,
            severity="error",
            message="Unchanged finding",
        ),
        SimpleNamespace(
            file_path="src/Changed.php",
            line=2,
            column=3,
            severity="error",
            message="Changed finding",
        ),
    ]

    result = rule._run_intelephense_check(lambda **_kwargs: diagnostics)

    assert result.status == RuleStatus.OK
    assert [violation.file_path for violation in result.violations] == ["src/Changed.php"]
    with (output_folder / "intelephense_analyze.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [row["file"] for row in rows] == ["src/Changed.php"]


def test_filter_skips_intelephense_when_no_changed_php_is_in_scope(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/Changed.js").write_text("const value = 1;\n", encoding="utf-8")
    rule = _rule(tmp_path, filter_files={"src/Changed.js"})
    calls = []

    result = rule._run_intelephense_check(lambda **_kwargs: calls.append(True))

    assert result.status == RuleStatus.OK
    assert result.violations == []
    assert calls == []


def test_filter_skips_intelephense_for_excluded_changed_php(tmp_path: Path):
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor/Changed.php").write_text("<?php\n", encoding="utf-8")
    rule = _rule(tmp_path, filter_files={"vendor/Changed.php"})
    calls = []

    result = rule._run_intelephense_check(lambda **_kwargs: calls.append(True))

    assert result.status == RuleStatus.OK
    assert result.violations == []
    assert calls == []
