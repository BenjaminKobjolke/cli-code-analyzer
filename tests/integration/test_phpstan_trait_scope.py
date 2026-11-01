"""Exercise PHPStan's trait analysis in the same scoped mode as the analyzer."""

import shutil
from pathlib import Path

import pytest

from logger import Logger
from models import RuleStatus
from rules.context import RuleContext
from rules.php_tool_paths import get_bundled_php_tool_path
from rules.phpstan_analyze import PHPStanAnalyzeRule


@pytest.mark.skipif(
    not get_bundled_php_tool_path("phpstan") or not shutil.which("php"),
    reason="bundled PHPStan and PHP runtime are required",
)
def test_scoped_phpstan_analyses_promoted_property_reads_in_nested_traits(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    dispatcher = source / "Dispatcher.php"
    dispatcher.write_text(
        """<?php
class Dispatcher {
    use ContentCreationTrait;

    public function __construct(private string $value) {}
}
""",
        encoding="utf-8",
    )
    content_trait = source / "ContentCreationTrait.php"
    content_trait.write_text(
        """<?php
trait ContentCreationTrait {
    use RequestStatusUpdaterFactoryTrait;
}
""",
        encoding="utf-8",
    )
    nested_trait = source / "RequestStatusUpdaterFactoryTrait.php"
    nested_trait.write_text(
        """<?php
trait RequestStatusUpdaterFactoryTrait {
    public function readValue(): string {
        return $this->value;
    }
}
""",
        encoding="utf-8",
    )
    rule = PHPStanAnalyzeRule(RuleContext(
        config={"level": 5},
        base_path=tmp_path,
        filter_files={"src/Dispatcher.php"},
        logger=Logger(quiet=True),
    ))
    phpstan_path = get_bundled_php_tool_path("phpstan")
    assert phpstan_path is not None

    result = rule._run_phpstan_check(phpstan_path)

    assert result.status == RuleStatus.OK
    assert not any("property.onlyWritten" in violation.message for violation in result.violations)
