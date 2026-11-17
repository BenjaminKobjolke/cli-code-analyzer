"""Characterization tests for the project-wide Dart dependency check."""

from pathlib import Path

from logger import Logger
from models import RuleStatus, Severity
from rules.context import RuleContext
from rules.dart_unused_dependencies import DartUnusedDependenciesRule


def _rule(base_path: Path, config: dict | None = None) -> DartUnusedDependenciesRule:
    context = RuleContext(config=config or {}, base_path=base_path, logger=Logger(quiet=True))
    return DartUnusedDependenciesRule(context)


def test_reports_unused_runtime_and_dev_dependencies_with_manifest_path(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text(
        "dependencies:\n  used_runtime: ^1.0.0\n  unused_runtime: ^1.0.0\n"
        "dev_dependencies:\n  used_dev: ^1.0.0\n  unused_dev: ^1.0.0\n",
        encoding="utf-8",
    )
    (tmp_path / "lib").mkdir()
    (tmp_path / "test").mkdir()
    (tmp_path / "lib" / "app.dart").write_text(
        "import 'package:used_runtime/app.dart';\n", encoding="utf-8")
    (tmp_path / "test" / "app_test.dart").write_text(
        "import 'package:used_dev/test.dart';\n", encoding="utf-8")

    result = _rule(tmp_path, {"ignore_packages": []}).check(tmp_path)

    assert result.status == RuleStatus.OK
    assert [(v.file_path, v.rule_name, v.severity, v.message) for v in result.violations] == [
        (
            "pubspec.yaml",
            "dart_unused_dependencies",
            Severity.WARNING,
            "Package 'unused_runtime' is listed in pubspec.yaml dependencies but never imported in lib",
        ),
        (
            "pubspec.yaml",
            "dart_unused_dependencies",
            Severity.WARNING,
            "Package 'unused_dev' is listed in pubspec.yaml dev_dependencies but never imported in test, integration_test",
        ),
    ]


def test_ignore_packages_and_disabled_dev_dependencies_are_respected(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text(
        "dependencies:\n  ignored: ^1.0.0\ndev_dependencies:\n  unused_dev: ^1.0.0\n",
        encoding="utf-8",
    )

    result = _rule(tmp_path, {"ignore_packages": ["ignored"], "check_dev_dependencies": False}).check(
        tmp_path)

    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_missing_manifest_is_skipped(tmp_path: Path) -> None:
    result = _rule(tmp_path).check(tmp_path)

    assert result.status == RuleStatus.SKIPPED
    assert result.message == "pubspec.yaml not found"


def test_malformed_manifest_is_failed(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text("dependencies: [", encoding="utf-8")

    result = _rule(tmp_path).check(tmp_path)

    assert result.status == RuleStatus.FAILED
    assert result.message.startswith("error parsing pubspec.yaml:")
