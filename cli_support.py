"""Runtime helpers shared by the CLI entry point."""

from pathlib import Path


def clean_report_files(output_folder: Path) -> None:
    """Remove all CSV and TXT report files from the output folder."""
    for report_file in output_folder.iterdir():
        if report_file.is_file() and report_file.suffix in ('.csv', '.txt'):
            report_file.unlink()


def resolve_reporter_log_level(cli_log_level, rules_file: str):
    """Resolve the reporter log level from CLI args and rules config."""
    from config import Config
    from models import LogLevel

    if cli_log_level:
        return cli_log_level
    config = Config(rules_file)
    global_log_level = config.get_global_log_level()
    if global_log_level:
        try:
            return LogLevel(global_log_level)
        except ValueError:
            pass
    return LogLevel.ALL
