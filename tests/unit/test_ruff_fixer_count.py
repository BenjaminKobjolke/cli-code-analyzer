"""The fixer must report how many issues it FIXED, not how many it found.

Regression guard: ruff prints "Found 1025 errors (186 fixed, 839 remaining)."
and the old regex read the 1025, so a run that fixed 186 things announced
"Fixed 1025 issue(s)".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ruff_fixer import parse_fixed_count

FOUND_AND_FIXED = "Found 1025 errors (186 fixed, 839 remaining).\n"
FOUND_ONLY = "Found 50 errors.\n"
CLEAN = "All checks passed!\n"
# --diff runs report what they WOULD fix instead of a "(N fixed" clause.
DRY_RUN = "Would fix 146 errors (40 additional fixes available with `--unsafe-fixes`).\n"


def test_reads_the_fixed_count_not_the_found_count():
    assert parse_fixed_count(FOUND_AND_FIXED) == 186


def test_nothing_fixed_when_ruff_only_reports_findings():
    assert parse_fixed_count(FOUND_ONLY) == 0


def test_clean_run_is_zero():
    assert parse_fixed_count(CLEAN) == 0


def test_singular_fix_is_parsed():
    assert parse_fixed_count("Found 1 error (1 fixed, 0 remaining).\n") == 1


def test_dry_run_would_fix_count_is_parsed():
    assert parse_fixed_count(DRY_RUN) == 146
