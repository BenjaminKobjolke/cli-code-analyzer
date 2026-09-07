"""Exclude-pattern matching in FileDiscovery.

Regression guard for the nested-dir bug: a dependency dir nested below the repo
root (e.g. a WordPress theme's wp-content/themes/x/vendor/) must be excluded by
the canonical vendor/** and **/vendor/** forms, which previously matched only a
root-level vendor/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from file_discovery import FileDiscovery

BASE = Path("/repo")
NESTED_VENDOR = BASE / "wp-content/themes/x/vendor/a/b.php"
NESTED_BUILD = BASE / "wp-content/themes/x/build/y.php"
NESTED_SRC = BASE / "wp-content/themes/x/src/render.php"
ROOT_VENDOR = BASE / "vendor/a.php"


def _excluded(patterns, file_path):
    return FileDiscovery("php", str(BASE), patterns)._is_excluded(file_path)


def test_nested_vendor_excluded_by_root_anchored_form():
    assert _excluded(["vendor/**"], NESTED_VENDOR) is True


def test_nested_vendor_excluded_by_globstar_form():
    assert _excluded(["**/vendor/**"], NESTED_VENDOR) is True


def test_nested_build_excluded():
    assert _excluded(["**/build/**"], NESTED_BUILD) is True


def test_src_not_excluded():
    patterns = ["**/vendor/**", "**/build/**", "**/node_modules/**"]
    assert _excluded(patterns, NESTED_SRC) is False


def test_root_vendor_still_excluded():
    assert _excluded(["vendor/**"], ROOT_VENDOR) is True


def test_language_defaults_survive_explicit_patterns():
    # Configured patterns add to the language defaults; they must not replace
    # them, or a project listing its cache dir silently re-enables *.g.dart.
    discovery = FileDiscovery("flutter", str(BASE), [".dart_tool/**"])
    assert discovery._is_excluded(BASE / "lib/objectbox.g.dart") is True
    assert discovery._is_excluded(BASE / ".dart_tool/flutter_build/x.dart") is True
    assert discovery._is_excluded(BASE / "lib/main.dart") is False


def test_flutter_tool_caches_excluded_by_default():
    discovery = FileDiscovery("flutter", str(BASE))
    assert discovery._is_excluded(BASE / ".dart_tool/flutter_build/x.dart") is True
    assert discovery._is_excluded(BASE / "build/app/x.dart") is True
    assert discovery._is_excluded(BASE / ".fvm/flutter_sdk/x.dart") is True


def test_segment_safe_no_false_prefix_match():
    # 'vendor' must not match a sibling dir that merely starts with it.
    vendored = BASE / "vendored-thing/a.php"
    assert _excluded(["vendor/**"], vendored) is False


if __name__ == "__main__":
    # Runnable self-check without pytest.
    test_nested_vendor_excluded_by_root_anchored_form()
    test_nested_vendor_excluded_by_globstar_form()
    test_nested_build_excluded()
    test_src_not_excluded()
    test_root_vendor_still_excluded()
    test_segment_safe_no_false_prefix_match()
    test_language_defaults_survive_explicit_patterns()
    test_flutter_tool_caches_excluded_by_default()
    print("OK")
