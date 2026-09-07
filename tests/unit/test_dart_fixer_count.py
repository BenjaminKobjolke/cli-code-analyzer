"""dart_fixer must report the number of fixes `dart fix` made / proposed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dart_fixer import find_project_root, parse_fixed_count

APPLIED = "Computing fixes in app...\nApplying fixes...\n\nlib/a.dart\n  unnecessary_new • 2 fixes\n\n2 fixes made in 1 file.\n"
APPLIED_ONE = "1 fix made in 1 file.\n"
DRY_RUN = "Computing fixes in app (dry run)...\n\n3 proposed fixes in 2 files.\n"
CLEAN = "Computing fixes in app (dry run)...\nNothing to fix!\n"


def test_applied_count_is_parsed():
    assert parse_fixed_count(APPLIED) == 2


def test_singular_fix_is_parsed():
    assert parse_fixed_count(APPLIED_ONE) == 1


def test_dry_run_proposed_count_is_parsed():
    assert parse_fixed_count(DRY_RUN) == 3


def test_clean_run_is_zero():
    assert parse_fixed_count(CLEAN) == 0


def test_project_root_walks_up_to_pubspec(tmp_path):
    (tmp_path / 'pubspec.yaml').write_text('name: app\n', encoding='utf-8')
    nested = tmp_path / 'lib' / 'feature'
    nested.mkdir(parents=True)
    assert find_project_root(str(nested)) == tmp_path.resolve()


def test_project_root_falls_back_to_path(tmp_path):
    assert find_project_root(str(tmp_path)) == tmp_path.resolve()
