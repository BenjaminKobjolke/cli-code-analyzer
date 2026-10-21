"""PHP dependency auditing through Composer's lock-aware commands."""

from pathlib import Path

from dependency_audit.command import (
    AuditToolError,
    parse_json,
    resolve_tool,
    run_tool,
    run_tool_result,
)
from dependency_audit.models import (
    Advisory,
    AuditReport,
    Ecosystem,
    OutdatedPackage,
    StackError,
)

LOCK_FILE = "composer.lock"
ECOSYSTEM = Ecosystem.PHP


def _locked_versions(lock: dict[str, object]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for group in ("packages", "packages-dev"):
        for package in lock.get(group, []):
            versions[package["name"]] = package["version"]
    return versions


def parse_composer_audit(text: str, lock: dict[str, object]) -> list[Advisory]:
    data = parse_json(text, "composer audit")
    if not isinstance(data, dict) or "advisories" not in data:
        raise AuditToolError("composer audit returned JSON without advisories")
    versions = _locked_versions(lock)
    advisories = data.get("advisories", {})
    if not isinstance(advisories, dict):
        return []
    results: list[Advisory] = []
    for package, entries in advisories.items():
        for entry in entries:
            results.append(Advisory(
                ecosystem=ECOSYSTEM, package=package, installed=versions.get(package), fixed=None,
                id=entry.get("advisoryId", ""), summary=entry.get("title", ""),
                url=entry.get("link", ""),
            ))
    return results


def parse_composer_outdated(data: object) -> list[OutdatedPackage]:
    if data == []:
        return []
    if not isinstance(data, dict):
        raise AuditToolError("composer outdated returned unexpected JSON")
    entries = data.get("locked", data.get("installed", []))
    return [OutdatedPackage(
        ECOSYSTEM, item["name"], item["version"], item["latest"]
    ) for item in entries if item.get("latest-status") != "up-to-date"]


def audit(checkout: Path, report: AuditReport) -> None:
    try:
        lock = parse_json((checkout / LOCK_FILE).read_text(encoding="utf-8"), "composer.lock")
        composer = resolve_tool("composer")
        result = run_tool_result(
            [composer, "audit", "--locked", "--format=json", "--no-interaction",
             "--abandoned=ignore"],
            checkout,
            accepted=tuple(range(256)),
        )
        if result.returncode != 0 or result.stdout.strip():
            report.advisories.extend(parse_composer_audit(result.stdout, lock))
    except (AuditToolError, KeyError, ValueError) as error:
        report.errors.append(StackError(ECOSYSTEM, str(error)))
    try:
        composer = resolve_tool("composer")
        output = run_tool([composer, "outdated", "--direct", "--locked", "--format=json",
                           "--no-interaction"], checkout)
        data = parse_json(output, "composer outdated")
        report.outdated.extend(parse_composer_outdated(data))
    except (AuditToolError, KeyError, ValueError) as error:
        report.errors.append(StackError(ECOSYSTEM, str(error)))
