import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_php_rule_switch_filters_disabled_php_finding(tmp_path: Path):
    rule = _rule(tmp_path, {
        "php_rules": {"php-hardcoded-fallback": False},
        "php_rule_severity": {"php-potential-n-plus-one": "info"},
    })
    rule._run_subprocess = _fake_run(0, json.dumps({
        "results": [
            {"check_id": "php-hardcoded-fallback", "path": "sample.php",
             "start": {"line": 3, "col": 1},
             "extra": {"message": "Potential fallback", "severity": "WARNING"}},
            {"check_id": "php-potential-n-plus-one", "path": "sample.php",
             "start": {"line": 4, "col": 1},
             "extra": {"message": "Potential query", "severity": "WARNING"}},
        ],
        "errors": [],
    }))

    result = rule._run(tmp_path)

    assert [violation.message for violation in result.violations] == ["Potential query [php-potential-n-plus-one]"]
    assert result.violations[0].severity == Severity.INFO


def test_php_findings_are_omitted_when_php_is_not_selected(tmp_path: Path):
    rule = _rule(tmp_path, {"_selected_languages": ["python"]})
    rule._run_subprocess = _fake_run(0, json.dumps({
        "results": [
            {"check_id": "php-hardcoded-fallback", "path": "sample.php",
             "start": {"line": 3, "col": 1},
             "extra": {"message": "Potential fallback", "severity": "WARNING"}},
            {"check_id": "complex-boolean-condition", "path": "sample.py",
             "start": {"line": 4, "col": 1},
             "extra": {"message": "Complex condition", "severity": "WARNING"}},
        ],
        "errors": [],
    }))

    result = rule._run(tmp_path)

    assert len(result.violations) == 1
    assert result.violations[0].file_path == "sample.py"


def test_php_findings_preserve_function_metadata_and_recommendation(tmp_path: Path):
    rule = _rule(tmp_path, {"_selected_languages": ["php"]})
    rule._run_subprocess = _fake_run(0, json.dumps({
        "results": [{
            "check_id": "php-potential-n-plus-one",
            "path": "sample.php",
            "start": {"line": 8, "col": 5},
            "extra": {
                "message": "Potential N+1 risk",
                "severity": "WARNING",
                "metavars": {"$FUNCTION": {"abstract_content": "buildContent"}},
                "metadata": {
                    "confidence": "medium",
                    "evidence": "repository lookup inside a loop",
                    "recommendation": "Batch the repository lookup.",
                },
            },
        }],
        "errors": [],
    }))

    result = rule._run(tmp_path)

    violation = result.violations[0]
    assert violation.function_name == "buildContent"
    assert violation.confidence == "medium"
    assert violation.evidence == "repository lookup inside a loop"
    assert violation.recommendation == "Batch the repository lookup."


def test_php_exclusions_do_not_suppress_findings_in_other_languages(tmp_path: Path):
    rule = _rule(tmp_path, {"php_exclude_patterns": ["generated"]})
    rule._run_subprocess = _fake_run(0, json.dumps({
        "results": [
            {"check_id": "php-hardcoded-fallback", "path": "generated/sample.php",
             "start": {"line": 3, "col": 1},
             "extra": {"message": "Potential fallback", "severity": "WARNING"}},
            {"check_id": "complex-boolean-condition", "path": "generated/sample.js",
             "start": {"line": 4, "col": 1},
             "extra": {"message": "Complex condition", "severity": "WARNING"}},
        ],
        "errors": [],
    }))

    result = rule._run(tmp_path)

    assert len(result.violations) == 1
    assert result.violations[0].file_path.replace("\\", "/") == "generated/sample.js"


@pytest.mark.skipif(shutil.which("semgrep") is None, reason="Semgrep executable is optional")
def test_php_patterns_are_configurable_without_mutating_bundled_rules(tmp_path: Path):
    rule = _rule(tmp_path, {
        "repository_receiver_patterns": [".*repository.*"],
        "repository_method_patterns": ["findById"],
    })

    with rule._bundled_config_context() as config_path:
        php_rules = Path(config_path) / "php_function_patterns.yaml"
        content = php_rules.read_text(encoding="utf-8")
        assert "(?i)(?:.*repository.*)" in content
        assert "(?i)(?:findById)" in content
        assert "findactivebyid" in BUNDLED_RULES_DIR.joinpath("php_function_patterns.yaml").read_text(encoding="utf-8")

        source = tmp_path / "custom-pattern.php"
        source.write_text(
            "<?php\n"
            "function loadOne($requestRepository, $requests) {\n"
            "    foreach ($requests as $request) {\n"
            "        $requestRepository->findById($request->id);\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["semgrep", "scan", "--json", "--metrics=off", "--quiet", "--config", config_path,
             str(source)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert result.returncode in (0, 1), result.stderr
        findings = json.loads(result.stdout)["results"]
        assert any(finding["check_id"].endswith("php-potential-n-plus-one") for finding in findings)


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


@pytest.mark.skipif(shutil.which("semgrep") is None, reason="Semgrep executable is optional")
def test_php_performance_patterns_require_repository_evidence(tmp_path: Path):
    source = tmp_path / "sample.php"
    source.write_text(
        """<?php
        function buildContent(array $requests, $requestRepository, $formatter): void {
            foreach ($requests as $request) {
                $requestRepository->findById($request->id);
                $requestRepository->findById($request->id);
                $formatter->findById($request->id);
            }
        }
        function buildSafeContent(array $requests, $requestRepository): void {
            $records = $requestRepository->findByIds(array_column($requests, 'id'));
            foreach ($records as $record) {
                echo $record->name;
            }
        }
        """,
        encoding="utf-8",
    )

    result = subprocess.run(
        ["semgrep", "scan", "--json", "--metrics=off", "--quiet", "--config",
         str(BUNDLED_RULES_DIR), str(source)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    findings = json.loads(result.stdout)["results"]
    php_findings = [finding for finding in findings if "php-" in finding["check_id"]]

    assert any(finding["check_id"].endswith("php-potential-n-plus-one") for finding in php_findings)
    assert any(finding["check_id"].endswith("php-repeated-expensive-operation")
               for finding in php_findings)
    assert all(finding["start"]["line"] < 6 for finding in php_findings)


@pytest.mark.skipif(shutil.which("semgrep") is None, reason="Semgrep executable is optional")
def test_php_maintainability_patterns_need_multiple_signals(tmp_path: Path):
    source = tmp_path / "sample.php"
    source.write_text(
        """<?php
        function buildContent(array $requests, $requestRepository, $mailer, $renderer): string {
            foreach ($requests as $request) {
                if (!$request->email) { throw new RuntimeException('Missing email'); }
                $user = $requestRepository->findById($request->userId);
                $requestType = $request->type ?? 'general';
                $mailer->send($user->email, $requestType);
            }
            return $renderer->render('email.html', ['requests' => $requests]);
        }
        function safeContent(array $requests): array {
            return array_map(static fn ($request) => $request->type, $requests);
        }
        function hardToTest($requestRepository, $userRepository, $mailer, $renderer): void {
            $requestRepository->findById(1);
            $userRepository->findById(1);
            $mailer->send('user@example.com', 'content');
            $renderer->render('email.html');
        }
        function simpleDependencies($requestRepository, $mailer): void {
            $requestRepository->findById(1);
            $mailer->send('user@example.com', 'content');
        }
        function validateRequest($validator, $request): void {
            $validator->validate($request->email);
            $validator->validate($request->email);
        }
        function validateOnce($validator, $request): void {
            $validator->validate($request->email);
        }
        """,
        encoding="utf-8",
    )

    result = subprocess.run(
        ["semgrep", "scan", "--json", "--metrics=off", "--quiet", "--config",
         str(BUNDLED_RULES_DIR), str(source)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    findings = json.loads(result.stdout)["results"]
    ids = {finding["check_id"] for finding in findings}

    assert any(check_id.endswith("php-mixed-responsibilities") for check_id in ids)
    assert any(check_id.endswith("php-hardcoded-fallback") for check_id in ids)
    assert any(check_id.endswith("php-repeated-validation") for check_id in ids)
    assert any(check_id.endswith("php-many-dependencies") for check_id in ids)
    assert all("potential" in finding["extra"]["message"].lower() for finding in findings)
    dependency_findings = [finding for finding in findings
                           if finding["check_id"].endswith("php-many-dependencies")]
    assert [finding["start"]["line"] for finding in dependency_findings] == [14]


@pytest.mark.skipif(shutil.which("semgrep") is None, reason="Semgrep executable is optional")
def test_php_nested_queries_and_duplicate_sensitive_counting_are_risk_findings(tmp_path: Path):
    source = tmp_path / "sample.php"
    source.write_text(
        """<?php
        function groupRequests(array $requests, $userRepository, $formatter): int {
            $requestCount = 0;
            foreach ($requests as $request) {
                foreach ($request->entries as $entry) {
                    $userRepository->findActiveById($entry->userId);
                    $formatter->findActiveById($entry->userId);
                    $requestCount++;
                }
            }
            return $requestCount;
        }
        function groupBatched(array $requests, $userRepository): array {
            $users = $userRepository->findByIds(array_column($requests, 'userId'));
            return array_unique(array_column($users, 'id'));
        }
        """,
        encoding="utf-8",
    )

    result = subprocess.run(
        ["semgrep", "scan", "--json", "--metrics=off", "--quiet", "--config",
         str(BUNDLED_RULES_DIR), str(source)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    findings = json.loads(result.stdout)["results"]
    ids = {finding["check_id"] for finding in findings}

    assert any(check_id.endswith("php-potential-n-plus-one") for check_id in ids)
    assert any(check_id.endswith("php-nested-database-loop-risk") for check_id in ids)
    assert any(check_id.endswith("php-duplicate-sensitive-counting") for check_id in ids)
    assert all(finding["extra"]["metadata"]["confidence"] == "low"
               for finding in findings
               if finding["check_id"].endswith("php-duplicate-sensitive-counting"))
    assert not any(finding["start"]["line"] > 10 for finding in findings)
