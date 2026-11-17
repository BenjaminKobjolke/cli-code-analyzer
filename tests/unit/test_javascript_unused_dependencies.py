"""Tests for JavaScript, TypeScript, and Svelte dependency usage detection."""

import json
from pathlib import Path

from logger import Logger
from models import RuleStatus, Severity
from rules.context import RuleContext
from rules.javascript_unused_dependencies import JavaScriptUnusedDependenciesRule


def _rule(base_path: Path, config: dict | None = None) -> JavaScriptUnusedDependenciesRule:
    context = RuleContext(config=config or {}, base_path=base_path, logger=Logger(quiet=True))
    return JavaScriptUnusedDependenciesRule(context)


def _manifest(
    root: Path,
    *,
    dependencies: dict[str, str] | None = None,
    dev_dependencies: dict[str, str] | None = None,
    **extra: object,
) -> None:
    data = {
        "dependencies": dependencies or {},
        "devDependencies": dev_dependencies or {},
        **extra,
    }
    (root / "package.json").write_text(json.dumps(data), encoding="utf-8")


def _source(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _messages(result: object) -> list[str]:
    return [violation.message for violation in result.violations]


def test_detects_esm_require_dynamic_reexport_side_effect_and_scoped_deep_imports(
    tmp_path: Path,
) -> None:
    dependencies = {
        "esm-lib": "^1", "required-lib": "^1", "dynamic-lib": "^1", "reexport-lib": "^1",
        "side-effect-lib": "^1", "@scope/core": "^1", "@scope/unused": "^1",
        "unused-lib": "^1",
    }
    _manifest(tmp_path, dependencies=dependencies)
    _source(tmp_path, "src/app.js", "import { run } from 'esm-lib/sub/path'; run();\n")
    _source(tmp_path, "src/required.cjs", "const required = require('required-lib');\n")
    _source(tmp_path, "src/dynamic.mjs", "await import('dynamic-lib/feature');\n")
    _source(tmp_path, "src/reexport.ts", "export { value } from 'reexport-lib';\n")
    _source(tmp_path, "src/effects.jsx", "import 'side-effect-lib/register';\n")
    _source(tmp_path, "src/scoped.tsx", "import Thing from '@scope/core/deep';\n")

    result = _rule(tmp_path).check(tmp_path)

    assert result.status == RuleStatus.OK
    assert [(v.file_path, v.rule_name, v.severity) for v in result.violations] == [
        ("package.json", "javascript_unused_dependencies", Severity.WARNING),
        ("package.json", "javascript_unused_dependencies", Severity.WARNING),
    ]
    assert _messages(result) == [
        "Package '@scope/unused' is listed in package.json dependencies but never imported in .",
        "Package 'unused-lib' is listed in package.json dependencies but never imported in .",
    ]


def test_scans_svelte_imports_and_typescript_extension_forms(tmp_path: Path) -> None:
    _manifest(tmp_path, dependencies={"svelte-lib": "^1", "types-lib": "^1", "unused-lib": "^1"})
    _source(tmp_path, "src/App.svelte", "<script>import Widget from 'svelte-lib/widget';</script>\n")
    _source(tmp_path, "src/types.mts", "import type { Shape } from 'types-lib';\n")
    _source(tmp_path, "src/node.cts", "const plugin = require('types-lib/plugin');\n")

    result = _rule(tmp_path).check(tmp_path)

    assert _messages(result) == [
        "Package 'unused-lib' is listed in package.json dependencies but never imported in .",
    ]


def test_scans_dev_dependencies_in_test_paths_but_not_as_runtime_use(tmp_path: Path) -> None:
    _manifest(
        tmp_path,
        dependencies={"runtime-lib": "^1", "test-only-runtime": "^1"},
        dev_dependencies={"test-lib": "^1", "unused-dev": "^1"},
    )
    _source(tmp_path, "src/app.js", "import 'runtime-lib';\n")
    _source(tmp_path, "tests/app.test.ts", "import 'test-only-runtime'; import 'test-lib';\n")

    result = _rule(tmp_path).check(tmp_path)

    assert _messages(result) == [
        "Package 'test-only-runtime' is listed in package.json dependencies but never imported in .",
        "Package 'unused-dev' is listed in package.json devDependencies but never imported in tests, test",
    ]


def test_config_files_and_tsconfig_package_references_count_as_use(tmp_path: Path) -> None:
    _manifest(
        tmp_path,
        dependencies={"runtime-config": "^1", "ts-base": "^1"},
        dev_dependencies={"vite": "^1", "vitest": "^1", "@types/node-types": "^1", "unused": "^1"},
    )
    _source(tmp_path, "vite.config.ts", "import { defineConfig } from 'vite'; export default defineConfig({});\n")
    _source(tmp_path, "vitest.config.mjs", "export { defineConfig } from 'vitest/config';\n")
    _source(tmp_path, "tsconfig.json", json.dumps({"extends": "ts-base/tsconfig.json", "compilerOptions": {"types": ["node-types"]}}))
    _source(tmp_path, "src/app.js", "import 'runtime-config';\n")

    result = _rule(tmp_path).check(tmp_path)

    assert _messages(result) == [
        "Package 'unused' is listed in package.json devDependencies but never imported in tests, test",
    ]


def test_types_packages_pair_with_runtime_package_and_node_types_need_typescript(tmp_path: Path) -> None:
    _manifest(
        tmp_path,
        dependencies={"@types/used-lib": "^1", "@types/unused-lib": "^1", "@types/node": "^1"},
    )
    _source(tmp_path, "src/app.ts", "import { run } from 'used-lib'; run();\n")
    _source(tmp_path, "src/app.js", "const fs = require('fs');\n")

    result = _rule(tmp_path).check(tmp_path)

    assert _messages(result) == [
        "Package '@types/unused-lib' is listed in package.json dependencies but never imported in .",
    ]


def test_bin_and_script_tools_are_exempt_by_default_and_can_be_checked(tmp_path: Path) -> None:
    _manifest(
        tmp_path,
        dependencies={"bin-tool": "^1", "script-tool": "^1", "ordinary-lib": "^1"},
        scripts={"build": "script-tool build"},
    )
    bin_package = tmp_path / "node_modules" / "bin-tool"
    bin_package.mkdir(parents=True)
    (bin_package / "package.json").write_text(json.dumps({"name": "bin-tool", "bin": "./cli.js"}),
                                                  encoding="utf-8")

    result = _rule(tmp_path).check(tmp_path)
    checked = _rule(tmp_path, {"ignore_tool_packages": False}).check(tmp_path)

    assert _messages(result) == [
        "Package 'ordinary-lib' is listed in package.json dependencies but never imported in .",
    ]
    assert _messages(checked) == [
        "Package 'bin-tool' is listed in package.json dependencies but never imported in .",
        "Package 'ordinary-lib' is listed in package.json dependencies but never imported in .",
        "Package 'script-tool' is listed in package.json dependencies but never imported in .",
    ]


def test_default_sveltekit_plugin_ignores_and_configured_ignores(tmp_path: Path) -> None:
    _manifest(
        tmp_path,
        dependencies={"@sveltejs/adapter-auto": "^1", "@sveltejs/vite-plugin-svelte": "^1",
                      "ordinary-lib": "^1"},
    )

    result = _rule(tmp_path).check(tmp_path)

    assert _messages(result) == [
        "Package 'ordinary-lib' is listed in package.json dependencies but never imported in .",
    ]

    _manifest(tmp_path, dependencies={"ignored-lib": "^1", "ordinary-lib": "^1"})
    configured = _rule(tmp_path, {"ignore_packages": ["ignored-lib"]}).check(tmp_path)
    assert _messages(configured) == [
        "Package 'ordinary-lib' is listed in package.json dependencies but never imported in .",
    ]


def test_scan_paths_and_dev_check_can_be_configured(tmp_path: Path) -> None:
    _manifest(tmp_path, dependencies={"ignored-runtime": "^1", "unused-runtime": "^1"},
              dev_dependencies={"unused-dev": "^1"})
    _source(tmp_path, "custom/app.js", "import 'ignored-runtime';\n")

    runtime = _rule(tmp_path, {
        "scan_paths": {"dependencies": ["custom"]}, "check_dev_dependencies": False,
    }).check(tmp_path)
    disabled_dev = _rule(tmp_path, {"check_dev_dependencies": False}).check(tmp_path)

    assert _messages(runtime) == [
        "Package 'unused-runtime' is listed in package.json dependencies but never imported in custom",
    ]
    assert _messages(disabled_dev) == [
        "Package 'unused-runtime' is listed in package.json dependencies but never imported in .",
    ]


def test_ignores_build_and_dependency_directories(tmp_path: Path) -> None:
    _manifest(tmp_path, dependencies={"bundled-only": "^1", "used-lib": "^1"})
    _source(tmp_path, "src/app.js", "import 'used-lib';\n")
    _source(tmp_path, "node_modules/other/index.js", "import 'bundled-only';\n")
    _source(tmp_path, "dist/app.js", "import 'bundled-only';\n")
    _source(tmp_path, ".svelte-kit/output.js", "import 'bundled-only';\n")

    result = _rule(tmp_path).check(tmp_path)

    assert _messages(result) == [
        "Package 'bundled-only' is listed in package.json dependencies but never imported in .",
    ]


def test_missing_manifest_is_skipped_and_malformed_manifest_fails(tmp_path: Path) -> None:
    missing = _rule(tmp_path).check(tmp_path)
    (tmp_path / "package.json").write_text("{", encoding="utf-8")

    malformed = _rule(tmp_path).check(tmp_path)

    assert missing.status == RuleStatus.SKIPPED
    assert missing.message == "package.json not found"
    assert malformed.status == RuleStatus.FAILED
    assert malformed.message.startswith("error parsing package.json:")
