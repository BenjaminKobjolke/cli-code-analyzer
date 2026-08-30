"""The ruff fixer must never autofix import-removal rules.

Regression guard: `ruff check --fix` with F selected deleted re-export imports
it could not see through — `from .zip import *` in a package __init__.py and a
name re-exported through a plain module — silently breaking the target project
at runtime. Those rules are now force-ignored for the fix pass.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ruff_fixer import UNSAFE_FIX_RULES, build_fix_command


def _ignored(cmd):
    return cmd[cmd.index("--ignore") + 1].split(",")


def test_import_rules_are_force_ignored_when_no_ignore_configured():
    cmd = build_fix_command("ruff", ".", {"select": ["E", "F", "W"]}, dry_run=False)
    assert set(UNSAFE_FIX_RULES) <= set(_ignored(cmd))


def test_import_rules_are_appended_to_configured_ignores():
    cmd = build_fix_command("ruff", ".", {"ignore": ["W191"]}, dry_run=False)
    ignored = _ignored(cmd)
    assert "W191" in ignored
    assert set(UNSAFE_FIX_RULES) <= set(ignored)


def test_configured_ignore_is_not_duplicated():
    config = {"ignore": [UNSAFE_FIX_RULES[0]]}
    ignored = _ignored(build_fix_command("ruff", ".", config, dry_run=False))
    assert ignored.count(UNSAFE_FIX_RULES[0]) == 1


def test_f401_is_blocked():
    """The rule that deleted the re-exports."""
    assert "F401" in UNSAFE_FIX_RULES


def test_per_language_exclude_dict_is_expanded():
    config = {"exclude_patterns": {"python": ["target/**", "venv/**"]}}
    cmd = build_fix_command("ruff", ".", config, dry_run=False, languages=["python"])
    assert "target/**" in cmd
    assert "venv/**" in cmd
    assert "python" not in cmd


def test_dry_run_uses_diff_not_fix():
    assert "--diff" in build_fix_command("ruff", ".", {}, dry_run=True)
    assert "--fix" not in build_fix_command("ruff", ".", {}, dry_run=True)
