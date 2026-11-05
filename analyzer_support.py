"""Small configuration helpers shared by the code analyzer."""

from config import Config
from logger import Logger
from models import LogLevel
from path_utils import dir_paths_to_patterns, resolve_exclude_patterns


def discovery_exclude_patterns(config: Config, languages: list[str]) -> list[str]:
    """Build global and max-lines exclusions shared by discovery consumers."""
    patterns = dir_paths_to_patterns(config.get_global_exclude_paths())
    if config.is_rule_enabled('max_lines_per_file'):
        rule_config = config.get_rule('max_lines_per_file')
        patterns += dir_paths_to_patterns(rule_config.get('exclude_paths'))
        patterns += resolve_exclude_patterns(rule_config.get('exclude_patterns'), languages)
    return patterns


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
