"""Focused parsing and orchestration coverage for dependency audits."""

import json
import subprocess
from io import StringIO
from pathlib import Path

import pytest

from dependency_audit import run_dependency_audit
from dependency_audit.command import AuditToolError, parse_json
from dependency_audit.dart_stack import (
    audit as audit_dart,
)
from dependency_audit.dart_stack import (
    is_flutter_project,
    match_pub_advisories,
    parse_pub_outdated,
)
from dependency_audit.models import AuditReport, Ecosystem, StackError
from dependency_audit.php_stack import audit as audit_php
from dependency_audit.php_stack import parse_composer_audit, parse_composer_outdated
from dependency_audit.python_stack import parse_pip_audit, parse_uv_tree


def test_parse_pip_audit_maps_vulnerabilities_and_omits_clean_packages():
    results = parse_pip_audit(json.dumps({"dependencies": [
        {"name": "jinja2", "version": "3.1.3", "vulns": [{
            "id": "GHSA-abcd", "fix_versions": ["3.1.4", "3.2.0"],
            "description": "  unsafe   template rendering\nissue  ",
        }]},
        {"name": "clean", "version": "1.0", "vulns": []},
        {"name": "no-fix", "version": "1.0", "vulns": [{
            "id": "CVE-1", "fix_versions": [], "description": "issue",
        }]},
    ]}))

    assert [(item.package, item.fixed, item.summary) for item in results] == [
        ("jinja2", "3.1.4", "unsafe template rendering issue"),
        ("no-fix", None, "issue"),
    ]
    assert results[0].url == "https://osv.dev/vulnerability/GHSA-abcd"


def test_parse_uv_tree_skips_root_and_non_outdated_lines():
    results = parse_uv_tree(
        "project v1.0.0\n"
        "├── pydantic v2.12.5 (latest: v2.14.1)\n"
        "└── ruff v0.15.8 (group: dev) (latest: v0.17.0)\n"
        "    └── clean v1.0.0\n"
    )

    assert [(item.package, item.installed, item.latest) for item in results] == [
        ("pydantic", "2.12.5", "2.14.1"),
        ("ruff", "0.15.8", "0.17.0"),
    ]


def test_parse_composer_audit_uses_lock_versions():
    lock = {"packages": [{"name": "vendor/pkg", "version": "1.2.0"}], "packages-dev": []}
    data = {"advisories": {"vendor/pkg": [{
        "advisoryId": "GHSA-1", "packageName": "vendor/pkg", "title": "Bad package",
        "link": "https://example.test/advisory",
    }]}}

    results = parse_composer_audit(json.dumps(data), lock)

    assert len(results) == 1
    assert (results[0].package, results[0].installed, results[0].fixed) == ("vendor/pkg", "1.2.0", None)
    assert (results[0].id, results[0].summary, results[0].url) == (
        "GHSA-1", "Bad package", "https://example.test/advisory"
    )
    assert parse_composer_audit('{"advisories": []}', lock) == []
    with pytest.raises(AuditToolError, match="without advisories"):
        parse_composer_audit('{"unexpected": []}', lock)


def test_parse_composer_outdated_locked_and_installed_forms():
    locked = {"locked": [
        {"name": "vendor/a", "version": "1.0", "latest": "2.0", "latest-status": "semver-safe-update"},
        {"name": "vendor/b", "version": "2.0", "latest": "2.0", "latest-status": "up-to-date"},
    ]}
    fallback = {"installed": [
        {"name": "vendor/c", "version": "3.0", "latest": "4.0", "latest-status": "update-possible"}
    ]}

    assert [(x.package, x.installed, x.latest) for x in parse_composer_outdated(locked)] == [
        ("vendor/a", "1.0", "2.0")
    ]
    assert [x.package for x in parse_composer_outdated(fallback)] == ["vendor/c"]


def test_parse_composer_outdated_accepts_empty_array_and_rejects_unexpected_array():
    assert parse_composer_outdated([]) == []
    with pytest.raises(AuditToolError, match="composer outdated returned unexpected JSON"):
        parse_composer_outdated([{"x": 1}])


def test_parse_json_accepts_complete_arrays_and_keeps_banner_support():
    assert parse_json("[]", "composer outdated") == []
    assert parse_json('Composer banner\n{"packages": []}', "dart pub outdated") == {"packages": []}
    for text in ("", "garbage"):
        with pytest.raises(AuditToolError, match="did not return JSON"):
            parse_json(text, "composer outdated")


def test_composer_audit_accepts_empty_stdout_for_empty_lock(tmp_path, monkeypatch):
    (tmp_path / "composer.lock").write_text(
        '{"packages": [], "packages-dev": []}', encoding="utf-8"
    )
    commands = []
    monkeypatch.setattr("dependency_audit.php_stack.resolve_tool", lambda _name: "composer")

    def run_tool_result(command, *_args, **_kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "No packages - skipping audit.")

    monkeypatch.setattr("dependency_audit.php_stack.run_tool_result", run_tool_result)
    monkeypatch.setattr("dependency_audit.php_stack.run_tool", lambda *_args, **_kwargs: "[]")

    report = AuditReport()
    audit_php(tmp_path, report)

    assert len(commands) == 1
    assert report.errors == []
    assert report.advisories == []
    assert report.outdated == []


@pytest.mark.parametrize(
    "returncode,stdout,error_message",
    [(1, "", "composer audit did not return JSON"), (0, "garbage", "composer audit did not return JSON")],
)
def test_composer_audit_still_reports_failure_or_garbage(
    tmp_path, monkeypatch, returncode, stdout, error_message
):
    (tmp_path / "composer.lock").write_text(
        '{"packages": [], "packages-dev": []}', encoding="utf-8"
    )
    monkeypatch.setattr("dependency_audit.php_stack.resolve_tool", lambda _name: "composer")
    monkeypatch.setattr(
        "dependency_audit.php_stack.run_tool_result",
        lambda command, *_args, **_kwargs: subprocess.CompletedProcess(command, returncode, stdout, ""),
    )
    monkeypatch.setattr("dependency_audit.php_stack.run_tool", lambda *_args, **_kwargs: "[]")

    report = AuditReport()
    audit_php(tmp_path, report)

    assert [error.message for error in report.errors] == [error_message]


def test_composer_outdated_tool_failure_is_reported(tmp_path, monkeypatch):
    (tmp_path / "composer.lock").write_text(
        '{"packages": [], "packages-dev": []}', encoding="utf-8"
    )
    monkeypatch.setattr("dependency_audit.php_stack.resolve_tool", lambda _name: "composer")
    monkeypatch.setattr(
        "dependency_audit.php_stack.run_tool_result",
        lambda command, *_args, **_kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )

    def fail_outdated(*_args, **_kwargs):
        raise AuditToolError("composer exited with code 1")

    monkeypatch.setattr("dependency_audit.php_stack.run_tool", fail_outdated)
    report = AuditReport()
    audit_php(tmp_path, report)

    assert [error.message for error in report.errors] == ["composer exited with code 1"]


def test_pub_outdated_and_advisory_matching():
    packages = parse_pub_outdated({"packages": [
        {"package": "app", "kind": "direct", "current": {"version": "1.0"}, "latest": {"version": "2.0"}, "isCurrentAffectedByAdvisory": True},
        {"package": "dev", "kind": "dev", "current": {"version": "1.0"}, "latest": {"version": "1.1"}, "isCurrentAffectedByAdvisory": False},
        {"package": "transitive", "kind": "transitive", "current": {"version": "1.0"}, "latest": {"version": "2.0"}, "isCurrentAffectedByAdvisory": False},
        {"package": "same", "kind": "direct", "current": {"version": "1.0"}, "latest": {"version": "1.0"}, "isCurrentAffectedByAdvisory": False},
    ]})
    assert [x.package for x in packages] == ["app", "dev"]
    advisory_packages = parse_pub_outdated({"packages": [
        {"package": "app", "isCurrentAffectedByAdvisory": True},
        {"package": "clean", "isCurrentAffectedByAdvisory": False},
    ]}, advisories=True)
    assert [x["package"] for x in advisory_packages] == ["app"]

    advisories = {"advisories": [{
        "id": "OSV-1", "summary": "Issue", "affected": [{
            "versions": ["1.0"], "ranges": [{"events": [{"introduced": "0"}, {"fixed": "1.2"}]}]
        }],
        "database_specific": {"pub_display_url": "https://pub.dev/advisories/1"},
    }, {
        "id": "OSV-2", "summary": "Not affected", "affected": [{"versions": ["9.0"]}],
    }]}
    matched = match_pub_advisories("app", "1.0", advisories)

    assert len(matched) == 1
    assert (matched[0].id, matched[0].fixed, matched[0].url) == (
        "OSV-1", "1.2", "https://pub.dev/advisories/1"
    )


@pytest.mark.parametrize("data", [[], "unexpected", None])
def test_dart_audit_reports_unexpected_outdated_json(tmp_path, monkeypatch, data):
    monkeypatch.setattr(
        "dependency_audit.dart_stack._dart_command", lambda _checkout, _name: ["dart"]
    )
    monkeypatch.setattr(
        "dependency_audit.dart_stack.run_tool",
        lambda *_args, **_kwargs: json.dumps(data),
    )

    report = AuditReport()
    audit_dart(tmp_path, report)

    assert len(report.errors) == 1
    assert report.errors[0].message == "dart pub outdated returned unexpected JSON: expected an object"


@pytest.mark.parametrize("data", [
    {"advisories": {}},
    {"advisories": [None]},
    {"advisories": [{"affected": [None]}]},
    {"advisories": [{"affected": [{"versions": [], "ranges": [None]}]}]},
    {"advisories": [{"affected": [{"versions": ["1.0"], "ranges": [{"events": [None]}]}]}]},
    {"advisories": [{"affected": [{"versions": ["1.0"]}], "database_specific": []}]},
])
def test_match_pub_advisories_rejects_malformed_api_data(data):
    with pytest.raises(AuditToolError, match="pub.dev advisory response"):
        match_pub_advisories("app", "1.0", data)


def test_dart_audit_continues_after_malformed_package_advisory(tmp_path, monkeypatch):
    from dependency_audit.models import Ecosystem, StackError

    outdated = json.dumps({"packages": [
        {"package": "broken", "current": {"version": "1.0"}, "isCurrentAffectedByAdvisory": True},
        {"package": "valid", "current": {"version": "2.0"}, "isCurrentAffectedByAdvisory": True},
    ]})
    monkeypatch.setattr("dependency_audit.dart_stack._dart_command", lambda _checkout, _name: ["dart"])
    monkeypatch.setattr("dependency_audit.dart_stack.run_tool", lambda *_args, **_kwargs: outdated)
    monkeypatch.setattr("dependency_audit.dart_stack.fetch_pub_advisories", lambda _package: {})

    def fetch(package):
        if package == "broken":
            return {"advisories": None}
        return {"advisories": [{"id": "OSV-valid", "affected": [{"versions": ["2.0"]}]}]}

    report = AuditReport()
    audit_dart(tmp_path, report, fetch)

    assert report.advisories[0].id == "OSV-valid"
    assert report.errors == [StackError(Ecosystem.DART, "pub.dev advisory response has invalid advisories")]


@pytest.mark.parametrize("pin", [".fvmrc", ".fvm"])
@pytest.mark.parametrize("is_flutter,tool_name", [(True, "flutter"), (False, "dart")])
def test_dart_audit_uses_fvm_for_pinned_checkout(tmp_path, monkeypatch, pin, is_flutter, tool_name):
    if pin == ".fvmrc":
        (tmp_path / pin).write_text('{"flutter": "3.24.0"}', encoding="utf-8")
    else:
        (tmp_path / pin).mkdir()
    if is_flutter:
        (tmp_path / "pubspec.yaml").write_text(
            "dependencies:\n  flutter:\n    sdk: flutter\n", encoding="utf-8"
        )

    calls = []
    monkeypatch.setattr(
        "dependency_audit.dart_stack.shutil.which",
        lambda name: {"fvm": "C:/tools/fvm.bat"}.get(name),
    )
    monkeypatch.setattr("dependency_audit.dart_stack.Settings", lambda: type("S", (), {"get_path": lambda *_: None})())
    monkeypatch.setattr("dependency_audit.dart_stack.run_tool", lambda command, *_: calls.append(command) or '{"packages": []}')

    report = AuditReport()
    audit_dart(tmp_path, report)

    assert calls == [["C:/tools/fvm.bat", tool_name, "pub", "outdated", "--json"]]
    assert report.errors == []


def test_dart_audit_does_not_use_fvm_for_unpinned_checkout(tmp_path, monkeypatch):
    calls = []
    found = {"fvm": "C:/tools/fvm.bat", "dart": "C:/dart/dart.exe"}
    monkeypatch.setattr("dependency_audit.dart_stack.shutil.which", found.get)
    monkeypatch.setattr("dependency_audit.dart_stack.Settings", lambda: type("S", (), {"get_path": lambda *_: None})())
    monkeypatch.setattr("dependency_audit.dart_stack.run_tool", lambda command, *_: calls.append(command) or '{"packages": []}')

    report = AuditReport()
    audit_dart(tmp_path, report)

    assert calls == [["C:/dart/dart.exe", "pub", "outdated", "--json"]]
    assert report.errors == []


def test_dart_audit_pinned_without_fvm_keeps_tool_lookup_error(tmp_path, monkeypatch):
    (tmp_path / ".fvmrc").touch()
    (tmp_path / "pubspec.yaml").write_text(
        "dependencies:\n  flutter:\n    sdk: flutter\n", encoding="utf-8"
    )
    monkeypatch.setattr("dependency_audit.dart_stack.shutil.which", lambda _name: None)
    monkeypatch.setattr("dependency_audit.dart_stack.Settings", lambda: type("S", (), {"get_path": lambda *_: None})())

    report = AuditReport()
    audit_dart(tmp_path, report)

    assert report.errors == [StackError(Ecosystem.DART, "flutter not found")]


def test_flutter_detection_reads_pubspec(tmp_path: Path):
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text("dependencies:\n  flutter:\n    sdk: flutter\n", encoding="utf-8")
    assert is_flutter_project(tmp_path)
    pubspec.write_text("dependencies:\n  http: ^1.0.0\n", encoding="utf-8")
    assert not is_flutter_project(tmp_path)


def test_run_dependency_audit_keeps_other_stacks_when_composer_missing(tmp_path, monkeypatch):
    (tmp_path / "uv.lock").touch()
    (tmp_path / "composer.lock").write_text('{"packages": [], "packages-dev": []}', encoding="utf-8")

    def resolve(name):
        if name == "composer":
            from dependency_audit.command import AuditToolError
            raise AuditToolError("composer not found")
        return name

    monkeypatch.setattr("dependency_audit.python_stack.resolve_tool", resolve)
    monkeypatch.setattr("dependency_audit.python_stack.run_tool", lambda *args, **kwargs: (
        '{"dependencies":[{"name":"jinja2","version":"3.1.3","vulns":[{"id":"GHSA-1","fix_versions":["3.1.4"],"description":"issue"}]}]}'
        if "pip-audit" in str(args[0]) else "pydantic v1.0 (latest: v2.0)"
    ))
    monkeypatch.setattr("dependency_audit.php_stack.resolve_tool", resolve)

    report = []
    monkeypatch.setattr("dependency_audit.print_report", lambda value: report.append(value))

    assert run_dependency_audit(str(tmp_path)) == 0
    assert report[0].advisories[0].package == "jinja2"
    assert any(error.ecosystem.value == "php" for error in report[0].errors)


def test_run_dependency_audit_empty_and_invalid_path(tmp_path, capsys):
    assert run_dependency_audit(str(tmp_path)) == 0
    assert json.loads(capsys.readouterr().out) == {"advisories": [], "outdated": [], "errors": []}
    assert run_dependency_audit(str(tmp_path / "missing")) == 2
    assert capsys.readouterr().out == ""


def test_run_dependency_audit_logs_invalid_path_and_stack_errors(tmp_path, monkeypatch):
    from logger import Logger

    stream = StringIO()
    assert run_dependency_audit(str(tmp_path / "missing"), Logger(stream=stream)) == 2
    assert "not a directory" in stream.getvalue()

    (tmp_path / "uv.lock").touch()
    monkeypatch.setattr(
        "dependency_audit.python_stack.audit",
        lambda _checkout, report: report.errors.append(StackError(Ecosystem.PYTHON, "uv not found")),
    )
    monkeypatch.setattr("dependency_audit.print_report", lambda _report: None)
    stream = StringIO()
    run_dependency_audit(str(tmp_path), Logger(stream=stream))
    assert "python dependency audit failed: uv not found" in stream.getvalue()


def test_audit_report_uses_ticket_shape_and_null_fixed():
    report = AuditReport()

    assert set(report.to_dict()) == {"advisories", "outdated", "errors"}
    assert report.to_dict() == {"advisories": [], "outdated": [], "errors": []}
