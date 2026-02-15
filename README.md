# CLI Code Analyzer

A flexible command-line tool for analyzing code files based on configurable rules. Specifically designed for AI-generated code to ensure quality and maintainability.

## Features

- **Multi-language support**: Currently supports Flutter/Dart, Python, Java, JavaScript, TypeScript (extensible to other languages)
- **Configurable rules**: Define custom rules via JSON configuration
- **Multiple output formats**: Minimal, normal, and verbose output modes
- **File export capability**: Save analysis reports to files for CI/CD integration
- **Severity filtering**: Filter violations by error or warning levels
- **Line count rules**: Check maximum lines per file with warning and error thresholds
- **Duplicate code detection**: Integrated [PMD](https://pmd.github.io/) CPD for finding copy-paste code across projects
- **Flutter/Dart static analysis**: Integrated `dart analyze --fatal-infos` for comprehensive Dart code analysis with severity mapping (info/warning/error)
- **Flutter analyze**: Integrated `flutter analyze` for Flutter-specific code analysis with text output parsing
- **Dart code metrics**: Integrated [dart_code_linter](https://pub.dev/packages/dart_code_linter) for advanced metrics (cyclomatic complexity, maintainability index, technical debt, etc.)
- **Python linting**: Integrated [Ruff](https://docs.astral.sh/ruff/) for fast Python linting with 800+ rules
- **ESLint integration**: Integrated [ESLint](https://eslint.org/) for JavaScript/TypeScript linting with auto-detection of Svelte projects
- **Svelte type checking**: Integrated [svelte-check](https://github.com/sveltejs/language-tools/tree/master/packages/svelte-check) for Svelte/TypeScript type checking with configurable compiler warning suppression
- **TypeScript type checking**: Integrated `tsc --noEmit` for project-wide TypeScript type checking with error code filtering
- **Auto-fix support**: Automatically fix Python issues using Ruff with `ruff_fixer.py`
- **Language-specific exclusions**: Automatically exclude generated files (e.g., `**.g.dart`, `**.freezed.dart`)
- **Relative path display**: Clean, readable output with relative file paths

## Installation

1. Clone the repository:
```bash
git clone https://github.com/BenjaminKobjolke/cli-code-analyzer.git
cd cli-code-analyzer
```

2. Install Python dependencies (Python 3.7+ required):
```bash
# On Windows
install.bat

# On Linux/Mac
pip install -r requirements.txt
```

3. Activate the virtual environment (required before each use):
```bash
# On Windows
activate_environment.bat

# On Linux/Mac
source venv/bin/activate
```

4. (Optional) Install PMD for duplicate code detection:
   - Download PMD from [https://pmd.github.io/](https://pmd.github.io/)
   - Extract to a location on your system
   - The analyzer will prompt for the path to `pmd.bat` on first use

5. (Optional) Install Flutter/Dart SDK for Dart analysis:
   - Download Flutter SDK from [https://docs.flutter.dev/get-started/install](https://docs.flutter.dev/get-started/install)
   - Ensure `dart` is in your PATH, or the analyzer will prompt for the path on first use

## Usage

**Important:** Always activate the virtual environment before running the analyzer:
```bash
# On Windows
activate_environment.bat

# On Linux/Mac
source venv/bin/activate
```

### Basic Command Structure

```bash
python main.py --language <language> --path <path> [options]
```

### Command Line Arguments

| Argument | Short | Required | Default | Description |
|----------|-------|----------|---------|-------------|
| `--language` | `-l` | Yes | - | Programming language to analyze. **Line counting:** `flutter`, `python`. **Duplicate detection (PMD):** `dart`, `python`, `java`, `javascript`, `typescript` |
| `--path` | `-p` | Yes | - | Path to the code directory (analyzes recursively) or single file to analyze |
| `--rules` | `-r` | No | `rules.json` | Path to the rules JSON configuration file |
| `--verbosity` | `-v` | No | `normal` | Output verbosity level: `minimal`, `normal`, or `verbose` |
| `--output` | `-o` | No | - | Path to output folder for reports. If set, saves reports to files (`line_count_report.txt`, `duplicate_code.csv`) instead of console output |
| `--loglevel` | `-L` | No | `all` | Filter violations by severity: `error`, `warning`, or `all` |
| `--maxamountoferrors` | `-m` | No | unlimited | Maximum number of violations to include in reports. When exceeded, keeps the largest violations (e.g., duplicates with most lines) |
| `--list-files` | `-f` | No | off | List all analyzed file paths after analysis |
| `--list-analyzers` | `-a` | No | - | List available analyzers for a language (or all) |

## Examples

### Quick Start

To get started quickly with the example project:

```bash
# 1. Activate the virtual environment
activate_environment.bat

# 2. Run the analyzer on the example directory
python main.py --language flutter --path example/lib --rules example/rules.json
```

### Test with the Example Directory

The project includes an `example/` directory with a sample Flutter project that exceeds the configured line limits.

> **Note:** All examples below assume you have already activated the virtual environment with `activate_environment.bat` (Windows) or `source venv/bin/activate` (Linux/Mac).

#### 1. Basic Analysis (Normal Output)
```bash
python main.py --language flutter --path example/lib --rules example/rules.json
```

**Output:**
```
ERRORS (1):
================================================================================
  sample_widget.dart
    File has 350 lines (limit: 300)

================================================================================
Summary: 1 error(s), 0 warning(s)
```

#### 2. Minimal Output Format
```bash
python main.py --language flutter --path example/lib --rules example/rules.json --verbosity minimal
```

**Output:**
```
sample_widget.dart errors:1 warnings:0 maxlines>350
Summary: 1 error(s), 0 warning(s)
```

#### 3. Verbose Output Format
```bash
python main.py --language flutter --path example/lib --rules example/rules.json --verbosity verbose
```

**Output:**
```
Analyzing 1 file(s)...

ERRORS (1):
================================================================================
  sample_widget.dart
    Rule: max_lines_per_file
    Severity: ERROR
    Lines: 350 / 300 (limit exceeded by 50)
    Message: File has 350 lines (limit: 300)

================================================================================
Files analyzed: 1
Files with violations: 1
Summary: 1 error(s), 0 warning(s)
```

#### 4. Show Only Errors
```bash
python main.py --language flutter --path example/lib --rules example/rules.json --loglevel error
```

**Output:**
```
ERRORS (1):
================================================================================
  sample_widget.dart
    File has 350 lines (limit: 300)

================================================================================
Summary: 1 error(s)
```

#### 5. Show Only Errors with Minimal Output
```bash
python main.py --language flutter --path example/lib --rules example/rules.json --verbosity minimal --loglevel error
```

**Output:**
```
sample_widget.dart errors:1 maxlines>350
Summary: 1 error(s)
```

#### 6. Save Reports to Files
```bash
python main.py --language flutter --path example/lib --rules example/rules.json --output reports/
```

**Output:**
```
Line count report saved to: reports/line_count_report.txt
```

This will create a `reports/` folder with analysis results in files instead of printing to console. Useful for CI/CD pipelines and automated reporting.

### Single File vs Directory Analysis

The `--path` argument is flexible and works with both directories and individual files:

#### Analyze a Single File

Perfect for checking a specific file during development:

```bash
# Analyze just the sample widget file
python main.py --language flutter --path example/lib/sample_widget.dart --rules example/rules.json
```

**When to use:**
- Quick check of a file you just modified
- Testing specific files in CI/CD
- Focused code review on changed files

#### Analyze a Directory

Recursively analyzes all `.dart` files in the directory and subdirectories:

```bash
# Analyze all files in the lib directory
python main.py --language flutter --path example/lib --rules example/rules.json
```

**When to use:**
- Full project analysis
- Pre-commit checks
- Comprehensive code quality audits

### Analyze Your Own Flutter Project

```bash
# Analyze entire Flutter project
python main.py --language flutter --path /path/to/your/flutter/project/lib

# Analyze specific directory
python main.py --language flutter --path /path/to/your/flutter/project/lib/widgets

# Analyze single file
python main.py --language flutter --path /path/to/your/flutter/project/lib/main.dart
```

## Configuration

### Rules Configuration File

The rules are defined in a JSON file (default: `rules.json`):

```json
{
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500
  }
}
```

**Configuration Options:**

- `enabled`: Boolean to enable/disable the rule
- `warning`: Line count threshold for warnings
- `error`: Line count threshold for errors

### Creating Custom Rules Files

You can create multiple rule files for different scenarios:

```bash
# Strict rules for production code
python main.py --language flutter --path lib/ --rules rules-strict.json

# Lenient rules for test code
python main.py --language flutter --path test/ --rules rules-lenient.json
```

**Example `rules-strict.json`:**
```json
{
  "max_lines_per_file": {
    "enabled": true,
    "warning": 200,
    "error": 300
  }
}
```

**Example `rules-lenient.json`:**
```json
{
  "max_lines_per_file": {
    "enabled": true,
    "warning": 500,
    "error": 1000
  }
}
```

### Log Level Configuration

The analyzer supports flexible log level configuration at three levels: global, per-rule, and via CLI flag.

#### Log Level Hierarchy

Log levels are resolved using the following precedence (highest to lowest):

1. **CLI flag `--loglevel`** (highest priority, overrides everything)
2. **Per-rule `log_level`** in rules.json
3. **Global `log_level`** in rules.json
4. **Default: "all"** (if nothing is specified)

#### Available Log Levels

- `all`: Show all violations (INFO, WARNING, ERROR)
- `warning`: Show only WARNING and ERROR violations
- `error`: Show only ERROR violations

#### Global Log Level

Set a default log level for all rules at the top level of `rules.json`:

```json
{
  "log_level": "warning",
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500
  },
  "dart_analyze": {
    "enabled": true
  }
}
```

This will filter all rules to show only warnings and errors by default.

#### Per-Rule Log Level

Override the log level for specific rules:

```json
{
  "log_level": "all",
  "max_lines_per_file": {
    "enabled": true,
    "log_level": "error",
    "warning": 300,
    "error": 500
  },
  "dart_analyze": {
    "enabled": true,
    "log_level": "warning"
  },
  "pmd_duplicates": {
    "enabled": true,
    "minimum_tokens": 100
  }
}
```

In this example:
- `max_lines_per_file` only shows ERROR violations
- `dart_analyze` shows WARNING and ERROR violations
- `pmd_duplicates` inherits the global "all" level

#### CLI Flag Override

The `--loglevel` CLI flag overrides all configuration:

```bash
# Ignores all rules.json log_level settings, shows only errors
python main.py --language flutter --path lib/ --loglevel error

# Uses rules.json log_level settings (no CLI override)
python main.py --language flutter --path lib/
```

#### Example Use Cases

**Use Case 1: Strict CI/CD Pipeline**
```json
{
  "log_level": "error",
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500
  },
  "dart_analyze": {
    "enabled": true
  }
}
```

CI/CD will only fail on errors, warnings are ignored.

**Use Case 2: Focus on Specific Rules**
```json
{
  "log_level": "all",
  "max_lines_per_file": {
    "enabled": true,
    "log_level": "error",
    "warning": 300,
    "error": 500
  },
  "dart_analyze": {
    "enabled": true,
    "log_level": "warning"
  }
}
```

- See all issues from most rules
- Only see critical file length violations
- Hide info-level issues from dart analyze

**Use Case 3: Development vs Production**

**rules-dev.json** (show everything):
```json
{
  "log_level": "all",
  "dart_analyze": {
    "enabled": true
  }
}
```

**rules-production.json** (strict):
```json
{
  "log_level": "error",
  "dart_analyze": {
    "enabled": true
  }
}
```

```bash
# Development: see all issues
python main.py --language flutter --path lib/ --rules rules-dev.json

# CI/CD: fail only on errors
python main.py --language flutter --path lib/ --rules rules-production.json
```

### PMD Duplicate Code Detection

The analyzer integrates with [PMD](https://pmd.github.io/)'s Copy-Paste Detector (CPD) to find duplicate code blocks across your project.

#### Enabling PMD Duplicate Detection

1. Install [PMD](https://pmd.github.io/) (see Installation step 4)
2. Enable the rule in `rules.json`:

```json
{
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500
  },
  "pmd_duplicates": {
    "enabled": true,
    "minimum_tokens": 100,
    "max_results": 50,
    "exclude_patterns": {
      "dart": ["*.g.dart", "*.freezed.dart"],
      "python": ["**/__pycache__/**", "*.pyc"],
      "java": ["**/target/**", "**/build/**"],
      "javascript": ["**/node_modules/**", "**/dist/**", "**/build/**"],
      "typescript": ["**/node_modules/**", "**/dist/**", "**/build/**"]
    }
  }
}
```

**Configuration Options:**

- `enabled`: Enable/disable duplicate code detection
- `minimum_tokens`: Minimum number of duplicate tokens to report (lower = more sensitive)

- `max_results`:
Maximum number of duplicate blocks to report (keeps largest duplicates when exceeded)
Limit the maximum amount of errors this way.

- `exclude_patterns`: Language-specific glob patterns to exclude (e.g., `*.g.dart` for generated files, `**/node_modules/**` for dependencies)

#### Using PMD Duplicate Detection

**Console Output (Text Format):**
```bash
python main.py --language flutter --path lib/
```

The duplicate code report will be printed directly to the console.

**File Output (CSV Format):**
```bash
python main.py --language flutter --path lib/ --output reports/
```

This creates two files:
- `reports/line_count_report.txt` - Line count analysis
- `reports/duplicate_code.csv` - Duplicate code detection results

#### First-Time Setup

On first run with PMD enabled, you'll be prompted to enter the path to PMD:

```
PMD path not configured. Please enter the path to pmd.bat
[Default: E:\downloads\pmd-dist-7.17.0-bin\pmd-bin-7.17.0\bin\pmd.bat]:
```

Enter the path to your PMD installation, or press Enter to use the default. The path will be saved to `settings.ini` for future use.

#### Supported Languages for Duplicate Detection

- Dart/Flutter
- Python
- Java
- JavaScript
- TypeScript

#### Example: Finding Duplicates in a Flutter Project

```bash
# Enable pmd_duplicates in rules.json first
python main.py --language flutter --path lib/ --output reports/
```

**Output:**
```
Duplicate code report saved to: reports/duplicate_code.csv
Line count report saved to: reports/line_count_report.txt
```

The CSV file contains:
- Number of duplicate lines
- Number of duplicate tokens
- Number of occurrences
- File locations of duplicates

### Dart Static Analysis

The analyzer integrates with Flutter/Dart's built-in `dart analyze` tool to perform comprehensive static analysis on Dart/Flutter projects. This catches issues like unused variables, type errors, missing return types, and many other code quality issues.

#### Enabling Dart Analysis

1. Install Flutter/Dart SDK (see Installation step 5)
2. Ensure the rule is enabled in `rules.json`:

```json
{
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500
  },
  "pmd_duplicates": {
    "enabled": true,
    "minimum_tokens": 100
  },
  "dart_analyze": {
    "enabled": true
  }
}
```

**Note:** The `dart_analyze` rule is enabled by default for Flutter/Dart projects.

#### Using Dart Analysis

**Console Output:**
```bash
python main.py --language flutter --path lib/
```

Dart analyze will run automatically on Flutter/Dart projects and report issues with their original severity levels (info, warning, error).

**File Output:**
```bash
python main.py --language flutter --path lib/ --output reports/
```

This creates `reports/dart_analyze.csv` with the full analysis results in CSV format.

#### First-Time Setup

If `dart` is not found in your PATH, you'll be prompted:

```
Dart executable not found in PATH.
Please ensure Flutter/Dart SDK is installed.
Download from: https://docs.flutter.dev/get-started/install

Enter path to dart executable (or press Enter to skip):
```

Enter the path to your Dart executable (e.g., `C:\flutter\bin\dart.exe`), or press Enter to skip. The path will be saved to `settings.ini` for future use.

#### What Dart Analyze Detects

The `dart analyze --fatal-infos` command checks for:

- **Errors**: Type errors, undefined methods, syntax errors
- **Warnings**: Missing return types, unused imports, deprecated API usage
- **Infos**: Unused variables, unnecessary casts, style guide violations
- **Lints**: Code style and best practice recommendations

#### Severity Mapping

The analyzer preserves Dart's original severity levels:
- `info` → INFO (informational issues)
- `warning` → WARNING (code smells, potential issues)
- `error` → ERROR (code that won't compile or will fail at runtime)

#### Example: Analyzing a Flutter Project

```bash
# Analyze with all rules including dart analyze
python main.py --language flutter --path lib/

# Only show errors from dart analyze
python main.py --language flutter --path lib/ --loglevel error

# Save dart analyze results to file
python main.py --language flutter --path lib/ --output reports/
```

**Example Output:**
```
Dart analyze found 3 issue(s)

ERRORS (1):
================================================================================
  lib/main.dart
    The method 'foo' isn't defined for the type 'String' (undefined_method) at line 23, column 5

WARNINGS (1):
================================================================================
  lib/utils.dart
    Missing return type (type_annotate_public_apis) at line 15, column 3

INFO (1):
================================================================================
  lib/widgets/button.dart
    The declaration 'unusedVar' isn't referenced (unused_element) at line 10, column 7
```

#### Generated Files Handling

Generated Dart files (like `*.g.dart`, `*.freezed.dart`) are automatically handled by Dart's analyzer. These files typically include `// ignore_for_file` comments at the top, which suppress lint warnings while still reporting errors. **No additional configuration is needed.**

### Flutter Analyze

The analyzer integrates with Flutter's built-in `flutter analyze` tool to perform comprehensive static analysis specifically for Flutter projects. This is similar to `dart analyze` but uses the Flutter executable and is particularly useful for Flutter-specific validations.

#### Enabling Flutter Analyze

1. Install Flutter SDK (see Installation step 5)
2. Enable the rule in `rules.json`:

```json
{
  "dart_analyze": {
    "enabled": true
  },
  "flutter_analyze": {
    "enabled": true,
    "exclude_patterns": ["*.g.dart", "*.freezed.dart"]
  }
}
```

**Configuration Options:**

- `enabled`: Enable/disable flutter analyze analysis
- `exclude_patterns`: Glob patterns for files to exclude (for future use)

**Note:** The `flutter_analyze` rule is disabled by default. Enable it if you want to use `flutter` executable instead of `dart` for analysis.

#### Flutter Project Detection

The analyzer automatically detects Flutter projects by checking `pubspec.yaml` for a `flutter:` dependency. If detected, it will run `flutter analyze` on the project root.

#### Using Flutter Analyze

**Console Output:**
```bash
python main.py --language flutter --path lib/
```

Flutter analyze will run automatically on detected Flutter projects and report issues with their original severity levels (info, warning, error).

**File Output:**
```bash
python main.py --language flutter --path lib/ --output reports/
```

This creates `reports/flutter_analyze.csv` with the full analysis results in CSV format.

#### First-Time Setup

If `flutter` is not found in your PATH, you'll be prompted:

```
Flutter executable not found in PATH.
Please ensure Flutter SDK is installed.
Download from: https://docs.flutter.dev/get-started/install

Enter path to flutter executable (or press Enter to skip):
```

Enter the path to your Flutter executable (e.g., `C:\flutter\bin\flutter.bat`), or press Enter to skip. The path will be saved to `settings.ini` for future use.

#### What Flutter Analyze Detects

The `flutter analyze` command checks for:

- **Errors**: Type errors, undefined methods, syntax errors
- **Warnings**: Missing return types, unused imports, deprecated API usage, implementation imports
- **Infos**: Unused variables, unnecessary imports, style guide violations

#### Severity Mapping

The analyzer maps Flutter analyze severity levels:
- `info` → INFO (informational issues like unnecessary imports)
- `warning` → WARNING (code smells, unused code)
- `error` → ERROR (code that won't compile or will fail at runtime)

#### Example Output

**Console:**
```
Flutter analyze found 5 issue(s)

WARNINGS (4):
================================================================================
  lib/screens/directory_browser_screen.dart
    Unused import: 'package:path/path.dart' (unused_import) at line 3, column 8

  lib/screens/directory_browser_screen.dart
    Unused import: 'package:saf/src/storage_access_framework/api.dart' (unused_import) at line 6, column 8

  lib/screens/directory_browser_screen.dart
    Unused import: '../models/sort_settings.dart' (unused_import) at line 7, column 8

  lib/screens/directory_browser_screen.dart
    Unused import: '../utils/custom_snackbar_helper.dart' (unused_import) at line 12, column 8

INFO (1):
================================================================================
  lib/screens/directory_browser_screen.dart
    Import of a library in the 'lib/src' directory of another package (implementation_imports) at line 6, column 8
```

**CSV Format (`flutter_analyze.csv`):**
```csv
file,line,column,severity,code,message
lib/screens/directory_browser_screen.dart,3,8,WARNING,unused_import,Unused import: 'package:path/path.dart'
lib/screens/directory_browser_screen.dart,6,8,WARNING,unused_import,Unused import: 'package:saf/src/storage_access_framework/api.dart'
lib/screens/directory_browser_screen.dart,6,8,INFO,implementation_imports,Import of a library in the 'lib/src' directory of another package
```

#### Flutter vs Dart Analyze

Both `dart_analyze` and `flutter_analyze` provide similar functionality. Choose based on your needs:

- **Use `dart_analyze`**: For general Dart projects, or when you want JSON output format
- **Use `flutter_analyze`**: For Flutter projects, or when you prefer using the Flutter executable
- **Use both**: Can be enabled simultaneously (though usually redundant)

#### Integration with Other Rules

Flutter analyze works alongside other analyzer rules:

```bash
# All rules enabled
python main.py --language flutter --path lib/ --output reports/

# This can create:
# - reports/line_count_report.csv
# - reports/duplicate_code.csv
# - reports/dart_analyze.csv (if enabled)
# - reports/flutter_analyze.csv (if enabled)
# - reports/dart_code_linter.csv (if enabled)
```

### Dart Code Linter - Code Metrics Analysis

The analyzer integrates with [dart_code_linter](https://pub.dev/packages/dart_code_linter) to perform advanced code metrics analysis on Dart/Flutter projects. This provides detailed metrics like cyclomatic complexity, maintainability index, lines of code per function/class, and more.

#### Enabling Dart Code Linter

1. The rule is disabled by default in `rules.json`. Enable it by setting `"enabled": true`:

```json
{
  "dart_code_linter": {
    "enabled": true,
    "auto_install": false,
    "analyze_path": "lib",
    "metrics": {
      "cyclomatic-complexity": {
        "warning": 10,
        "error": 20
      },
      "lines-of-code": {
        "warning": 50,
        "error": 100
      },
      "number-of-methods": {
        "warning": 10,
        "error": 20
      },
      "technical-debt": {
        "warning": 10,
        "error": 50
      },
      "maintainability-index": {
        "warning": 40,
        "error": 20
      },
      "maximum-nesting-level": {
        "warning": 3,
        "error": 5
      }
    }
  }
}
```

**Configuration Options:**

- `enabled`: Enable/disable dart_code_linter analysis
- `auto_install`: If `true`, automatically runs `dart pub add --dev dart_code_linter` if not installed
- `analyze_path`: Path to analyze (default: `lib`)
- `metrics`: Metric thresholds for warning and error levels

#### Installing dart_code_linter

**Option 1: Manual Installation (Recommended)**
```bash
cd your-flutter-project
dart pub add --dev dart_code_linter
```

**Option 2: Automatic Installation**

Set `"auto_install": true` in `rules.json`, and the analyzer will install it automatically if not found in `pubspec.yaml`.

#### Using Dart Code Linter

**Console Output:**
```bash
python main.py --language flutter --path lib/
```

Dart Code Linter will analyze your code and report metric violations based on configured thresholds.

**File Output:**
```bash
python main.py --language flutter --path lib/ --output reports/
```

This creates `reports/dart_code_linter.csv` with all metric violations.

#### Supported Metrics

The following metrics can be configured with warning and error thresholds:

| Metric ID | Description | Normal Direction |
|-----------|-------------|------------------|
| `cyclomatic-complexity` | Number of linearly independent paths through code | Higher is worse |
| `lines-of-code` | Number of lines in a function/method | Higher is worse |
| `source-lines-of-code` | Non-comment, non-blank lines of code | Higher is worse |
| `number-of-methods` | Number of methods in a class | Higher is worse |
| `technical-debt` | Estimated hours of technical debt | Higher is worse |
| `maintainability-index` | Maintainability score (0-100) | **Lower is worse** |
| `maximum-nesting-level` | Maximum depth of nested blocks | Higher is worse |
| `halstead-volume` | Halstead complexity volume metric | Higher is worse |
| `weight-of-class` | Class weight metric | Higher is worse |

**Note:** For `maintainability-index`, lower values indicate worse code. A value of 100 is perfect, while lower scores indicate harder-to-maintain code.

#### Example Output

**Console:**
```
Dart Code Linter found 5 metric violation(s)

ERRORS (2):
================================================================================
  lib/services/data_processor.dart
    cyclomatic-complexity = 25 >= 20 (threshold) in function processData

  lib/widgets/complex_form.dart
    lines-of-code = 120 >= 100 (threshold) in class ComplexForm

WARNINGS (3):
================================================================================
  lib/utils/helper.dart
    cyclomatic-complexity = 12 >= 10 (threshold) in function calculateResult

  lib/models/user.dart
    number-of-methods = 15 >= 10 (threshold) in class User

  lib/widgets/dashboard.dart
    maintainability-index = 35 <= 40 (threshold) in function buildDashboard
```

**CSV Format (`dart_code_linter.csv`):**
```csv
file_path,metric,severity,message
lib/services/data_processor.dart,dart_code_linter,ERROR,"cyclomatic-complexity = 25 >= 20 (threshold) in function processData"
lib/widgets/complex_form.dart,dart_code_linter,ERROR,"lines-of-code = 120 >= 100 (threshold) in class ComplexForm"
```

#### Customizing Metric Thresholds

Adjust thresholds in `rules.json` based on your project's needs:

**Strict Configuration (for new/clean code):**
```json
{
  "dart_code_linter": {
    "enabled": true,
    "metrics": {
      "cyclomatic-complexity": {
        "warning": 5,
        "error": 10
      },
      "lines-of-code": {
        "warning": 30,
        "error": 50
      },
      "maintainability-index": {
        "warning": 60,
        "error": 40
      }
    }
  }
}
```

**Lenient Configuration (for legacy code):**
```json
{
  "dart_code_linter": {
    "enabled": true,
    "metrics": {
      "cyclomatic-complexity": {
        "warning": 20,
        "error": 30
      },
      "lines-of-code": {
        "warning": 100,
        "error": 200
      },
      "maintainability-index": {
        "warning": 30,
        "error": 10
      }
    }
  }
}
```

#### Focusing on Specific Metrics

You can track only the metrics you care about by removing others from the configuration:

```json
{
  "dart_code_linter": {
    "enabled": true,
    "metrics": {
      "cyclomatic-complexity": {
        "warning": 10,
        "error": 20
      },
      "maintainability-index": {
        "warning": 40,
        "error": 20
      }
    }
  }
}
```

Only metrics listed in the configuration will be checked. Unlisted metrics will be ignored.

#### Integration with Other Rules

Dart Code Linter works alongside other analyzer rules:

```bash
# All rules enabled (line count + duplicates + dart analyze + dart_code_linter)
python main.py --language flutter --path lib/ --output reports/

# This creates:
# - reports/line_count_report.csv
# - reports/duplicate_code.csv
# - reports/dart_analyze.csv
# - reports/dart_code_linter.csv
```

### Python Auto-Fix with Ruff

The analyzer includes a dedicated tool to automatically fix Python code issues using Ruff. It uses the same configuration from your `rules.json` file.

#### Using the Ruff Fixer

**Quick Start (Windows):**
```bash
fix_python_ruff_issues.bat
```

**Manual Usage:**
```bash
python ruff_fixer.py --path . --rules code_analysis_rules.json
```

**Dry Run (show what would be fixed):**
```bash
python ruff_fixer.py --path . --rules code_analysis_rules.json --dry-run
```

#### Ruff Fixer Options

| Option | Description | Default |
|--------|-------------|---------|
| `--path` | Path to code directory or file | Required |
| `--rules` | Path to rules JSON file | `code_analysis_rules.json` |
| `--dry-run` | Show changes without applying | False |

The fixer reads the `ruff_analyze` configuration from your rules JSON:
- `select`: Which rule categories to check/fix
- `ignore`: Rules to ignore
- `exclude_patterns`: Directories to skip

#### Example Workflow

```bash
# 1. First, analyze to see issues
python main.py --language python --path . --rules code_analysis_rules.json

# 2. Auto-fix the issues
python ruff_fixer.py --path . --rules code_analysis_rules.json

# 3. Re-analyze to confirm fixes
python main.py --language python --path . --rules code_analysis_rules.json
```

### ESLint Analysis (JavaScript/TypeScript/Svelte)

The analyzer integrates with [ESLint](https://eslint.org/) for JavaScript and TypeScript linting. It auto-detects Svelte projects and conditionally includes `.svelte` files.

#### Enabling ESLint Analysis

Enable the rule in `rules.json`:

```json
{
  "eslint_analyze": {
    "enabled": true,
    "config_mode": "auto",
    "exclude_patterns": ["node_modules/**", "dist/**", "build/**", "coverage/**"]
  }
}
```

**Configuration Options:**

- `enabled`: Enable/disable ESLint analysis
- `config_mode`: How to resolve ESLint config — `"auto"` (detect project config), `"project"` (require project config), or `"builtin"` (use rules from `rules.json` only)
- `exclude_patterns`: Glob patterns for files/directories to exclude
- `extensions`: Explicitly set file extensions to lint (e.g., `[".js", ".ts", ".svelte"]`). If omitted, extensions are auto-detected

#### Svelte Support

The analyzer auto-detects Svelte projects. The behavior depends on whether `eslint-plugin-svelte` is installed in the target project:

| Condition | Behavior |
|---|---|
| Plugin installed (`node_modules/eslint-plugin-svelte` exists) | `.svelte` files are automatically included for ESLint |
| Plugin not installed, `.svelte` files exist | Warning printed, `.svelte` files skipped |
| No `.svelte` files in project | Standard JS/TS extensions only |

**Important:** Installing `eslint-plugin-svelte` alone is not enough. The target project's ESLint config must also be set up to use the Svelte parser. Without this, ESLint will try to parse `.svelte` files as plain JavaScript, resulting in `Parsing error: Unexpected token <` on every `.svelte` file.

#### Setting Up ESLint for Svelte Projects

1. Install the plugin and parser in your project:

```bash
npm install --save-dev eslint-plugin-svelte svelte-eslint-parser
```

2. Add a Svelte config block to your `eslint.config.js` (ESLint 9 flat config):

```javascript
import sveltePlugin from 'eslint-plugin-svelte';
import svelteParser from 'svelte-eslint-parser';
import tsparser from '@typescript-eslint/parser';

export default [
    // ... your existing JS/TS config ...
    {
        files: ['**/*.svelte'],
        languageOptions: {
            parser: svelteParser,
            parserOptions: {
                parser: tsparser,  // for TypeScript in <script lang="ts">
                ecmaVersion: 'latest',
                sourceType: 'module'
            }
        },
        plugins: {
            svelte: sveltePlugin
        },
        rules: {
            ...sveltePlugin.configs.recommended.rules
        }
    },
    // ... ignores, etc. ...
];
```

Without this configuration, the analyzer will correctly detect the plugin and include `.svelte` files, but ESLint will fail to parse them.

#### Using ESLint Analysis

**Console Output:**
```bash
python main.py --language javascript --path src/
```

**File Output:**
```bash
python main.py --language javascript --path src/ --output reports/
```

This creates `reports/eslint_analyze.csv` with all ESLint violations.

### Svelte Check (Svelte/TypeScript Type Checking)

The analyzer integrates with [svelte-check](https://github.com/sveltejs/language-tools/tree/master/packages/svelte-check) for type checking Svelte and TypeScript code in SvelteKit projects.

#### Enabling Svelte Check

Enable the rule in your project's rules JSON file (passed via `--rules`, default: `rules.json`):

```json
{
  "svelte_check": {
    "enabled": true,
    "tsconfig": "./tsconfig.json"
  }
}
```

**Configuration Options:**

- `enabled`: Enable/disable svelte-check analysis
- `tsconfig`: Path to `tsconfig.json` (default: `./tsconfig.json`)
- `compiler_warnings`: Map of Svelte compiler warning codes to their level. Each key is a warning code, each value is `"ignore"` or `"error"`. Passed as the `--compiler-warnings` flag to svelte-check

#### Suppressing Compiler Warnings

Use the `compiler_warnings` option to suppress known false positives. For example, SvelteKit passes `params` to every page component, which triggers `unused-export-let` warnings on every route file. To suppress these:

```json
{
  "svelte_check": {
    "enabled": true,
    "tsconfig": "./tsconfig.json",
    "compiler_warnings": {
      "unused-export-let": "ignore"
    }
  }
}
```

This passes `--compiler-warnings unused-export-let:ignore` to svelte-check. Multiple warnings can be suppressed by adding more entries to the map.

#### Using Svelte Check

**Console Output:**
```bash
python main.py --language javascript --path src/
```

**File Output:**
```bash
python main.py --language javascript --path src/ --output reports/
```

This creates `reports/svelte_check.csv` with all svelte-check violations.

#### First-Time Setup

If `svelte-check` is not found, you'll be prompted to enter the path to the executable (e.g., `node_modules/.bin/svelte-check`). The path will be saved to `settings.ini` for future use.

### TypeScript Type Checking (tsc)

The analyzer integrates with TypeScript's `tsc --noEmit` for project-wide type checking.

#### Enabling TypeScript Type Checking

Enable the rule in `rules.json`:

```json
{
  "tsc_analyze": {
    "enabled": true,
    "tsconfig": "./tsconfig.json",
    "skip_svelte_resolve_errors": true,
    "ignore_codes": ["TS2614"]
  }
}
```

**Configuration Options:**

- `enabled`: Enable/disable tsc type checking
- `tsconfig`: Path to `tsconfig.json` (default: `./tsconfig.json`)
- `skip_svelte_resolve_errors`: Filter out `TS2614` errors referencing `*.svelte` files (common false positives in Svelte projects)
- `ignore_codes`: List of TypeScript error codes to ignore (e.g., `["TS2614", "TS6133"]`)

#### Using TypeScript Type Checking

**Console Output:**
```bash
python main.py --language javascript --path src/
```

**File Output:**
```bash
python main.py --language javascript --path src/ --output reports/
```

This creates `reports/tsc_analyze.csv` with all TypeScript violations.

#### First-Time Setup

If `tsc` is not found in your PATH, you'll be prompted to enter the path to the executable (e.g., `node_modules/.bin/tsc`). The path will be saved to `settings.ini` for future use.

## Project Structure

```
cli-code-analyzer/
├── main.py                     # CLI entry point
├── analyzer.py                 # Main analyzer orchestration
├── ruff_fixer.py               # Ruff auto-fix tool for Python
├── file_discovery.py           # File discovery logic
├── config.py                   # Configuration loading
├── settings.py                 # Settings management (INI-based)
├── models.py                   # Data models (Violation, Severity, etc.)
├── reporter.py                 # Report formatting (minimal/normal/verbose/file)
├── rules/
│   ├── __init__.py            # Rules module
│   ├── base.py                # Base rule class
│   ├── max_lines.py           # Max lines per file rule
│   ├── pmd_duplicates.py      # PMD duplicate code detection rule
│   ├── dart_analyze.py        # Dart static analysis rule
│   ├── flutter_analyze.py     # Flutter static analysis rule
│   ├── dart_code_linter.py    # Dart code metrics analysis rule
│   ├── ruff_analyze.py        # Ruff Python linter rule
│   ├── eslint_analyze.py      # ESLint JavaScript/TypeScript/Svelte rule
│   ├── svelte_check.py        # Svelte type checking rule
│   └── tsc_analyze.py         # TypeScript type checking rule (tsc --noEmit)
├── rules.json                  # Default rules configuration
├── settings.ini                # User settings (PMD path, Dart path, etc.)
├── fix_python_ruff_issues.bat  # Batch file to auto-fix Python issues
└── example/                    # Example project for testing
    ├── rules.json             # Example rules (warning:200, error:300)
    └── lib/
        └── sample_widget.dart  # Sample Flutter file (350+ lines)
```

## Exit Codes

- `0`: No errors found (warnings may exist)
- `1`: Errors found or execution failure

## Use Cases

### CI/CD Integration

Add to your CI/CD pipeline to enforce code quality:

```bash
# GitHub Actions, GitLab CI, etc.
python main.py --language flutter --path lib/ --loglevel error --verbosity minimal
```

This will fail the build if any files exceed the error threshold.

**With File Output for Artifact Storage:**

```bash
# Save reports as CI artifacts
python main.py --language flutter --path lib/ --output ci-reports/
```

The generated reports can be stored as CI artifacts for later review.

### Pre-commit Hook

Create a pre-commit hook to check code before commits:

```bash
#!/bin/bash
python main.py --language flutter --path lib/ --verbosity minimal
```

### Code Review

Use during code reviews to identify files that need refactoring:

```bash
python main.py --language flutter --path lib/ --verbosity verbose
```

### Duplicate Code Refactoring

Find and eliminate duplicate code across your project:

```bash
# Generate duplicate code report
python main.py --language flutter --path lib/ --output reports/

# Review the reports/duplicate_code.csv file
# Refactor duplicated code into reusable functions/classes
```

## Extending the Analyzer

### Adding New Rules

1. Create a new rule class in `rules/` directory:

```python
# rules/my_custom_rule.py
from rules.base import BaseRule
from models import Violation, Severity

class MyCustomRule(BaseRule):
    def check(self, file_path):
        # Your rule logic here
        violations = []
        # ... check logic ...
        return violations
```

2. Register the rule in `analyzer.py`

3. Add configuration to `rules.json`

### Adding New Languages

1. Update `file_discovery.py` with new file extensions:

```python
LANGUAGE_EXTENSIONS = {
    'flutter': ['.dart'],
    'python': ['.py'],  # Add new language
}
```

2. Test with your language-specific code

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/BenjaminKobjolke/cli-code-analyzer).
