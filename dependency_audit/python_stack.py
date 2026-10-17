"""Python dependency auditing using uv and pip-audit."""

import re
import tempfile
from pathlib import Path

from dependency_audit.command import AuditToolError, parse_json, resolve_tool, run_tool
from dependency_audit.models import (
    Advisory,
    AuditReport,
    Ecosystem,
    OutdatedPackage,
    StackError,
)

LOCK_FILE = "uv.lock"
ECOSYSTEM = Ecosystem.PYTHON


def parse_pip_audit(text: str) -> list[Advisory]:
    data = parse_json(text, "pip-audit")
    results: list[Advisory] = []
    for dependency in data.get("dependencies", []):
        for vulnerability in dependency.get("vulns", []):
            summary = " ".join(vulnerability.get("description", "").split())[:200]
            advisory_id = vulnerability["id"]
            fixes = vulnerability.get("fix_versions", [])
            results.append(Advisory(
                ecosystem=ECOSYSTEM,
                package=dependency["name"],
                installed=dependency.get("version"),
                fixed=fixes[0] if fixes else None,
                id=advisory_id,
                summary=summary,
                url=f"https://osv.dev/vulnerability/{advisory_id}",
            ))
    return results


def parse_uv_tree(text: str) -> list[OutdatedPackage]:
    results: list[OutdatedPackage] = []
    for line in text.splitlines()[1:]:
        match = re.search(r"([\w.-]+) v([^\s()]+).*?\(latest: v([^\s)]+)\)", line)
        if match:
            results.append(OutdatedPackage(ECOSYSTEM, match[1], match[2], match[3]))
    return results


def audit(checkout: Path, report: AuditReport) -> None:
    """Run advisory and outdated checks independently."""
    try:
        uv = resolve_tool("uv")
        uvx = resolve_tool("uvx")
        with tempfile.TemporaryDirectory(prefix="cli-code-audit-") as directory:
            requirements = Path(directory) / "requirements.txt"
            run_tool([uv, "export", "--frozen", "--no-hashes", "--no-emit-project",
                      "--format", "requirements-txt", "-o", str(requirements)], checkout)
            output = run_tool([uvx, "pip-audit", "-r", str(requirements), "--no-deps",
                               "--disable-pip", "--format", "json", "--progress-spinner", "off"],
                              checkout, accepted=(0, 1))
            report.advisories.extend(parse_pip_audit(output))
    except (AuditToolError, KeyError, ValueError) as error:
        report.errors.append(StackError(ECOSYSTEM, str(error)))
    try:
        uv = resolve_tool("uv")
        output = run_tool([uv, "tree", "--outdated", "--depth", "1", "--frozen"], checkout)
        report.outdated.extend(parse_uv_tree(output))
    except (AuditToolError, KeyError, ValueError) as error:
        report.errors.append(StackError(ECOSYSTEM, str(error)))
