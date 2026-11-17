"""Tests for Python project dependency usage detection."""

from pathlib import Path

from logger import Logger
from models import RuleStatus, Severity
from rules.context import RuleContext
from rules.python_unused_dependencies import PythonUnusedDependenciesRule


def _rule(base_path: Path, config: dict | None = None) -> PythonUnusedDependenciesRule:
    context = RuleContext(config=config or {}, base_path=base_path, logger=Logger(quiet=True))
    return PythonUnusedDependenciesRule(context)


def _pyproject(root: Path, *, dependencies: list[str] | None = None,
               dev: list[str] | None = None) -> None:
    content = ["[project]", 'name = "sample"', 'version = "1.0"']
    if dependencies is not None:
        content += ["dependencies = [", *(f'    "{item}",' for item in dependencies), "]"]
    if dev is not None:
        content += ["", "[dependency-groups]", "dev = [", *(f'    "{item}",' for item in dev), "]"]
    (root / "pyproject.toml").write_text("\n".join(content), encoding="utf-8")


def _source(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _violations(result: object) -> list[tuple[str, Severity, str]]:
    return [(violation.file_path, violation.severity, violation.message)
            for violation in result.violations]


def test_pyproject_detects_runtime_and_dev_imports_and_reports_unused(tmp_path: Path) -> None:
    _pyproject(
        tmp_path,
        dependencies=["runtime-lib>=1; python_version >= '3.10'", "unused-lib[extra]>=2"],
        dev=["test-helper==1", "unused-dev"],
    )
    _source(tmp_path, "src/app.py", "import runtime_lib.submodule\n")
    _source(tmp_path, "tests/test_app.py", "from test_helper.assertions import check\n")

    result = _rule(tmp_path).check(tmp_path)

    assert result.status == RuleStatus.OK
    assert _violations(result) == [
        ("pyproject.toml", Severity.WARNING,
         "Package 'unused-lib' is listed in pyproject.toml dependencies but never imported in ."),
        ("pyproject.toml", Severity.WARNING,
         "Package 'unused-dev' is listed in pyproject.toml dev_dependencies but never imported in tests, test"),
    ]


def test_comma_separated_imports_mark_every_package_used(tmp_path: Path) -> None:
    _pyproject(tmp_path, dependencies=["first-package", "second-package"])
    _source(tmp_path, "app.py", "import first_package, second_package\n")

    result = _rule(tmp_path).check(tmp_path)

    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_requirements_and_dev_requirements_skip_options_comments_and_urls(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text(
        "# ordinary comment\nrequests[security]>=2.0; python_version > '3'\n"
        "-r included.txt\n-e .\n--index-url https://packages.example/simple\n"
        "https://example.invalid/archive.whl\nunused_pkg==1 # inline comment\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements-dev.txt").write_text("pytest>=8\nunused-test\n", encoding="utf-8")
    _source(tmp_path, "app.py", "import requests\n")
    _source(tmp_path, "tests/test_app.py", "import pytest\n")

    result = _rule(tmp_path).check(tmp_path)

    assert result.status == RuleStatus.OK
    assert _violations(result) == [
        ("requirements.txt", Severity.WARNING,
         "Package 'unused-pkg' is listed in requirements.txt dependencies but never imported in ."),
        ("requirements-dev.txt", Severity.WARNING,
         "Package 'unused-test' is listed in requirements-dev.txt dev_dependencies but never imported in tests, test"),
    ]


def test_dependency_names_normalize_and_known_import_aliases_are_mapped(tmp_path: Path) -> None:
    names = ["PyYAML", "Pillow", "beautifulsoup4", "python-dateutil", "scikit-learn",
             "opencv-python", "python-dotenv", "attrs"]
    _pyproject(tmp_path, dependencies=[f"{name}>=1" for name in names])
    imports = ["yaml", "PIL", "bs4", "dateutil", "sklearn", "cv2", "dotenv", "attr"]
    _source(tmp_path, "app.py", "\n".join(f"import {name}" for name in imports))

    result = _rule(tmp_path).check(tmp_path)

    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_site_packages_metadata_maps_top_level_and_record_names(tmp_path: Path) -> None:
    _pyproject(tmp_path, dependencies=["metadata-name", "record-name"])
    site_packages = tmp_path / ".venv" / "Lib" / "site-packages"
    top_level = site_packages / "metadata_name-1.0.dist-info"
    top_level.mkdir(parents=True)
    (top_level / "top_level.txt").write_text("actual_import\n", encoding="utf-8")
    record = site_packages / "record_name-2.0.dist-info"
    record.mkdir(parents=True)
    (record / "RECORD").write_text("record_import/__init__.py,,\n", encoding="utf-8")
    _source(tmp_path, "app.py", "import actual_import\nimport record_import.child\n")

    result = _rule(tmp_path).check(tmp_path)

    assert result.violations == []


def test_configured_import_names_override_fallback_mapping(tmp_path: Path) -> None:
    _pyproject(tmp_path, dependencies=["acme-widget"])
    _source(tmp_path, "app.py", "from acme.custom import Widget\n")

    result = _rule(tmp_path, {"import_names": {"acme-widget": ["acme.custom"]}}).check(tmp_path)

    assert result.violations == []


def test_console_scripts_are_exempt_by_default_and_can_be_checked(tmp_path: Path) -> None:
    _pyproject(tmp_path, dependencies=["command-line-tool", "unused-lib"])
    dist_info = tmp_path / "venv" / "Lib" / "site-packages" / "command_line_tool-1.0.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "entry_points.txt").write_text("[console_scripts]\nmy-tool = tool:main\n", encoding="utf-8")

    exempt = _rule(tmp_path).check(tmp_path)
    checked = _rule(tmp_path, {"ignore_tool_packages": False}).check(tmp_path)

    assert [v.message for v in exempt.violations] == [
        "Package 'unused-lib' is listed in pyproject.toml dependencies but never imported in .",
    ]
    assert [v.message for v in checked.violations] == [
        "Package 'command-line-tool' is listed in pyproject.toml dependencies but never imported in .",
        "Package 'unused-lib' is listed in pyproject.toml dependencies but never imported in .",
    ]


def test_default_tool_ignores(tmp_path: Path) -> None:
    _pyproject(tmp_path, dependencies=["pytest", "ruff", "ordinary-lib", "ignored-lib"])
    result = _rule(tmp_path).check(tmp_path)

    assert [v.message for v in result.violations] == [
        "Package 'ignored-lib' is listed in pyproject.toml dependencies but never imported in .",
        "Package 'ordinary-lib' is listed in pyproject.toml dependencies but never imported in .",
    ]


def test_configured_ignore_list_is_respected(tmp_path: Path) -> None:
    _pyproject(tmp_path, dependencies=["ignored-lib", "ordinary-lib"])
    result = _rule(tmp_path, {"ignore_packages": ["IGNORED_lib"]}).check(tmp_path)

    assert [v.message for v in result.violations] == [
        "Package 'ordinary-lib' is listed in pyproject.toml dependencies but never imported in .",
    ]


def test_check_dev_dependencies_can_be_disabled(tmp_path: Path) -> None:
    _pyproject(tmp_path, dependencies=["runtime-lib"], dev=["unused-dev"])
    result = _rule(tmp_path, {"check_dev_dependencies": False}).check(tmp_path)

    assert [v.message for v in result.violations] == [
        "Package 'runtime-lib' is listed in pyproject.toml dependencies but never imported in .",
    ]


def test_missing_manifest_is_skipped_and_invalid_toml_fails(tmp_path: Path) -> None:
    missing = _rule(tmp_path).check(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project\ndependencies = [", encoding="utf-8")
    invalid = _rule(tmp_path).check(tmp_path)

    assert missing.status == RuleStatus.SKIPPED
    assert missing.message == "Python dependency manifest not found"
    assert invalid.status == RuleStatus.FAILED
    assert invalid.message.startswith("error parsing pyproject.toml:")


def test_malformed_python_source_is_ignored_while_other_files_are_scanned(tmp_path: Path) -> None:
    _pyproject(tmp_path, dependencies=["used-lib", "unused-lib"])
    _source(tmp_path, "app.py", "import used_lib\n")
    _source(tmp_path, "broken.py", "def invalid(:\n")

    result = _rule(tmp_path).check(tmp_path)

    assert result.status == RuleStatus.OK
    assert [v.message for v in result.violations] == [
        "Package 'unused-lib' is listed in pyproject.toml dependencies but never imported in .",
    ]


def test_absolute_imports_only_and_runtime_scan_skips_test_and_environment_dirs(tmp_path: Path) -> None:
    _pyproject(tmp_path, dependencies=["runtime-lib", "test-only-lib", "environment-lib"])
    _source(tmp_path, "src/app.py", "from runtime_lib import Client\nfrom .local import helper\n")
    _source(tmp_path, "tests/test_app.py", "import test_only_lib\n")
    _source(tmp_path, "venv/Lib/site-packages/environment_lib/__init__.py", "")

    result = _rule(tmp_path).check(tmp_path)

    assert [v.message for v in result.violations] == [
        "Package 'environment-lib' is listed in pyproject.toml dependencies but never imported in .",
        "Package 'test-only-lib' is listed in pyproject.toml dependencies but never imported in .",
    ]
