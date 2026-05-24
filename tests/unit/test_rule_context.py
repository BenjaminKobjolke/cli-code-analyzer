import pytest

from models import LogLevel
from rules.context import RuleContext


def test_defaults_minimal_config():
    ctx = RuleContext(config={"warning": 10})
    assert ctx.config == {"warning": 10}
    assert ctx.base_path is None
    assert ctx.output_folder is None
    assert ctx.log_level is LogLevel.ALL
    assert ctx.max_errors is None
    assert ctx.rules_file_path is None
    assert ctx.logger is None
    assert ctx.language is None


def test_frozen_disallows_mutation():
    ctx = RuleContext(config={})
    with pytest.raises(Exception):
        ctx.config = {"other": 1}
