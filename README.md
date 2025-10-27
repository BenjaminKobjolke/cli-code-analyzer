# CLI Code Analyzer

A flexible command-line tool for analyzing code files based on configurable rules. Specifically designed for AI-generated code to ensure quality and maintainability.

## Features

- **Multi-language support**: Currently supports Flutter/Dart (extensible to other languages)
- **Configurable rules**: Define custom rules via JSON configuration
- **Multiple output formats**: Minimal, normal, and verbose output modes
- **Severity filtering**: Filter violations by error or warning levels
- **Line count rules**: Check maximum lines per file with warning and error thresholds
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

## Usage

### Basic Command Structure

```bash
python main.py --language <language> --path <path> [options]
```

### Command Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--language` | Yes | - | Programming language to analyze (currently: `flutter`) |
| `--path` | Yes | - | Path to analyze - can be a **directory** (analyzes all files recursively) or a **single file** |
| `--rules` | No | `rules.json` | Path to the rules JSON configuration file |
| `--output` | No | `normal` | Output verbosity level: `minimal`, `normal`, or `verbose` |
| `--loglevel` | No | `all` | Filter violations by severity: `error`, `warning`, or `all` |

## Examples

### Test with the Example Directory

The project includes an `example/` directory with a sample Flutter project that exceeds the configured line limits.

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
python main.py --language flutter --path example/lib --rules example/rules.json --output minimal
```

**Output:**
```
sample_widget.dart errors:1 warnings:0 maxlines>350
Summary: 1 error(s), 0 warning(s)
```

#### 3. Verbose Output Format
```bash
python main.py --language flutter --path example/lib --rules example/rules.json --output verbose
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
python main.py --language flutter --path example/lib --rules example/rules.json --output minimal --loglevel error
```

**Output:**
```
sample_widget.dart errors:1 maxlines>350
Summary: 1 error(s)
```

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

## Project Structure

```
cli-code-analyzer/
├── main.py                     # CLI entry point
├── analyzer.py                 # Main analyzer orchestration
├── file_discovery.py           # File discovery logic
├── config.py                   # Configuration loading
├── models.py                   # Data models (Violation, Severity, etc.)
├── reporter.py                 # Report formatting (minimal/normal/verbose)
├── rules/
│   ├── __init__.py            # Rules module
│   ├── base.py                # Base rule class
│   └── max_lines.py           # Max lines per file rule
├── rules.json                  # Default rules configuration
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
python main.py --language flutter --path lib/ --loglevel error --output minimal
```

This will fail the build if any files exceed the error threshold.

### Pre-commit Hook

Create a pre-commit hook to check code before commits:

```bash
#!/bin/bash
python main.py --language flutter --path lib/ --output minimal
```

### Code Review

Use during code reviews to identify files that need refactoring:

```bash
python main.py --language flutter --path lib/ --output verbose
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
