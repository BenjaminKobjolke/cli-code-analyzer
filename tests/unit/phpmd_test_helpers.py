"""Shared fixture helpers for PHPMD analyzer tests."""

from pathlib import Path

from logger import Logger
from rules.context import RuleContext
from rules.phpmd_analyze import PHPMDAnalyzeRule


def _rule(tmp_path: Path, filter_files=None, config=None) -> PHPMDAnalyzeRule:
    source = tmp_path / "src" / "Example.php"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("<?php\n", encoding="utf-8")
    return PHPMDAnalyzeRule(RuleContext(
        config=config or {},
        base_path=tmp_path,
        logger=Logger(quiet=True),
        filter_files=filter_files,
    ))
