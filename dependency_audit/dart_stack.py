"""Dart and Flutter package auditing via pub's advisory metadata."""

import json
import shutil
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from dependency_audit.command import AuditToolError, parse_json, run_tool
from dependency_audit.models import (
    Advisory,
    AuditReport,
    Ecosystem,
    OutdatedPackage,
    StackError,
)
from settings import Settings

LOCK_FILE = "pubspec.lock"
ECOSYSTEM = Ecosystem.DART
FetchAdvisories = Callable[[str], dict[str, object]]


def is_flutter_project(checkout: Path) -> bool:
    pubspec = checkout / "pubspec.yaml"
    return pubspec.exists() and "sdk: flutter" in pubspec.read_text(encoding="utf-8")


def parse_pub_outdated(data: dict[str, object], advisories: bool = False) -> list[OutdatedPackage] | list[dict[str, str]]:
    if not isinstance(data, dict):
        raise AuditToolError("dart pub outdated returned unexpected JSON: expected an object")
    packages = data.get("packages", [])
    if advisories:
        return [item for item in packages if item.get("isCurrentAffectedByAdvisory")]
    outdated: list[OutdatedPackage] = []
    for item in packages:
        if item.get("kind") not in ("direct", "dev"):
            continue
        current = item.get("current") or {}
        latest = item.get("latest") or {}
        current_version = current.get("version")
        latest_version = latest.get("version")
        has_different_versions = bool(current_version and latest_version) and current_version != latest_version
        if has_different_versions:
            outdated.append(OutdatedPackage(ECOSYSTEM, item["package"], current["version"], latest["version"]))
    return outdated


def fetch_pub_advisories(package: str) -> dict[str, object]:
    url = f"https://pub.dev/api/packages/{package}/advisories"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise AuditToolError(f"pub.dev advisory lookup failed for {package}: {error}") from error


def match_pub_advisories(
    package: str, current: str, data: dict[str, object]
) -> list[Advisory]:
    def entries(value: object, field: str) -> list[dict[str, object]]:
        if not isinstance(value, list) or any(not isinstance(entry, dict) for entry in value):
            raise AuditToolError(f"pub.dev advisory response has invalid {field}")
        return value

    if not isinstance(data, dict):
        raise AuditToolError("pub.dev advisory response must be an object")
    results: list[Advisory] = []
    advisories = entries(data.get("advisories", []), "advisories")
    for item in advisories:
        affected = entries(item.get("affected", []), "affected")
        for entry in affected:
            versions = entry.get("versions", [])
            if not isinstance(versions, list) or any(not isinstance(version, str) for version in versions):
                raise AuditToolError("pub.dev advisory response has invalid affected versions")
            ranges = entries(entry.get("ranges", []), "ranges")
            for group in ranges:
                entries(group.get("events", []), "range events")
        if not any(current in entry.get("versions", []) for entry in affected):
            continue
        fixed = next((event["fixed"] for entry in affected for group in entry.get("ranges", [])
                      for event in group.get("events", []) if isinstance(event.get("fixed"), str)), None)
        advisory_id = item.get("id", "")
        details = item.get("database_specific", {})
        if not isinstance(details, dict):
            raise AuditToolError("pub.dev advisory response has invalid database_specific")
        url = details.get("pub_display_url")
        results.append(Advisory(
            ECOSYSTEM, package, current, fixed, advisory_id, item.get("summary", ""),
            url or f"https://osv.dev/vulnerability/{advisory_id}",
        ))
    return results


def _dart_command(checkout: Path, name: str) -> list[str]:
    fvm = shutil.which("fvm")
    if fvm and ((checkout / ".fvmrc").exists() or (checkout / ".fvm").is_dir()):
        # Keep the resolved path: on Windows fvm may be a .bat file or shim.
        return [fvm, name]

    executable = shutil.which(name)
    if executable:
        return [executable]
    configured = Settings().get_path(name)
    if configured:
        return [configured]
    raise AuditToolError(f"{name} not found")


def audit(checkout: Path, report: AuditReport, fetch: FetchAdvisories = fetch_pub_advisories) -> None:
    tool_name = "flutter" if is_flutter_project(checkout) else "dart"
    try:
        output = run_tool([*_dart_command(checkout, tool_name), "pub", "outdated", "--json"], checkout)
        data = parse_json(output, f"{tool_name} pub outdated")
        outdated = parse_pub_outdated(data)
        advisory_packages = parse_pub_outdated(data, advisories=True)
    except (AuditToolError, KeyError, ValueError) as error:
        report.errors.append(StackError(ECOSYSTEM, str(error)))
        return
    report.outdated.extend(outdated)
    for package in advisory_packages:
        try:
            current = package.get("current") or {}
            version = current.get("version")
            if version:
                report.advisories.extend(match_pub_advisories(package["package"], version, fetch(package["package"])))
        except (AuditToolError, KeyError, ValueError) as error:
            report.errors.append(StackError(ECOSYSTEM, str(error)))
