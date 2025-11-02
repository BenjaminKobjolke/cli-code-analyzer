# Creating a New Analyzer

This guide walks you through creating a new analyzer (rule) for the CLI Code Analyzer, including support for file-specific threshold exceptions.

## Table of Contents
1. [Overview](#overview)
2. [Step-by-Step Guide](#step-by-step-guide)
3. [Exception Support](#exception-support)
4. [Testing Your Analyzer](#testing-your-analyzer)
5. [Example: Complete Analyzer](#example-complete-analyzer)

---

## Overview

Analyzers in this project are implemented as **rules** that inherit from `BaseRule`. Each rule:
- Checks files or projects for specific issues
- Returns `Violation` objects when issues are found
- Supports configurable thresholds (warning/error levels)
- Can support file-specific exceptions for threshold overrides

---

## Step-by-Step Guide

### Step 1: Create the Rule File

Create a new Python file in `rules/your_analyzer_name.py`:

```python
"""
Your Analyzer Name - Description of what it checks
"""

from pathlib import Path
from typing import List, Optional
from rules.base import BaseRule
from models import Violation, Severity

class YourAnalyzerRule(BaseRule):
    """Rule to check for [describe what this checks]"""

    def __init__(self, config: dict, base_path: Path = None, max_errors: Optional[int] = None, rules_file_path: str = None):
        """Initialize Your Analyzer rule.

        Args:
            config: Rule configuration from rules.json
            base_path: Base path for analysis
            max_errors: Optional limit on number of violations
            rules_file_path: Path to the rules.json file (for exception matching)
        """
        super().__init__(config, base_path, max_errors, rules_file_path)

        # Extract your configuration values
        self.warning_threshold = config.get('warning', 100)
        self.error_threshold = config.get('error', 200)
        # Add any other config values you need

    def check(self, file_path: Path) -> List[Violation]:
        """
        Check the file against this rule

        Args:
            file_path: Path to the file to check

        Returns:
            List of violations found
        """
        violations = []

        # TODO: Implement your analysis logic here

        return violations
```

### Step 2: Add Your Rule to the Imports

Edit `rules/__init__.py` to export your new rule:

```python
from rules.max_lines import MaxLinesRule
from rules.pmd_duplicates import PMDDuplicatesRule
from rules.dart_analyze import DartAnalyzeRule
from rules.dart_code_linter import DartCodeLinterRule
from rules.your_analyzer_name import YourAnalyzerRule  # Add this line

__all__ = [
    'MaxLinesRule',
    'PMDDuplicatesRule',
    'DartAnalyzeRule',
    'DartCodeLinterRule',
    'YourAnalyzerRule',  # Add this line
]
```

### Step 3: Register the Rule in the Analyzer

Edit `analyzer.py` to integrate your rule:

**Option A: Per-File Analysis** (like MaxLinesRule)
```python
# In the _check_file method around line 90
def _check_file(self, file_path: Path):
    """Check a single file against all enabled rules"""
    # ... existing rules ...

    # Check your analyzer rule
    if self.config.is_rule_enabled('your_analyzer_name'):
        rule_config = self.config.get_rule('your_analyzer_name')
        rule = YourAnalyzerRule(rule_config, self.base_path, self.max_errors, self.rules_file)
        violations = rule.check(file_path)
        self.violations.extend(violations)
```

**Option B: Project-Wide Analysis** (like DartAnalyzeRule)
```python
# In the analyze method around line 70
def analyze(self):
    """Run the analysis"""
    # ... existing code ...

    # Run your analyzer check (once per analysis, not per file)
    if self.config.is_rule_enabled('your_analyzer_name'):
        rule_config = self.config.get_rule('your_analyzer_name')
        your_rule = YourAnalyzerRule(
            rule_config,
            self.base_path,
            self.max_errors,
            self.rules_file
        )
        # Call it once with any file
        if self.files:
            violations = your_rule.check(self.files[0])
            self.violations.extend(violations)
```

Don't forget to import your rule at the top of `analyzer.py`:
```python
from rules import MaxLinesRule, PMDDuplicatesRule, DartAnalyzeRule, DartCodeLinterRule, YourAnalyzerRule
```

### Step 4: Add Configuration to rules.json

Add your rule configuration to `rules.json`:

```json
{
  "your_analyzer_name": {
    "enabled": true,
    "warning": 100,
    "error": 200,
    "exceptions": [
      {
        "file": "lib/generated/*.dart",
        "warning": 500,
        "error": 1000
      }
    ]
  }
}
```

---

## Exception Support

The `BaseRule` class provides built-in support for file-specific threshold exceptions. Here's how to use it:

### Basic Implementation (Simple Thresholds)

For analyzers with simple warning/error thresholds (like `max_lines_per_file`):

```python
def check(self, file_path: Path) -> List[Violation]:
    """Check the file against this rule"""
    violations = []

    # Your analysis logic
    metric_value = self._calculate_metric(file_path)
    relative_path = self._get_relative_path(file_path)

    # Get thresholds for this specific file (automatically checks exceptions)
    thresholds = self._get_threshold_for_file(file_path, self.config)
    error_threshold = thresholds.get('error')
    warning_threshold = thresholds.get('warning')

    # Check thresholds
    if error_threshold and metric_value >= error_threshold:
        violations.append(Violation(
            file_path=relative_path,
            rule_name='your_analyzer_name',
            severity=Severity.ERROR,
            message=f"Metric value {metric_value} exceeds limit {error_threshold}"
        ))
    elif warning_threshold and metric_value >= warning_threshold:
        violations.append(Violation(
            file_path=relative_path,
            rule_name='your_analyzer_name',
            severity=Severity.WARNING,
            message=f"Metric value {metric_value} exceeds warning {warning_threshold}"
        ))

    return violations
```

### Advanced Implementation (Multiple Metrics)

For analyzers with multiple metrics (like `dart_code_linter`):

```python
def _check_metric_threshold(
    self,
    file_path: str,
    metric_name: str,
    metric_value: float,
    thresholds: Dict[str, Dict[str, int]]
) -> Optional[Violation]:
    """Check if a metric exceeds configured thresholds.

    Args:
        file_path: Path to the file
        metric_name: Name of the metric being checked
        metric_value: Current value of the metric
        thresholds: Configured thresholds from rules.json

    Returns:
        Violation if threshold exceeded, None otherwise
    """
    # Check if this metric has configured thresholds
    if metric_name not in thresholds:
        return None

    threshold_config = thresholds[metric_name]

    # Check for file-specific exceptions
    effective_thresholds = self._get_threshold_for_file(
        Path(file_path),
        threshold_config,
        metric_name  # Optional: pass metric name for debugging
    )
    error_threshold = effective_thresholds.get('error')
    warning_threshold = effective_thresholds.get('warning')

    # Determine severity
    severity = None
    if error_threshold and metric_value >= error_threshold:
        severity = Severity.ERROR
        threshold_value = error_threshold
    elif warning_threshold and metric_value >= warning_threshold:
        severity = Severity.WARNING
        threshold_value = warning_threshold

    if severity is None:
        return None

    # Create relative path
    rel_path = self._get_relative_path(Path(file_path))

    return Violation(
        file_path=rel_path,
        rule_name='your_analyzer_name',
        severity=severity,
        message=f"{metric_name} = {metric_value} >= {threshold_value}"
    )
```

### Path Matching Strategies

The `_get_threshold_for_file()` method tries multiple path matching strategies in order:

1. **Relative to `--path` (base_path)**
   - Pattern: `services/preferences_service.dart`
   - Matches file: `<base_path>/services/preferences_service.dart`

2. **Relative to rules.json location**
   - Pattern: `lib/services/preferences_service.dart`
   - Matches file: `<rules.json parent>/lib/services/preferences_service.dart`

3. **Filename only**
   - Pattern: `preferences_service.dart`
   - Matches any file with this name

4. **Glob patterns** (supported in all strategies)
   - Pattern: `services/*.dart`
   - Pattern: `**/test_*.dart`
   - Pattern: `lib/models/**/*.dart`

### Exception Configuration Examples

**Simple exception (exact file path):**
```json
{
  "your_analyzer_name": {
    "enabled": true,
    "warning": 100,
    "error": 200,
    "exceptions": [
      {
        "file": "lib/services/preferences_service.dart",
        "warning": 500,
        "error": 800
      }
    ]
  }
}
```

**Glob pattern exception:**
```json
{
  "your_analyzer_name": {
    "enabled": true,
    "warning": 100,
    "error": 200,
    "exceptions": [
      {
        "file": "lib/generated/*.dart",
        "warning": 1000,
        "error": 2000
      },
      {
        "file": "**/test_*.dart",
        "warning": 300,
        "error": 500
      }
    ]
  }
}
```

**Multiple metrics with different exceptions (like dart_code_linter):**
```json
{
  "your_analyzer_name": {
    "enabled": true,
    "metrics": {
      "complexity": {
        "warning": 10,
        "error": 20,
        "exceptions": [
          {
            "file": "lib/screens/*_screen.dart",
            "warning": 30,
            "error": 40
          }
        ]
      },
      "method-count": {
        "warning": 15,
        "error": 25,
        "exceptions": [
          {
            "file": "lib/services/*.dart",
            "warning": 50,
            "error": 80
          }
        ]
      }
    }
  }
}
```

---

## Testing Your Analyzer

### 1. Manual Testing

Create a test file and run your analyzer:

```bash
python main.py --language flutter --path test_files/ --rules rules.json --verbosity verbose
```

### 2. Test with Exceptions

Create a `test_rules.json` with your analyzer configured:

```json
{
  "your_analyzer_name": {
    "enabled": true,
    "warning": 10,
    "error": 20,
    "exceptions": [
      {
        "file": "test_files/special_case.dart",
        "warning": 100,
        "error": 200
      }
    ]
  }
}
```

Run the analyzer:
```bash
python main.py --language flutter --path test_files/ --rules test_rules.json
```

Verify that:
- Regular files use the base thresholds (10/20)
- Exception files use the override thresholds (100/200)
- Path matching works for all strategies

### 3. Debug Output

Add debug prints to verify exception matching:

```python
thresholds = self._get_threshold_for_file(file_path, self.config)
print(f"DEBUG: File {file_path}")
print(f"DEBUG: Using thresholds: warning={thresholds.get('warning')}, error={thresholds.get('error')}")
```

---

## Example: Complete Analyzer

Here's a complete example of a complexity analyzer with exception support:

```python
"""
Code Complexity Analyzer - Checks cyclomatic complexity
"""

from pathlib import Path
from typing import List, Optional
from rules.base import BaseRule
from models import Violation, Severity

class ComplexityRule(BaseRule):
    """Rule to check cyclomatic complexity of functions"""

    def __init__(self, config: dict, base_path: Path = None, max_errors: Optional[int] = None, rules_file_path: str = None):
        """Initialize Complexity rule.

        Args:
            config: Rule configuration from rules.json
            base_path: Base path for analysis
            max_errors: Optional limit on number of violations
            rules_file_path: Path to the rules.json file
        """
        super().__init__(config, base_path, max_errors, rules_file_path)
        self.warning_threshold = config.get('warning', 10)
        self.error_threshold = config.get('error', 20)

    def check(self, file_path: Path) -> List[Violation]:
        """
        Check cyclomatic complexity of all functions in the file

        Args:
            file_path: Path to the file to check

        Returns:
            List of violations found
        """
        violations = []

        # Calculate complexity (pseudo-code)
        functions = self._parse_functions(file_path)

        for func_name, complexity in functions.items():
            # Get thresholds for this specific file (checks exceptions automatically)
            thresholds = self._get_threshold_for_file(file_path, self.config)
            error_threshold = thresholds.get('error')
            warning_threshold = thresholds.get('warning')

            # Check thresholds
            severity = None
            threshold_value = None

            if error_threshold and complexity >= error_threshold:
                severity = Severity.ERROR
                threshold_value = error_threshold
            elif warning_threshold and complexity >= warning_threshold:
                severity = Severity.WARNING
                threshold_value = warning_threshold

            if severity:
                relative_path = self._get_relative_path(file_path)
                violations.append(Violation(
                    file_path=relative_path,
                    rule_name='complexity',
                    severity=severity,
                    message=f"Function '{func_name}' has complexity {complexity} (threshold: {threshold_value})"
                ))

        return violations

    def _parse_functions(self, file_path: Path) -> dict:
        """Parse file and calculate complexity for each function.

        Returns:
            Dict mapping function names to complexity scores
        """
        # TODO: Implement your complexity calculation logic
        # This is pseudo-code - replace with actual implementation
        functions = {}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Parse and calculate complexity
                # functions['myFunction'] = 15
                # functions['anotherFunction'] = 25
        except Exception as e:
            print(f"Warning: Could not analyze {file_path}: {e}")

        return functions
```

**Configuration in rules.json:**

```json
{
  "complexity": {
    "enabled": true,
    "warning": 10,
    "error": 20,
    "exceptions": [
      {
        "file": "lib/screens/*_screen.dart",
        "warning": 30,
        "error": 40,
        "reason": "Screens can be complex due to UI logic"
      },
      {
        "file": "lib/services/api_service.dart",
        "warning": 50,
        "error": 80,
        "reason": "API service handles many endpoints"
      }
    ]
  }
}
```

**Integration in analyzer.py:**

```python
# Add to imports
from rules import MaxLinesRule, PMDDuplicatesRule, DartAnalyzeRule, DartCodeLinterRule, ComplexityRule

# Add to _check_file method
def _check_file(self, file_path: Path):
    """Check a single file against all enabled rules"""
    # ... existing rules ...

    # Check complexity rule
    if self.config.is_rule_enabled('complexity'):
        rule_config = self.config.get_rule('complexity')
        rule = ComplexityRule(rule_config, self.base_path, self.max_errors, self.rules_file)
        violations = rule.check(file_path)
        self.violations.extend(violations)
```

---

## Best Practices

1. **Always inherit from BaseRule** - It provides essential utilities and exception support

2. **Use `_get_relative_path()`** - Always convert absolute paths to relative paths for violation output

3. **Support exceptions** - Always use `_get_threshold_for_file()` instead of reading thresholds directly

4. **Handle errors gracefully** - Wrap file operations in try-except blocks

5. **Document your thresholds** - Explain what the warning and error values represent

6. **Provide context** - Include helpful information in violation messages (function name, line number, etc.)

7. **Test with edge cases**:
   - Files that match multiple exception patterns
   - Files with special characters in paths
   - Very large files
   - Files with encoding issues

8. **Add debug output** - Use print statements during development to verify exception matching

---

## Helper Methods from BaseRule

The following methods are available from `BaseRule`:

### `_get_relative_path(file_path: Path) -> str`
Converts an absolute file path to a relative path from `base_path`.

```python
rel_path = self._get_relative_path(Path('/full/path/to/file.dart'))
# Returns: 'path/to/file.dart'
```

### `_count_lines(file_path: Path) -> int`
Counts the number of lines in a file.

```python
line_count = self._count_lines(file_path)
```

### `_get_threshold_for_file(file_path: Path, threshold_config: dict, metric_id: str = None) -> dict`
Gets thresholds for a specific file, checking for exceptions.

```python
thresholds = self._get_threshold_for_file(file_path, self.config)
error_threshold = thresholds.get('error')
warning_threshold = thresholds.get('warning')
```

### `_match_file_path(file_path: str, pattern: str) -> bool`
Checks if a file path matches a pattern (exact, glob, or ends-with).

```python
if self._match_file_path('lib/services/api.dart', 'services/*.dart'):
    # File matches pattern
```

---

## Common Patterns

### Pattern 1: Single Metric per File

```python
def check(self, file_path: Path) -> List[Violation]:
    violations = []
    metric_value = self._analyze_file(file_path)

    thresholds = self._get_threshold_for_file(file_path, self.config)
    # ... check thresholds ...

    return violations
```

### Pattern 2: Multiple Metrics per File

```python
def check(self, file_path: Path) -> List[Violation]:
    violations = []
    metrics = self._analyze_file(file_path)  # Returns dict of metrics

    metric_thresholds = self.config.get('metrics', {})

    for metric_name, metric_value in metrics.items():
        if metric_name in metric_thresholds:
            violation = self._check_metric_threshold(
                file_path, metric_name, metric_value, metric_thresholds
            )
            if violation:
                violations.append(violation)

    return violations
```

### Pattern 3: Project-Wide Analysis

```python
def check(self, file_path: Path) -> List[Violation]:
    # Only execute once
    if self._executed:
        return []
    self._executed = True

    # Analyze entire project
    violations = self._analyze_project()

    return violations
```

---

## Troubleshooting

### Exception not matching files

**Problem:** Exception defined but files still use base thresholds.

**Solutions:**
1. Check path separators - use forward slashes `/` in patterns
2. Verify pattern relative to either `--path` or rules.json location
3. Add debug output to see what paths are being compared:
   ```python
   print(f"DEBUG: File path: {file_path}")
   print(f"DEBUG: Exception pattern: {exception_pattern}")
   ```

### Import errors

**Problem:** `ImportError: cannot import name 'YourAnalyzerRule'`

**Solutions:**
1. Verify you added the import to `rules/__init__.py`
2. Check class name matches between file and import
3. Ensure Python can find the module (check `__pycache__`)

### No violations reported

**Problem:** Analyzer runs but reports no violations.

**Solutions:**
1. Verify `enabled: true` in rules.json
2. Check that `check()` method returns violations list
3. Add print statements to verify analyzer is being called
4. Verify file extensions match your analyzer's expectations

---

## Summary Checklist

When creating a new analyzer, ensure you:

- [ ] Create rule file in `rules/your_analyzer_name.py`
- [ ] Inherit from `BaseRule`
- [ ] Accept `rules_file_path` parameter in `__init__()`
- [ ] Call `super().__init__()` with all parameters
- [ ] Implement `check()` method
- [ ] Use `_get_threshold_for_file()` for exception support
- [ ] Add import to `rules/__init__.py`
- [ ] Register in `analyzer.py` (either per-file or project-wide)
- [ ] Add configuration to `rules.json`
- [ ] Test with and without exceptions
- [ ] Document your analyzer's purpose and thresholds

---

**Happy coding!** 🎉
