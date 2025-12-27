# Implementation Plan: Ruff Linter Support

## Status: IN PROGRESS

## Overview

Add Ruff (fast Python linter) as a new rule for Python projects.

**Ruff JSON output format:**
```json
{
  "code": "F401",
  "filename": "path/to/file.py",
  "location": {"column": 8, "row": 4},
  "message": "`shutil` imported but unused",
  "url": "https://docs.astral.sh/ruff/rules/..."
}
```

---

## Files to Create/Modify

### 1. Create `rules/ruff_analyze.py` (NEW)

Follow pattern from `dart_analyze.py`:
- Inherit from `BaseRule`
- Execute once per analysis (guard pattern)
- Use `_get_tool_path()` for ruff path discovery
- Use `_run_subprocess()` for execution
- Parse JSON output into `Violation` objects
- Support log level filtering
- Write CSV output if output_folder specified

**Configuration:**
```json
{
  "ruff_analyze": {
    "enabled": true,
    "select": ["E", "F", "W"],
    "ignore": [],
    "exclude_patterns": ["venv/**", "__pycache__/**"]
  }
}
```

### 2. Update `settings.py`

Add methods:
- `get_ruff_path()` - Read from settings.ini `[paths]` section
- `prompt_and_save_ruff_path()` - Prompt user and save to settings.ini

### 3. Update `rules/__init__.py`

```python
from rules.ruff_analyze import RuffAnalyzeRule
__all__ = [..., 'RuffAnalyzeRule']
```

### 4. Update `analyzer.py`

Add Ruff integration (project-wide rule, like pmd_duplicates):
```python
# Run ruff analyze check (once per analysis, not per file)
if self.config.is_rule_enabled('ruff_analyze'):
    rule_config = self.config.get_rule('ruff_analyze')
    ruff_log_level = self._resolve_log_level('ruff_analyze')
    ruff_rule = RuffAnalyzeRule(
        rule_config,
        self.base_path,
        self.output_folder,
        ruff_log_level,
        self.max_errors,
        self.rules_file
    )
    if self.files:
        violations = ruff_rule.check(self.files[0])
        self.violations.extend(violations)
```

### 5. Update `docs/setup/PYTHON.md`

Add to Available Rules table:
| Rule | Description |
|------|-------------|
| `ruff_analyze` | Fast Python linter (800+ rules, replaces flake8/pylint) |

Add configuration example with select/ignore options.

### 6. Update config files

Add ruff_analyze to:
- `D:\GIT\BenjaminKobjolke\cli-code-analyzer\code_analysis_rules.json`
- `D:\GIT\Intern\ai-cmd\code_analysis_rules.json`

---

## Implementation Details

### Severity Mapping

```python
def _map_ruff_severity(self, code: str) -> Severity:
    """Map Ruff rule code to severity."""
    prefix = code[0] if code else ''
    if prefix == 'E':  # pycodestyle errors
        return Severity.ERROR
    elif prefix in ('F', 'W'):  # Pyflakes, warnings
        return Severity.WARNING
    else:  # All others (B, C, I, N, etc.)
        return Severity.INFO
```

### Command Construction

```python
cmd = [ruff_path, 'check', '--output-format', 'json']

# Add select rules if configured
if 'select' in self.config:
    cmd.extend(['--select', ','.join(self.config['select'])])

# Add ignore rules if configured
if 'ignore' in self.config:
    cmd.extend(['--ignore', ','.join(self.config['ignore'])])

# Add exclude patterns
if 'exclude_patterns' in self.config:
    for pattern in self.config['exclude_patterns']:
        cmd.extend(['--exclude', pattern])

cmd.append(str(self.base_path))
```

### CSV Output

Headers: `file`, `line`, `column`, `severity`, `code`, `message`, `url`

---

## Execution Order

1. Update `settings.py` - Add ruff path methods
2. Create `rules/ruff_analyze.py` - Main implementation
3. Update `rules/__init__.py` - Register rule
4. Update `analyzer.py` - Integrate rule
5. Update `docs/setup/PYTHON.md` - Documentation
6. Update config files - Enable for projects
7. Verify with `python -m py_compile`

---

## Reference Files

- Pattern to follow: `rules/dart_analyze.py`
- Settings pattern: `settings.py` (get_dart_path, prompt_and_save_dart_path)
- Registration: `rules/__init__.py`
- Integration: `analyzer.py`
