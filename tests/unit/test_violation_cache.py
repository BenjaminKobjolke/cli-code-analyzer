"""Unit tests for ViolationCache validity (age, rules hash, file set, mtimes)."""

import os
import sqlite3

from analyzer_fingerprint import compute_analyzer_hash
from models import Severity, Violation
from violation_cache import ViolationCache

RULES_HASH = "hash-1"


def _make_project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.py").write_text("print('a')\n")
    (proj / "b.py").write_text("print('b')\n")
    return proj


def _current_files(proj):
    return sorted(proj.glob("*.py"))


def _save_cache(tmp_path, proj):
    cache = ViolationCache(tmp_path / "cache.db")
    violation = Violation(
        file_path="a.py",
        rule_name="rule",
        severity=Severity.WARNING,
        message="msg",
        line=1,
        column=1,
    )
    cache.save([violation], RULES_HASH, ["python"], str(proj), ["a.py", "b.py"])
    return cache


def _make_analyzer_source(tmp_path):
    source_root = tmp_path / "analyzer"
    rules_dir = source_root / "rules"
    rules_dir.mkdir(parents=True)
    (source_root / "main.py").write_text("MAIN = 1\n")
    (source_root / "conftest.py").write_text("TEST_CONFIG = 1\n")
    (rules_dir / "sample.py").write_text("RULE = 1\n")
    for excluded_dir in ("tests", "example", "venv", ".venv", "__pycache__"):
        directory = source_root / excluded_dir
        directory.mkdir()
        (directory / "ignored.py").write_text("IGNORED = 1\n")
    return source_root


def _touch_future(path, seconds_ahead=10):
    future = os.stat(path).st_mtime + seconds_ahead
    os.utime(path, (future, future))


def test_valid_when_unchanged(tmp_path):
    proj = _make_project(tmp_path)
    cache = _save_cache(tmp_path, proj)

    assert cache.is_valid(60, RULES_HASH,
                          current_files=_current_files(proj),
                          base_path=str(proj))


def test_invalid_when_file_modified(tmp_path):
    proj = _make_project(tmp_path)
    cache = _save_cache(tmp_path, proj)
    _touch_future(proj / "a.py")

    assert not cache.is_valid(60, RULES_HASH,
                              current_files=_current_files(proj),
                              base_path=str(proj))


def test_invalid_when_file_added(tmp_path):
    proj = _make_project(tmp_path)
    cache = _save_cache(tmp_path, proj)
    new_file = proj / "c.py"
    new_file.write_text("print('c')\n")
    # Backdate so only the set check (not the mtime check) can catch it.
    past = os.stat(proj / "a.py").st_mtime - 100
    os.utime(new_file, (past, past))

    assert not cache.is_valid(60, RULES_HASH,
                              current_files=_current_files(proj),
                              base_path=str(proj))


def test_invalid_when_file_deleted(tmp_path):
    proj = _make_project(tmp_path)
    cache = _save_cache(tmp_path, proj)
    (proj / "b.py").unlink()

    assert not cache.is_valid(60, RULES_HASH,
                              current_files=_current_files(proj),
                              base_path=str(proj))


def test_invalid_on_rules_hash_mismatch(tmp_path):
    proj = _make_project(tmp_path)
    cache = _save_cache(tmp_path, proj)

    assert not cache.is_valid(60, "other-hash",
                              current_files=_current_files(proj),
                              base_path=str(proj))


def test_invalid_on_analyzer_hash_mismatch(tmp_path):
    proj = _make_project(tmp_path)
    cache = _save_cache(tmp_path, proj)
    with sqlite3.connect(str(tmp_path / "cache.db")) as con:
        con.execute(
            "INSERT OR REPLACE INTO cache_meta VALUES ('analyzer_hash', 'stale-hash')"
        )

    assert not cache.is_valid(60, RULES_HASH,
                              current_files=_current_files(proj),
                              base_path=str(proj))


def test_invalid_when_analyzer_hash_missing(tmp_path):
    proj = _make_project(tmp_path)
    cache = _save_cache(tmp_path, proj)
    with sqlite3.connect(str(tmp_path / "cache.db")) as con:
        con.execute("DELETE FROM cache_meta WHERE key = 'analyzer_hash'")

    assert not cache.is_valid(60, RULES_HASH,
                              current_files=_current_files(proj),
                              base_path=str(proj))


def test_invalid_when_expired(tmp_path):
    proj = _make_project(tmp_path)
    cache = _save_cache(tmp_path, proj)
    con = sqlite3.connect(str(tmp_path / "cache.db"))
    con.execute(
        "UPDATE cache_meta SET value = '2000-01-01T00:00:00+00:00' WHERE key = 'created_at'"
    )
    con.commit()
    con.close()

    assert not cache.is_valid(60, RULES_HASH,
                              current_files=_current_files(proj),
                              base_path=str(proj))


def test_invalid_when_newest_mtime_missing(tmp_path):
    """Old cache dbs (pre newest_mtime) must be treated as stale once."""
    proj = _make_project(tmp_path)
    cache = _save_cache(tmp_path, proj)
    con = sqlite3.connect(str(tmp_path / "cache.db"))
    con.execute("DELETE FROM cache_meta WHERE key = 'newest_mtime'")
    con.commit()
    con.close()

    assert not cache.is_valid(60, RULES_HASH,
                              current_files=_current_files(proj),
                              base_path=str(proj))


def test_valid_without_current_files_keeps_old_behavior(tmp_path):
    """No file list supplied -> only age + rules hash are checked."""
    proj = _make_project(tmp_path)
    cache = _save_cache(tmp_path, proj)
    _touch_future(proj / "a.py")

    assert cache.is_valid(60, RULES_HASH)


def test_load_for_files_roundtrip(tmp_path):
    proj = _make_project(tmp_path)
    cache = _save_cache(tmp_path, proj)

    loaded = cache.load_for_files(["a.py"])
    assert len(loaded) == 1
    assert loaded[0].file_path == "a.py"
    assert loaded[0].severity == Severity.WARNING
    assert cache.load_for_files(["b.py"]) == []


def test_analyzer_hash_is_deterministic_and_tracks_content(tmp_path):
    source_root = _make_analyzer_source(tmp_path)

    original = compute_analyzer_hash(source_root)
    assert compute_analyzer_hash(source_root) == original

    (source_root / "main.py").write_text("MAIN = 2\n")
    assert compute_analyzer_hash(source_root) != original


def test_analyzer_hash_tracks_file_set_and_relative_paths(tmp_path):
    source_root = _make_analyzer_source(tmp_path)
    original = compute_analyzer_hash(source_root)
    added = source_root / "rules" / "added.py"
    added.write_text("RULE = 2\n")
    added_hash = compute_analyzer_hash(source_root)
    assert added_hash != original

    renamed = source_root / "rules" / "renamed.py"
    added.rename(renamed)
    assert compute_analyzer_hash(source_root) != added_hash

    renamed.unlink()
    assert compute_analyzer_hash(source_root) == original


def test_analyzer_hash_ignores_nonproduction_python_files(tmp_path):
    source_root = _make_analyzer_source(tmp_path)
    original = compute_analyzer_hash(source_root)

    for path in (
        source_root / "conftest.py",
        source_root / "tests" / "ignored.py",
        source_root / "example" / "ignored.py",
        source_root / "venv" / "ignored.py",
        source_root / ".venv" / "ignored.py",
        source_root / "__pycache__" / "ignored.py",
    ):
        path.write_text("CHANGED = 1\n")

    assert compute_analyzer_hash(source_root) == original
