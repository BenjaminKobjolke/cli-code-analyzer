"""Verify PHPMD uses the cache directory supplied by the analyzer."""

import shutil
from pathlib import Path

import pytest

from logger import Logger
from models import RuleStatus
from rules.context import RuleContext
from rules.php_tool_paths import get_bundled_php_tool_path
from rules.phpmd_analyze import PHPMDAnalyzeRule


@pytest.mark.skipif(
    not get_bundled_php_tool_path("phpmd") or not shutil.which("php"),
    reason="bundled PHPMD and PHP runtime are required",
)
def test_phpmd_run_uses_isolated_pdepend_cache(tmp_path: Path, monkeypatch):
    global_cache = tmp_path / "global-cache"
    global_cache.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(global_cache))
    project = tmp_path / "project"
    project.mkdir()
    (project / "Example.php").write_text(
        "<?php\nclass Example { public function run(): void {} }\n",
        encoding="utf-8",
    )
    rule = PHPMDAnalyzeRule(RuleContext(
        config={},
        base_path=project,
        filter_files={"Example.php"},
        logger=Logger(quiet=True),
    ))

    result = rule.check(project / "Example.php")

    assert result.status == RuleStatus.OK
    assert not (global_cache / "pdepend").exists()
