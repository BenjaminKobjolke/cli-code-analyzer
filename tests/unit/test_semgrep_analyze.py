import json
from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from models import RuleStatus, Severity
from rules.context import RuleContext
from rules.semgrep_analyze import BUNDLED_RULES_DIR, SemgrepAnalyzeRule


def _rule(tmp_path: Path, config: dict, filter_files=None) -> SemgrepAnalyzeRule:
    rule = SemgrepAnalyzeRule(RuleContext(
        config=config,
        base_path=tmp_path,
        filter_files=filter_files,
        logger=Logger(quiet=True),
    ))
    rule._get_tool_path = lambda *_args, **_kwargs: "semgrep"
    return rule


def _fake_run(returncode: int, stdout: str, stderr: str = ""):
    def run(cmd, *_args, **_kwargs):
        run.cmd = cmd
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    run.cmd = None
    return run


def _result_json() -> str:
    return json.dumps({
        "results": [{
            "check_id": "complex-boolean-condition",
            "path": "lib/foo.dart",
            "start": {"line": 42, "col": 5},
            "extra": {"message": "Complex boolean condition (3+ operands).", "severity": "WARNING"},
        }],
        "errors": [],
    })


def test_parses_results_into_violations(tmp_path: Path):
    rule = _rule(tmp_path, {})
    rule._run_subprocess = _fake_run(1, _result_json())

    result = rule._run(tmp_path)

    assert result.status == RuleStatus.OK
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.line == 42
    assert violation.column == 5
    assert violation.severity == Severity.WARNING
    assert "complex-boolean-condition" in violation.message


def test_scopes_to_changed_files_and_uses_bundled_config(tmp_path: Path):
    changed = tmp_path / "lib" / "foo.dart"
    changed.parent.mkdir()
    changed.write_text("void main() {}\n", encoding="utf-8")

    rule = _rule(tmp_path, {}, filter_files={"lib/foo.dart"})
    fake = _fake_run(0, json.dumps({"results": [], "errors": []}))
    rule._run_subprocess = fake

    result = rule._run(tmp_path)

    assert result.status == RuleStatus.OK
    assert str(changed) in fake.cmd
    assert fake.cmd[fake.cmd.index("--config") + 1] == str(BUNDLED_RULES_DIR)


def test_no_matching_changed_files_skips_subprocess(tmp_path: Path):
    rule = _rule(tmp_path, {}, filter_files={"script.ahk"})
    fake = _fake_run(0, "")
    rule._run_subprocess = fake

    result = rule._run(tmp_path)

    assert result.status == RuleStatus.OK
    assert result.violations == []
    assert fake.cmd is None


def test_nonzero_exit_without_output_fails(tmp_path: Path):
    rule = _rule(tmp_path, {})
    rule._run_subprocess = _fake_run(2, "", "fatal: bad config")

    result = rule._run(tmp_path)

    assert result.status == RuleStatus.FAILED
    assert "fatal: bad config" in result.message


def test_non_json_output_fails(tmp_path: Path):
    rule = _rule(tmp_path, {})
    rule._run_subprocess = _fake_run(0, "not json at all")

    result = rule._run(tmp_path)

    assert result.status == RuleStatus.FAILED


def test_config_override_passes_registry_ref(tmp_path: Path):
    rule = _rule(tmp_path, {"config": "p/default"})
    fake = _fake_run(0, json.dumps({"results": [], "errors": []}))
    rule._run_subprocess = fake

    rule._run(tmp_path)

    assert fake.cmd[fake.cmd.index("--config") + 1] == "p/default"


def test_semgrep_merges_batches(tmp_path: Path, monkeypatch):
    monkeypatch.setattr('rules.filter_scope.MAX_COMMAND_CHARS', 270)
    names = {f'deep/{i:03d}_long_name.dart' for i in range(4)}
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.touch()
    rule = _rule(tmp_path, {}, filter_files=names)
    calls = []

    def run(cmd, _cwd):
        calls.append(cmd)
        data = {'results': [{'check_id': 'x', 'path': p, 'start': {'line': 1, 'col': 1},
                             'extra': {'message': 'bad', 'severity': 'WARNING'}}
                            for p in cmd if p.endswith('.dart')], 'errors': []}
        return SimpleNamespace(returncode=1, stdout=json.dumps(data), stderr='')

    rule._run_subprocess = run
    result = rule._run(tmp_path)
    assert result.status == RuleStatus.OK
    assert len(calls) > 1
    assert len(result.violations) == 4


def test_semgrep_fails_fatal_error_in_later_batch_without_partial_results(tmp_path: Path, monkeypatch):
    monkeypatch.setattr('rules.filter_scope.MAX_COMMAND_CHARS', 270)
    names = {f'deep/{i:03d}_long_name.dart' for i in range(4)}
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.touch()
    rule = _rule(tmp_path, {}, filter_files=names)
    calls = []

    def run(cmd, _cwd):
        calls.append(cmd)
        if len(calls) > 1:
            return SimpleNamespace(returncode=2, stdout='{"results": [], "errors": '
                                   '[{"message": "invalid rule configuration"}]}', stderr='')
        return SimpleNamespace(returncode=1, stdout=_result_json(), stderr='')

    rule._run_subprocess = run
    result = rule._run(tmp_path)
    assert result.status == RuleStatus.FAILED
    assert result.violations == []
    assert len(calls) > 1
