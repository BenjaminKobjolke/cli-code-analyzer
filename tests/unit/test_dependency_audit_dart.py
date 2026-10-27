"""Focused tests for Dart and Flutter dependency audits."""

import json

import pytest

from dependency_audit.command import AuditToolError
from dependency_audit.dart_stack import audit as audit_dart
from dependency_audit.dart_stack import match_pub_advisories, parse_pub_outdated
from dependency_audit.models import AuditReport, Ecosystem, StackError


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
    with pytest.raises(AuditToolError, match=r"pub\.dev advisory response"):
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


