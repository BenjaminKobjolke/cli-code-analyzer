"""`global_exclude_paths` and `max_lines_per_file.exclude_paths` reach discovery.

Regression guard: both keys used to be silently ignored (only
`max_lines_per_file.exclude_patterns` was read), so a project listing
`.dart_tool` there still had its generated plugin registrant analyzed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from path_utils import dir_paths_to_patterns


def test_bare_dirs_become_globs():
    assert dir_paths_to_patterns([".dart_tool", "vendor/", "a\\b"]) == [
        ".dart_tool/**", "vendor/**", "a/b/**",
    ]


def test_empty_and_none():
    assert dir_paths_to_patterns(None) == []
    assert dir_paths_to_patterns([]) == []


def test_global_exclude_paths_reach_discovery(tmp_path):
    from analyzer import CodeAnalyzer  # noqa: F401  (import guard only)
    from config import Config

    rules = tmp_path / "rules.json"
    rules.write_text(
        '{"global_exclude_paths": [".dart_tool"], '
        '"max_lines_per_file": {"enabled": true, "exclude_paths": ["build"]}}',
        encoding="utf-8",
    )
    config = Config(str(rules))
    assert config.get_global_exclude_paths() == [".dart_tool"]
    assert dir_paths_to_patterns(config.get_rule("max_lines_per_file")["exclude_paths"]) == ["build/**"]
