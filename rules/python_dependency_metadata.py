"""Read Python dependency declarations and map distributions to import packages."""

import configparser
import csv
import re
from pathlib import Path

import tomllib

from rules.unused_dependencies import DependencyDeclarations

ALIASES = {
    "pyyaml": {"yaml"}, "pillow": {"PIL"}, "beautifulsoup4": {"bs4"},
    "python-dateutil": {"dateutil"}, "scikit-learn": {"sklearn"},
    "opencv-python": {"cv2"}, "python-dotenv": {"dotenv"}, "attrs": {"attr"},
}
_REQUIREMENT_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
_FALLBACK_PACKAGES = frozenset(ALIASES)
_DEV_REQUIREMENT_NAMES = (
    "requirements-dev.txt", "dev-requirements.txt", "requirements_test.txt", "requirements-test.txt",
)


def read_declarations(root: Path) -> tuple[Path | None, DependencyDeclarations | str]:
    """Read pyproject metadata, or root runtime/development requirements files."""
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            with pyproject.open("rb") as stream:
                data = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as error:
            return pyproject, f"error parsing pyproject.toml: {error}"
        project = data.get("project", {})
        if not isinstance(project, dict):
            return pyproject, "error parsing pyproject.toml: [project] must be a table"
        runtime = _names(project.get("dependencies", []))
        dev: set[str] = set()
        groups = data.get("dependency-groups", {})
        if isinstance(groups, dict):
            for entries in groups.values():
                dev.update(_names(entries))
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for entries in optional.values():
                dev.update(_names(entries))
        poetry = data.get("tool", {}).get("poetry", {}) if isinstance(data.get("tool"), dict) else {}
        poetry_groups = poetry.get("group", {}) if isinstance(poetry, dict) else {}
        if isinstance(poetry_groups, dict):
            for group in poetry_groups.values():
                if isinstance(group, dict):
                    dev.update(_names(group.get("dependencies", {})))
        return pyproject, DependencyDeclarations(frozenset(runtime), frozenset(dev))

    runtime_file = root / "requirements.txt"
    dev_file = next((root / name for name in _DEV_REQUIREMENT_NAMES if (root / name).is_file()), None)
    manifest = runtime_file if runtime_file.is_file() else dev_file
    if manifest is None:
        return None, DependencyDeclarations(frozenset(), frozenset())
    runtime = _requirements_file(runtime_file) if runtime_file.is_file() else set()
    dev = _requirements_file(dev_file) if dev_file else set()
    return manifest, DependencyDeclarations(frozenset(runtime), frozenset(dev))


def normalize_requirement(requirement: str) -> str | None:
    """Normalize a distribution name according to PEP 503."""
    match = _REQUIREMENT_NAME.match(requirement.strip())
    if not match or "@" in requirement:
        return None
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def package_imports(root: Path) -> tuple[dict[str, set[str]], set[str]]:
    """Map installed distribution names to top-level import names and console tools."""
    import_map: dict[str, set[str]] = {}
    tool_packages: set[str] = set()
    for env_name in (".venv", "venv"):
        env = root / env_name
        if not env.is_dir():
            continue
        for dist_info in env.rglob("*.dist-info"):
            package = _distribution_name(dist_info)
            if not package:
                continue
            names = _dist_import_names(dist_info)
            if names:
                import_map[package] = names
            if _has_console_scripts(dist_info):
                tool_packages.add(package)
    for package in _FALLBACK_PACKAGES:
        import_map.setdefault(package, {package.replace("-", "_")} | ALIASES.get(package, set()))
    return import_map, tool_packages


def configured_imports(value: object) -> dict[str, set[str]]:
    """Read configured distribution-to-module overrides."""
    if not isinstance(value, dict):
        return {}
    configured: dict[str, set[str]] = {}
    for package_name, names in value.items():
        normalized = normalize_requirement(package_name) if isinstance(package_name, str) else None
        values = [names] if isinstance(names, str) else names
        if normalized and isinstance(values, (list, tuple, set)):
            configured[normalized] = {
                name.split(".", 1)[0] for name in values if isinstance(name, str) and name
            }
    return configured


def dev_manifest(manifest: Path, root: Path) -> Path:
    """Return the separate development requirements file when one is present."""
    if manifest.name == "requirements.txt":
        return next((root / name for name in _DEV_REQUIREMENT_NAMES if (root / name).is_file()), manifest)
    return manifest


def _names(value: object) -> set[str]:
    if isinstance(value, dict):
        values = value.keys()
    elif isinstance(value, list):
        values = value
    else:
        return set()
    return {normalized for item in values if isinstance(item, str)
            if (normalized := normalize_requirement(item))}


def _requirements_file(path: Path) -> set[str]:
    names: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return names
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(("#", "-", "http://", "https://", "git+", "file:")):
            continue
        line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
        name = normalize_requirement(line)
        if name:
            names.add(name)
    return names


def _distribution_name(dist_info: Path) -> str | None:
    metadata = dist_info / "METADATA"
    if metadata.is_file():
        try:
            for line in metadata.read_text(encoding="utf-8").splitlines():
                if line.lower().startswith("name:"):
                    return normalize_requirement(line.split(":", 1)[1].strip())
        except (OSError, UnicodeError):
            pass
    stem = dist_info.name.removesuffix(".dist-info")
    match = re.match(r"^(.+?)-(?=\d)", stem)
    return normalize_requirement(match.group(1)) if match else None


def _dist_import_names(dist_info: Path) -> set[str]:
    top_level = dist_info / "top_level.txt"
    if top_level.is_file():
        try:
            names = {line.strip() for line in top_level.read_text(encoding="utf-8").splitlines()
                     if line.strip().isidentifier()}
            if names:
                return names
        except (OSError, UnicodeError):
            pass
    record = dist_info / "RECORD"
    if not record.is_file():
        return set()
    names: set[str] = set()
    try:
        with record.open(encoding="utf-8", newline="") as stream:
            for row in csv.reader(stream):
                if not row:
                    continue
                first = row[0].replace("\\", "/").split("/", 1)[0]
                module = first[:-3] if first.endswith(".py") else first
                if module.isidentifier() and not module.endswith((".dist-info", ".data")):
                    names.add(module)
    except (OSError, UnicodeError, csv.Error):
        return set()
    return names


def _has_console_scripts(dist_info: Path) -> bool:
    entries = dist_info / "entry_points.txt"
    if not entries.is_file():
        return False
    parser = configparser.ConfigParser()
    try:
        parser.read(entries, encoding="utf-8")
    except (OSError, configparser.Error):
        return False
    return parser.has_section("console_scripts") and bool(parser.items("console_scripts"))
