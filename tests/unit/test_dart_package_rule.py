"""Tests for rootless Dart workspace package discovery and rule execution."""

from pathlib import Path

from logger import Logger
from models import RuleResult, RuleStatus, Severity, Violation
from rules.context import RuleContext
from rules.dart_utils import find_dart_package_roots


def _pubspec(path: Path, *, linter: bool = True, name: str | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    body = f"name: {name or path.name}\n"
    if linter:
        body += "dev_dependencies:\n  dart_code_linter: ^4.4.2\n"
    (path / "pubspec.yaml").write_text(body, encoding="utf-8")


def _context(base_path: Path, config: dict | None = None) -> RuleContext:
    return RuleContext(config=config or {}, base_path=base_path, logger=Logger(quiet=True))


def test_find_dart_package_roots_skips_nested_and_generated_directories(tmp_path: Path):
    _pubspec(tmp_path / "packages" / "b")
    _pubspec(tmp_path / "packages" / "a")
    _pubspec(tmp_path / "packages" / "a" / "example")
    _pubspec(tmp_path / "web_host")
    _pubspec(tmp_path / "build")
    _pubspec(tmp_path / ".dart_tool" / "x")
    _pubspec(tmp_path / "node_modules" / "y")

    roots = find_dart_package_roots(tmp_path)

    assert [root.relative_to(tmp_path).as_posix() for root in roots] == [
        "packages/a", "packages/b", "web_host"]


def test_find_dart_package_roots_returns_workspace_root_when_it_has_pubspec(tmp_path: Path):
    _pubspec(tmp_path)

    assert find_dart_package_roots(tmp_path) == [tmp_path]


def test_find_dart_package_roots_empty_when_no_package_exists(tmp_path: Path):
    (tmp_path / "src").mkdir()

    assert find_dart_package_roots(tmp_path) == []


def test_workspace_rules_run_once_per_package_and_merge_violations(tmp_path: Path):
    from rules.dart_package_rule import DartPackageRule

    _pubspec(tmp_path / "packages" / "a")
    _pubspec(tmp_path / "packages" / "b")

    class ProbeRule(DartPackageRule):
        def __init__(self, ctx):
            super().__init__(ctx)
            self.roots = []

        def _run_package(self, file_path: Path) -> RuleResult:
            root = self._find_pubspec()
            self.roots.append(root)
            violation = Violation(str(root), "probe", Severity.WARNING, "found")
            return self._ok([violation])

    rule = ProbeRule(_context(tmp_path))
    result = rule.check(tmp_path)

    assert rule.roots == [tmp_path / "packages" / "a", tmp_path / "packages" / "b"]
    assert result.status == RuleStatus.OK
    assert [v.file_path for v in result.violations] == [str(p) for p in rule.roots]
    assert rule._package_root is None


def test_workspace_rule_preserves_violations_when_a_package_fails(tmp_path: Path):
    from rules.dart_package_rule import DartPackageRule

    _pubspec(tmp_path / "packages" / "a")
    _pubspec(tmp_path / "packages" / "b")

    class ProbeRule(DartPackageRule):
        def _run_package(self, file_path: Path) -> RuleResult:
            root = self._find_pubspec()
            if root.name == "b":
                return self._failed("tool unavailable")
            return self._ok([Violation("packages/a/x.dart", "probe", Severity.WARNING, "found")])

    result = ProbeRule(_context(tmp_path)).check(tmp_path)

    assert result.status == RuleStatus.FAILED
    assert "packages/b" in result.message
    assert result.violations[0].file_path == "packages/a/x.dart"


def test_workspace_rule_converts_package_exception_to_failure_and_continues(tmp_path: Path):
    from rules.dart_package_rule import DartPackageRule

    _pubspec(tmp_path / "packages" / "a")
    _pubspec(tmp_path / "packages" / "b")

    class ProbeRule(DartPackageRule):
        def __init__(self, ctx):
            super().__init__(ctx)
            self.called = []

        def _run_package(self, file_path: Path) -> RuleResult:
            root = self._find_pubspec()
            self.called.append(root.name)
            if root.name == "a":
                raise RuntimeError("broken package")
            return self._ok([])

    rule = ProbeRule(_context(tmp_path))
    result = rule.check(tmp_path)

    assert result.status == RuleStatus.FAILED
    assert "packages/a" in result.message
    assert rule.called == ["a", "b"]
    assert rule._package_root is None


def test_workspace_rule_keeps_all_skipped_status(tmp_path: Path):
    from rules.dart_package_rule import DartPackageRule

    _pubspec(tmp_path / "packages" / "a")
    _pubspec(tmp_path / "packages" / "b")

    class ProbeRule(DartPackageRule):
        def _run_package(self, file_path: Path) -> RuleResult:
            return self._skipped("unsupported")

    result = ProbeRule(_context(tmp_path)).check(tmp_path)

    assert result.status == RuleStatus.SKIPPED
    assert "packages/a" in result.message
    assert "packages/b" in result.message


def test_workspace_rule_uses_single_root_pubspec_behavior(tmp_path: Path):
    from rules.dart_package_rule import DartPackageRule

    _pubspec(tmp_path)
    _pubspec(tmp_path / "packages" / "nested")

    class ProbeRule(DartPackageRule):
        def __init__(self, ctx):
            super().__init__(ctx)
            self.roots = []

        def _run_package(self, file_path: Path) -> RuleResult:
            self.roots.append(self._find_pubspec())
            return self._ok([])

    rule = ProbeRule(_context(tmp_path))
    rule.check(tmp_path)

    assert rule.roots == [tmp_path]


def test_workspace_rule_without_packages_preserves_existing_skip(tmp_path: Path):
    from rules.dart_package_rule import DartPackageRule

    class ProbeRule(DartPackageRule):
        def _run_package(self, file_path: Path) -> RuleResult:
            return self._skipped("pubspec.yaml not found")

    result = ProbeRule(_context(tmp_path)).check(tmp_path)

    assert result.status == RuleStatus.SKIPPED
    assert result.message == "pubspec.yaml not found"


def test_workspace_filter_paths_only_contains_current_package(tmp_path: Path):
    from rules.dart_package_rule import DartPackageRule

    _pubspec(tmp_path / "packages" / "a")
    _pubspec(tmp_path / "packages" / "b")
    file_a = tmp_path / "packages" / "a" / "lib" / "a.dart"
    file_b = tmp_path / "packages" / "b" / "lib" / "b.dart"
    file_a.parent.mkdir()
    file_b.parent.mkdir()
    file_a.touch()
    file_b.touch()

    class ProbeRule(DartPackageRule):
        def _run_package(self, file_path: Path) -> RuleResult:
            return self._ok([])

    rule = ProbeRule(_context(tmp_path))
    rule._package_root = tmp_path / "packages" / "a"
    rule.filter_files = {"packages/a/lib/a.dart", "packages/b/lib/b.dart"}

    assert rule._filtered_paths((".dart",)) == [file_a]


def test_workspace_rule_detects_fvm_at_workspace_root(tmp_path: Path):
    from rules.dart_package_rule import DartPackageRule

    _pubspec(tmp_path / "packages" / "a")
    (tmp_path / ".fvmrc").write_text("{\"flutter\": \"stable\"}", encoding="utf-8")

    class ProbeRule(DartPackageRule):
        def _run_package(self, file_path: Path) -> RuleResult:
            return self._ok([])

    rule = ProbeRule(_context(tmp_path))
    rule._package_root = tmp_path / "packages" / "a"

    assert rule._is_fvm_project()


def test_workspace_relative_path_uses_workspace_base(tmp_path: Path):
    from rules.dart_package_rule import DartPackageRule

    _pubspec(tmp_path / "packages" / "a")

    class ProbeRule(DartPackageRule):
        def _run_package(self, file_path: Path) -> RuleResult:
            return self._ok([])

    rule = ProbeRule(_context(tmp_path))
    rule._package_root = tmp_path / "packages" / "a"

    assert rule._workspace_relative("lib/a.dart") == "packages/a/lib/a.dart"
    assert rule._workspace_relative(str(tmp_path / "packages" / "a" / "lib" / "a.dart")) == (
        "packages/a/lib/a.dart")


def test_dart_code_linter_runs_from_package_and_uses_workspace_exception_path(tmp_path: Path, monkeypatch):
    from rules.dart_code_linter import DartCodeLinterRule

    package = tmp_path / "packages" / "a"
    _pubspec(package)
    metric_file = package / "lib" / "a.dart"
    metric_file.parent.mkdir()
    metric_file.touch()
    config = {
        "metrics": {"number-of-methods": {"warning": 1, "error": 2}},
        "exceptions": [{"file": "packages/a/lib/a.dart", "metric": "number-of-methods",
                        "warning": 50, "error": 60}],
    }
    rule = DartCodeLinterRule(_context(tmp_path, config))
    monkeypatch.setattr(rule, "_get_dart_command", lambda: ["dart"])

    def run_dcl(dart_cmd):
        report = tmp_path / "report.json"
        report.write_text(
            '{"records":[{"path":"lib/a.dart","fileMetrics":'
            '[{"metricsId":"number-of-methods","value":70}]}]}', encoding="utf-8")
        return rule._ok(rule._parse_metrics_json(report))

    monkeypatch.setattr(rule, "_run_dart_code_linter", run_dcl)
    result = rule.check(tmp_path)

    assert result.status == RuleStatus.OK
    assert result.violations[0].file_path == "packages/a/lib/a.dart"
    assert "60" in result.violations[0].message


def test_dart_code_linter_fails_with_package_name_when_dependency_missing(tmp_path: Path, monkeypatch):
    from rules.dart_code_linter import DartCodeLinterRule

    _pubspec(tmp_path / "packages" / "a")
    _pubspec(tmp_path / "packages" / "b", linter=False)
    rule = DartCodeLinterRule(_context(tmp_path))
    monkeypatch.setattr(rule, "_get_dart_command", lambda: ["dart"])
    monkeypatch.setattr(rule, "_run_dart_code_linter", lambda *args: rule._ok([]))

    result = rule.check(tmp_path)

    assert result.status == RuleStatus.FAILED
    assert "packages/b" in result.message


def test_flutter_analyze_violation_path_is_workspace_relative(tmp_path: Path):
    from rules.flutter_analyze import FlutterAnalyzeRule

    _pubspec(tmp_path / "packages" / "a")
    rule = FlutterAnalyzeRule(_context(tmp_path))
    rule.project_root = tmp_path / "packages" / "a"
    rule._package_root = rule.project_root

    violation = rule._create_violation({
        "file_path": "lib/a.dart", "severity": "warning", "message": "problem",
        "line": 1, "column": 1, "code": "test",
    })

    assert violation.file_path == "packages/a/lib/a.dart"


def test_lcov_path_is_workspace_relative(tmp_path: Path):
    from rules.dart_test_coverage import DartTestCoverageRule

    package = tmp_path / "packages" / "a"
    _pubspec(package)
    lcov = tmp_path / "coverage.info"
    lcov.write_text(
        f"SF:{package / 'lib' / 'a.dart'}\nDA:1,1\nend_of_record\n", encoding="utf-8")

    rule = DartTestCoverageRule(_context(tmp_path))
    rule._package_root = package

    assert rule._parse_lcov(lcov, {}) == {"packages/a/lib/a.dart": {"total": 1, "covered": 1}}


def test_unused_dependency_violation_names_workspace_pubspec(tmp_path: Path):
    from rules.dart_unused_dependencies import DartUnusedDependenciesRule

    package = tmp_path / "packages" / "a"
    _pubspec(package)
    (package / "pubspec.yaml").write_text(
        "name: a\ndependencies:\n  unused_package: ^1.0.0\n", encoding="utf-8")
    (package / "lib").mkdir()
    rule = DartUnusedDependenciesRule(_context(tmp_path, {
        "ignore_packages": [], "check_dev_dependencies": False,
        "scan_paths": {"dependencies": ["lib"]},
    }))
    rule._package_root = package

    violation = rule._run_package(tmp_path).violations[0]

    assert violation.file_path == "packages/a/pubspec.yaml"
