# Unused Dependencies

These project-wide analyzers compare direct package declarations with package references in
project source. They cover Dart/Flutter, PHP Composer, Python, and JavaScript/TypeScript/Svelte.
They do not require an external analyzer. Run the check for one ecosystem with:

```bash
python main.py --language python --path /path/to/project --only-analyzer python_unused_dependencies
```

Use `php_unused_dependencies` for PHP, `javascript_unused_dependencies` for JavaScript,
TypeScript, or Svelte, and `dart_unused_dependencies` for Dart/Flutter. The three newer rules
are enabled by default in `rules.json`; the PHP rule is also enabled when its entry is absent
from a PHP project's rules file. An explicit `"enabled": false` disables each rule.

## Shared Options

Each rule accepts these options in its `rules.json` entry:

| Option | Default | Description |
| --- | --- | --- |
| `enabled` | `true` | Enable or disable the rule. |
| `check_dev_dependencies` | `true` | Check development dependencies as well as runtime dependencies. |
| `severity` | `"warning"` | Severity of unused-package findings. |
| `ignore_packages` | Ecosystem-specific; see below | Package names to exempt from findings. |
| `scan_paths` | Ecosystem-specific; see below | Source directories used for runtime and development dependency references. |
| `ignore_tool_packages` | `true` for PHP, Python, and JavaScript | Treat recognized command-line/build tools as used even without source imports. |

Runtime packages are checked against runtime and development source paths. Development packages
are used when referenced from either set of paths. Configure `scan_paths` to include project code
outside the defaults, or add packages used by reflection, generated code, framework conventions,
or build configuration to `ignore_packages`. These checks only recognize the usage forms described
below; review findings before removing a package.

## Ecosystem Details

### Dart and Flutter

The `dart_unused_dependencies` rule reads `pubspec.yaml`, matches `package:` imports, and checks
both regular and development dependencies. Defaults scan `lib` for runtime packages and `test`
plus `integration_test` for development packages. Its default ignore list covers Flutter and common
code-generation packages. See [Dart unused dependencies](dart_unused_dependencies.md) for its
existing configuration and output details.

### PHP and Composer

`php_unused_dependencies` reads `require` and `require-dev` from `composer.json`. It needs
`composer.lock` or `vendor/composer/installed.json` to map direct requirements to PSR-4 or PSR-0
autoload namespaces. It scans PHP namespace uses, including grouped imports and fully qualified
names, case-insensitively. Runtime defaults scan the project root while excluding `vendor`,
`test`, and `tests`; development defaults scan `tests` and `test` while still excluding `vendor`.
There is no default `ignore_packages` list. When `ignore_tool_packages` is enabled, packages that
declare Composer binaries or are Composer plugins are exempt.

Without lock or installed-package data the rule skips with a warning. Packages with no usable
namespace mapping, such as files-only autoload packages, are logged and skipped because their use
cannot be established. PHP platform requirements (`php`, `ext-*`, and related platform names) are
not treated as packages. See the [PHP setup guide](../setup/PHP.md).

### Python

`python_unused_dependencies` reads runtime and development declarations from `pyproject.toml`,
including optional dependencies and dependency groups, or from a root `requirements.txt` and a
recognized development requirements file. It matches absolute Python imports. Distribution names
are mapped through `.venv`/`venv` package metadata where available, then common name aliases and a
normalized-name fallback. Use `import_names` to override or add mappings, for example:

```json
{
  "python_unused_dependencies": {
    "import_names": {
      "distribution-name": ["module_name"]
    }
  }
}
```

The default runtime path is `.` and the development paths are `tests` and `test`; environment,
test, and cache directories are excluded from runtime scans. The default ignore list is
`pytest`, `ruff`, `mypy`, `black`, `coverage`, `pytest-cov`, `pre-commit`, `setuptools`, `wheel`,
`hatchling`, and `pip`. With `ignore_tool_packages` enabled, installed distributions with a
`console_scripts` entry point are also exempt. Source files that cannot be parsed are logged and
skipped. See the [Python setup guide](../setup/PYTHON.md).

### JavaScript, TypeScript, and Svelte

`javascript_unused_dependencies` reads `dependencies` and `devDependencies` from `package.json`.
It recognizes static imports, re-exports, side-effect and dynamic imports, and `require()` in
JavaScript, TypeScript, Svelte, and Vue source files. It also uses package references in TypeScript
configuration and root config files. Defaults scan `.` for runtime packages and `tests`/`test` for
development packages, excluding `node_modules`, build output, `.svelte-kit`, and coverage folders.

The default ignore list is `typescript`, `svelte`, `tslib`, and the common SvelteKit adapters and
Vite plugin. `@types` packages are matched to their runtime package; `@types/node` counts as used
when TypeScript files are present. With `ignore_tool_packages` enabled, packages declaring a
`bin` entry or named in `package.json` scripts are exempt. See the
[JavaScript/TypeScript](../setup/JAVASCRIPT_TYPESCRIPT.md) and [Svelte](../setup/SVELTE.md) setup
guides.

## Unsupported Ecosystems

The remaining supported languages do not have a reliable package-to-source mapping for this
check:

- **C#:** NuGet package IDs do not reliably map to namespaces. Test adapters, analyzers, and
  dependency-injection extension packages may be used without a matching `using` directive.
- **Kotlin:** Gradle declarations, version catalogs, and plugins need resolved artifact metadata
  before they can be mapped to source packages.
- **Arduino/C++:** library manifests vary, and header names do not reliably identify library
  names.
- **AutoHotkey and contract JSON:** these project types have no package manifest to compare.

No unused-package findings are produced for these ecosystems. The separate `--audit-dependencies`
command reports advisories and outdated packages from supported lock files; it does not detect
unused packages.
