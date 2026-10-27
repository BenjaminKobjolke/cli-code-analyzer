"""Small configuration helpers shared by the code analyzer."""

from config import Config
from logger import Logger
from models import LogLevel


def resolve_log_level(
    cli_log_level: LogLevel | None, config: Config, logger: Logger, rule_name: str
) -> LogLevel:
    """Resolve log level for a rule: CLI, per-rule, global, then default."""
    if cli_log_level is not None:
        return cli_log_level

    rule_log_level = config.get_rule_log_level(rule_name)
    if rule_log_level:
        try:
            return LogLevel(rule_log_level)
        except ValueError:
            logger.warning(f"Warning: Invalid log_level '{rule_log_level}' for rule '{rule_name}', using default")

    global_log_level = config.get_global_log_level()
    if global_log_level:
        try:
            return LogLevel(global_log_level)
        except ValueError:
            logger.warning(f"Warning: Invalid global log_level '{global_log_level}', using default")

    return LogLevel.ALL
