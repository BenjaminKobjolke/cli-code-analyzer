"""Unit tests for ViolationCache validity (age, rules hash, file set, mtimes)."""

import os
import sqlite3

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
