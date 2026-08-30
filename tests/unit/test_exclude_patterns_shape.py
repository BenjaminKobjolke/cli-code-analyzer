"""Per-language `exclude_patterns` dicts must resolve to that language's list.

Regression guard: rules.json allows `exclude_patterns` as either a flat list or
a dict keyed by language. Only pmd_base handled the dict form; FileDiscovery and
ruff_analyze iterated the dict directly, which yields its KEYS ("python"), so
every real pattern was silently dropped and e.g. target/** was analyzed anyway.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from file_discovery import FileDiscovery
from path_utils import resolve_exclude_patterns

BASE = Path("/repo")
TARGET_FILE = BASE / "target/fman/Plugins/Core/core/commands/__init__.py"
SRC_FILE = BASE / "src/main/python/fman/__init__.py"

PER_LANGUAGE = {"python": ["target/**", "__pycache__/**"]}
FLAT = ["target/**", "__pycache__/**"]


def test_dict_form_resolves_to_language_list():
    assert resolve_exclude_patterns(PER_LANGUAGE, ["python"]) == FLAT


def test_list_form_passes_through():
    assert resolve_exclude_patterns(FLAT, ["python"]) == FLAT


def test_dict_form_unknown_language_yields_nothing():
    assert resolve_exclude_patterns(PER_LANGUAGE, ["php"]) == []


def test_dict_form_merges_multiple_languages_without_duplicates():
    config = {"python": ["target/**", "shared/**"], "php": ["vendor/**", "shared/**"]}
    assert resolve_exclude_patterns(config, ["python", "php"]) == [
        "target/**", "shared/**", "vendor/**",
    ]


def test_none_yields_nothing():
    assert resolve_exclude_patterns(None, ["python"]) == []


def test_file_discovery_honours_dict_form():
    discovery = FileDiscovery("python", str(BASE), PER_LANGUAGE)
    assert discovery._is_excluded(TARGET_FILE) is True
    assert discovery._is_excluded(SRC_FILE) is False


def test_file_discovery_still_honours_list_form():
    discovery = FileDiscovery("python", str(BASE), FLAT)
    assert discovery._is_excluded(TARGET_FILE) is True
    assert discovery._is_excluded(SRC_FILE) is False


def test_language_key_is_not_treated_as_a_pattern():
    """The old bug: iterating the dict matched the literal key, not the globs."""
    discovery = FileDiscovery("python", str(BASE), PER_LANGUAGE)
    assert "python" not in discovery.exclude_patterns
