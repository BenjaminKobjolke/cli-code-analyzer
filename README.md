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
- **Dart code metrics**: Integrated [dart_code_linter](https://pub.dev/packages/dart_code_linter) for advanced metrics (cyclomatic complexity, maintainability index, technical debt, etc.)
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

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--language` | Yes | - | Programming language to analyze. **Line counting:** `flutter`, `python`. **Duplicate detection (PMD):** `dart`, `python`, `java`, `javascript`, `typescript` |
| `--path` | Yes | - | Path to the code directory (analyzes recursively) or single file to analyze |
| `--rules` | No | `rules.json` | Path to the rules JSON configuration file |
| `--verbosity` | No | `normal` | Output verbosity level: `minimal`, `normal`, or `verbose` |
| `--output` | No | - | Path to output folder for reports. If set, saves reports to files (`line_count_report.txt`, `duplicate_code.csv`) instead of console output |
| `--loglevel` | No | `all` | Filter violations by severity: `error`, `warning`, or `all` |

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

## Project Structure

```
cli-code-analyzer/
├── main.py                     # CLI entry point
├── analyzer.py                 # Main analyzer orchestration
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
│   └── dart_code_linter.py    # Dart code metrics analysis rule
├── rules.json                  # Default rules configuration
├── settings.ini                # User settings (PMD path, Dart path, etc.)
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
