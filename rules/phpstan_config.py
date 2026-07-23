"""PHPStan temporary config generation."""

from pathlib import Path


def resolve_config_file(base_path: Path, config: dict) -> Path | None:
    configured = config.get('config_file')
    if not configured:
        return None

    config_file = Path(configured)
    if not config_file.is_absolute():
        config_file = base_path / config_file
    return config_file


def resolve_bootstrap_files(base_path: Path, config: dict) -> list[str]:
    bootstrap_files = []
    for configured in config.get('bootstrap_files') or []:
        bootstrap_file = Path(configured)
        if not bootstrap_file.is_absolute():
            bootstrap_file = base_path / bootstrap_file
        bootstrap_files.append(bootstrap_file.as_posix())
    return bootstrap_files


def resolve_exclude_dirs(base_path: Path, config: dict) -> list[str]:
    exclude_dirs = []
    for pattern in config.get('exclude_patterns') or []:
        if '**' in pattern:
            pattern = pattern.replace('/**', '').replace('**/', '')
        exclude_dirs.append((base_path / pattern).as_posix())
    return exclude_dirs


def build_phpstan_config(config_file: Path | None, bootstrap_files: list[str], exclude_dirs: list[str]) -> str:
    neon = ''
    if config_file:
        neon += 'includes:\n'
        neon += f'    - {config_file.as_posix()}\n'

    if bootstrap_files or exclude_dirs:
        neon += 'parameters:\n'

    if bootstrap_files:
        neon += '    bootstrapFiles:\n'
        neon += ''.join(f'        - {path}\n' for path in bootstrap_files)

    if exclude_dirs:
        # "(?)" marks each path optional so a configured-but-absent dir does
        # not abort the run.
        neon += '    excludePaths:\n'
        neon += ''.join(f'        - {d} (?)\n' for d in exclude_dirs)

    return neon
