"""Tests for Composer dependency usage detection."""

import json
from pathlib import Path

from logger import Logger
from models import RuleStatus, Severity
from rules.context import RuleContext
from rules.php_unused_dependencies import PHPUnusedDependenciesRule


def _rule(base_path: Path, config: dict | None = None) -> PHPUnusedDependenciesRule:
    context = RuleContext(config=config or {}, base_path=base_path, logger=Logger(quiet=True))
    return PHPUnusedDependenciesRule(context)


def _project(
    root: Path,
    *,
    require: dict | None = None,
    require_dev: dict | None = None,
    packages: list[dict] | None = None,
) -> None:
    (root / "composer.json").write_text(
        json.dumps({"require": require or {}, "require-dev": require_dev or {}}), encoding="utf-8")
    (root / "composer.lock").write_text(json.dumps({"packages": packages or [], "packages-dev": []}),
                                        encoding="utf-8")


def _package(name: str, namespace: str, *, extra: dict | None = None) -> dict:
    package = {"name": name, "autoload": {"psr-4": {namespace: "src/"}}}
    if extra:
        package.update(extra)
    return package


def test_detects_simple_grouped_and_fully_qualified_uses(tmp_path: Path) -> None:
    _project(
        tmp_path,
        require={"acme/simple": "^1", "acme/grouped": "^1", "acme/fqcn": "^1", "acme/unused": "^1"},
        packages=[
            _package("acme/simple", "Simple\\"),
            _package("acme/grouped", "Grouped\\"),
            _package("acme/fqcn", "Fqcn\\"),
            _package("acme/unused", "Unused\\"),
        ],
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.php").write_text(
        "<?php\nuse Simple\\Thing;\nuse Grouped\\{One AS OneAlias, Two};\n"
        "new \\Fqcn\\Client();\n", encoding="utf-8")

    result = _rule(tmp_path).check(tmp_path)

    assert result.status == RuleStatus.OK
    assert [(v.file_path, v.rule_name, v.severity, v.message) for v in result.violations] == [
        (
            "composer.json",
            "php_unused_dependencies",
            Severity.WARNING,
            "Package 'acme/unused' is listed in composer.json dependencies but never imported in .",
        ),
    ]


def test_runtime_and_dev_dependencies_use_separate_source_roots(tmp_path: Path) -> None:
    _project(
        tmp_path,
        require={"acme/runtime": "^1", "acme/test-only": "^1"},
        require_dev={"acme/dev": "^1", "acme/unused-dev": "^1"},
        packages=[
            _package("acme/runtime", "Runtime\\"),
            _package("acme/test-only", "TestOnly\\"),
            _package("acme/dev", "Dev\\"),
            _package("acme/unused-dev", "UnusedDev\\"),
        ],
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "App.php").write_text("<?php new Runtime\\Client();", encoding="utf-8")
    (tmp_path / "tests" / "AppTest.php").write_text(
        "<?php new TestOnly\\Client(); new Dev\\Client();", encoding="utf-8")

    result = _rule(tmp_path, {"scan_paths": {"dev_dependencies": ["tests"]}}).check(tmp_path)

    assert [v.message for v in result.violations] == [
        "Package 'acme/test-only' is listed in composer.json dependencies but never imported in .",
        "Package 'acme/unused-dev' is listed in composer.json dev_dependencies but never imported in tests",
    ]


def test_dev_options_ignores_and_tool_packages_are_configurable(tmp_path: Path) -> None:
    _project(
        tmp_path,
        require={"acme/ignored": "^1", "acme/tool": "^1", "acme/ordinary": "^1"},
        require_dev={"acme/dev": "^1"},
        packages=[
            _package("acme/ignored", "Ignored\\"),
            _package("acme/tool", "Tool\\", extra={"bin": ["bin/tool"]}),
            _package("acme/ordinary", "Ordinary\\", extra={"type": "composer-plugin"}),
            _package("acme/dev", "Dev\\"),
        ],
    )
    (tmp_path / "composer.json").write_text(
        json.dumps({"require": {"acme/ignored": "^1", "acme/tool": "^1", "acme/ordinary": "^1"},
                    "require-dev": {"acme/dev": "^1"}}), encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "Test.php").write_text("<?php new Dev\\Client();", encoding="utf-8")

    result = _rule(tmp_path, {"ignore_packages": ["acme/ignored"]}).check(tmp_path)
    tool_result = _rule(tmp_path, {"ignore_packages": ["acme/ignored"], "ignore_tool_packages": False}).check(
        tmp_path)
    no_dev_result = _rule(
        tmp_path, {"ignore_packages": ["acme/ignored"], "check_dev_dependencies": False}).check(tmp_path)

    assert result.violations == []
    assert [v.message for v in tool_result.violations] == [
        "Package 'acme/ordinary' is listed in composer.json dependencies but never imported in .",
        "Package 'acme/tool' is listed in composer.json dependencies but never imported in .",
    ]
    assert no_dev_result.violations == []


def test_platform_requirements_are_not_checked(tmp_path: Path) -> None:
    _project(tmp_path, require={"php": ">=8.2", "ext-json": "*", "lib-curl": "*", "acme/app": "^1"},
             packages=[_package("acme/app", "App\\")])

    result = _rule(tmp_path).check(tmp_path)

    assert [v.message for v in result.violations] == [
        "Package 'acme/app' is listed in composer.json dependencies but never imported in .",
    ]


def test_maps_psr0_underscore_prefixes(tmp_path: Path) -> None:
    _project(
        tmp_path,
        require={"acme/legacy": "^1"},
        packages=[{"name": "acme/legacy", "autoload": {"psr-0": {"Legacy_": "src/"}}}],
    )
    (tmp_path / "Legacy.php").write_text("<?php use Legacy_Db\\Table;", encoding="utf-8")

    result = _rule(tmp_path).check(tmp_path)

    assert result.violations == []


def test_comments_and_strings_do_not_count_as_package_use(tmp_path: Path) -> None:
    _project(tmp_path, require={"acme/dep": "^1"}, packages=[_package("acme/dep", "Vendor\\Package\\")])
    (tmp_path / "app.php").write_text(
        '<?php // Vendor\\Package\\Client is mentioned here only\n'
        '$example = "Vendor\\Package\\Client";\n', encoding="utf-8")

    result = _rule(tmp_path).check(tmp_path)

    assert [v.message for v in result.violations] == [
        "Package 'acme/dep' is listed in composer.json dependencies but never imported in .",
    ]


def test_php_attributes_count_as_namespace_use(tmp_path: Path) -> None:
    _project(tmp_path, require={"acme/dep": "^1"}, packages=[_package("acme/dep", "Vendor\\Package\\")])
    (tmp_path / "app.php").write_text("<?php #[Vendor\\Package\\Marker] class App {}", encoding="utf-8")

    result = _rule(tmp_path).check(tmp_path)

    assert result.violations == []


def test_unknown_autoload_mappings_are_skipped(tmp_path: Path) -> None:
    _project(
        tmp_path,
        require={"acme/files-only": "^1", "acme/unknown": "^1"},
        packages=[
            {"name": "acme/files-only", "autoload": {"files": ["bootstrap.php"]}},
            {"name": "acme/unknown"},
        ],
    )

    result = _rule(tmp_path).check(tmp_path)

    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_vendor_installed_manifest_can_supply_mapping_without_lock(tmp_path: Path) -> None:
    (tmp_path / "composer.json").write_text(json.dumps({"require": {"acme/used": "^1"}}), encoding="utf-8")
    vendor = tmp_path / "vendor" / "composer"
    vendor.mkdir(parents=True)
    (vendor / "installed.json").write_text(
        json.dumps({"packages": [_package("acme/used", "Used\\")]}), encoding="utf-8")
    (tmp_path / "app.php").write_text("<?php new Used\\Client();", encoding="utf-8")

    result = _rule(tmp_path).check(tmp_path)

    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_vendor_tree_is_never_scanned(tmp_path: Path) -> None:
    _project(tmp_path, require={"acme/dep": "^1"}, packages=[_package("acme/dep", "Dep\\")])
    vendor = tmp_path / "vendor" / "acme" / "package"
    vendor.mkdir(parents=True)
    (vendor / "Copied.php").write_text("<?php new Dep\\Client();", encoding="utf-8")

    result = _rule(tmp_path).check(tmp_path)

    assert len(result.violations) == 1


def test_missing_manifest_or_install_data_is_skipped(tmp_path: Path) -> None:
    missing_manifest = _rule(tmp_path).check(tmp_path)
    (tmp_path / "composer.json").write_text(json.dumps({"require": {"acme/dep": "^1"}}), encoding="utf-8")
    missing_install_data = _rule(tmp_path).check(tmp_path)

    assert missing_manifest.status == RuleStatus.SKIPPED
    assert missing_manifest.message == "composer.json not found"
    assert missing_install_data.status == RuleStatus.SKIPPED
    assert missing_install_data.message == "composer.lock and vendor/composer/installed.json not found"


def test_malformed_manifest_and_lock_are_failed(tmp_path: Path) -> None:
    (tmp_path / "composer.json").write_text("{", encoding="utf-8")
    malformed_manifest = _rule(tmp_path).check(tmp_path)
    (tmp_path / "composer.json").write_text(json.dumps({"require": {}}), encoding="utf-8")
    (tmp_path / "composer.lock").write_text("{", encoding="utf-8")
    malformed_lock = _rule(tmp_path).check(tmp_path)

    assert malformed_manifest.status == RuleStatus.FAILED
    assert malformed_manifest.message.startswith("error parsing composer.json:")
    assert malformed_lock.status == RuleStatus.FAILED
    assert malformed_lock.message.startswith("error parsing composer.lock:")
