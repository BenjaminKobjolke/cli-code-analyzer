import csv
from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from models import RuleStatus
from rules.context import RuleContext
from rules.intelephense_analyze import IntelephenseAnalyzeRule


def _rule(tmp_path: Path, output_folder: Path | None = None) -> IntelephenseAnalyzeRule:
    return IntelephenseAnalyzeRule(
        RuleContext(
            config={},
            base_path=tmp_path,
            output_folder=output_folder,
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
