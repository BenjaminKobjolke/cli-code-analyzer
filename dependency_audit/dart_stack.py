"""Dart and Flutter package auditing via pub's advisory metadata."""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from dependency_audit.command import AuditToolError, parse_json, resolve_tool, run_tool
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
    packages = data.get("packages", [])
    if advisories:
        return [item for item in packages if item.get("isCurrentAffectedByAdvisory")]
    outdated: list[OutdatedPackage] = []
    for item in packages:
        if item.get("kind") not in ("direct", "dev"):
            continue
        current = item.get("current") or {}
        latest = item.get("latest") or {}
        if current.get("version") and latest.get("version") and current["version"] != latest["version"]:
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


def _resolve_dart_tool(name: str) -> str:
    executable = __import__("shutil").which(name)
    if executable:
        return executable
    configured = Settings().get_path(name)
    if configured:
        return configured
    raise AuditToolError(f"{name} not found")


def audit(checkout: Path, report: AuditReport, fetch: FetchAdvisories = fetch_pub_advisories) -> None:
    tool_name = "flutter" if is_flutter_project(checkout) else "dart"
    try:
        tool = _resolve_dart_tool(tool_name)
        output = run_tool([tool, "pub", "outdated", "--json"], checkout)
        data = parse_json(output, f"{tool_name} pub outdated")
    except (AuditToolError, KeyError, ValueError) as error:
        report.errors.append(StackError(ECOSYSTEM, str(error)))
        return
    report.outdated.extend(parse_pub_outdated(data))
    for package in parse_pub_outdated(data, advisories=True):
        try:
            current = package.get("current") or {}
            version = current.get("version")
            if version:
                report.advisories.extend(match_pub_advisories(package["package"], version, fetch(package["package"])))
        except (AuditToolError, KeyError, ValueError) as error:
            report.errors.append(StackError(ECOSYSTEM, str(error)))
