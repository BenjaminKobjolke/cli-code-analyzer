"""Spec for --only-analyzer subsetting (RED until analyzer.py gains it).

CodeAnalyzer._should_run() must additionally require the analyzer name be in
AnalyzerConfig.only_analyzers when that set is provided. Unknown names in
only_analyzers must produce a warning (nothing to silently swallow). None
(the default) must preserve existing behavior.
"""
from pathlib import Path

from analyzer import AnalyzerConfig, CodeAnalyzer
from logger import Logger

# The analyzer's own rules file — exists in the repo root, has several
# analyzers enabled (max_lines_per_file, ruff_analyze, etc. for python).
RULES_FILE = str(Path(__file__).resolve().parents[2] / "code_analysis_rules.json")


def _analyzer(
    tmp_path: Path,
    only_analyzers=None,
    logger=None,
    languages="python",
    rules_file: str = RULES_FILE,
) -> CodeAnalyzer:
    cfg = AnalyzerConfig(
        languages=languages,
        path=str(tmp_path),
        rules_file=rules_file,
        logger=logger or Logger(quiet=True),
        only_analyzers=only_analyzers,
    )
    return CodeAnalyzer(cfg)


def _write_rules(tmp_path: Path, rules: str) -> str:
    path = tmp_path / "rules.json"
    path.write_text(rules, encoding="utf-8")
    return str(path)


def test_only_analyzers_none_preserves_existing_behavior(tmp_path: Path):
    a = _analyzer(tmp_path, only_analyzers=None)
    # max_lines_per_file is enabled in the repo's own rules file.
    assert a._should_run('max_lines_per_file') is True


def test_only_analyzers_restricts_to_named_set(tmp_path: Path):
    a = _analyzer(tmp_path, only_analyzers={'max_lines_per_file'})
    assert a._should_run('max_lines_per_file') is True
    # ruff_analyze is enabled for python in the repo's rules file too,
    # but excluded here since it's not in only_analyzers.
    assert a._should_run('ruff_analyze') is False


def test_only_analyzers_still_requires_enabled_in_rules(tmp_path: Path):
    # A disabled-in-rules analyzer named in only_analyzers must stay off —
    # only_analyzers narrows, it never re-enables.
    a = _analyzer(tmp_path, only_analyzers={'max_lines_per_file', 'pmd_duplicates'})
    if not a.config.is_rule_enabled('pmd_duplicates'):
        assert a._should_run('pmd_duplicates') is False


def test_unknown_only_analyzer_name_warns(tmp_path: Path, capsys):
    _analyzer(tmp_path, only_analyzers={'not_a_real_analyzer'}, logger=Logger(quiet=False))
    captured = capsys.readouterr()
    assert 'not_a_real_analyzer' in captured.out


def test_php_analyzers_default_on_when_rules_are_absent(tmp_path: Path):
    analyzer = _analyzer(
        tmp_path,
        languages="php",
        rules_file=_write_rules(tmp_path, "{}"),
    )

    assert analyzer._should_run("phpmd_analyze") is True
    assert analyzer._should_run("php_function_quality") is True
    assert analyzer._should_run("semgrep_analyze") is True


def test_php_analyzers_can_be_explicitly_disabled(tmp_path: Path):
    rules = '{"phpmd_analyze":{"enabled":false},"php_function_quality":{"enabled":false},"semgrep_analyze":{"enabled":false}}'
    analyzer = _analyzer(
        tmp_path,
        languages="php",
        rules_file=_write_rules(tmp_path, rules),
    )

    assert analyzer._should_run("phpmd_analyze") is False
    assert analyzer._should_run("php_function_quality") is False
    assert analyzer._should_run("semgrep_analyze") is False


def test_php_defaults_do_not_enable_analyzers_for_other_languages(tmp_path: Path):
    analyzer = _analyzer(
        tmp_path,
        languages="python",
        rules_file=_write_rules(tmp_path, "{}"),
    )

    assert analyzer._should_run("semgrep_analyze") is False
    assert analyzer._should_run("phpmd_analyze") is False
    assert analyzer._should_run("php_function_quality") is False


def test_only_analyzer_narrows_php_defaults(tmp_path: Path):
    analyzer = _analyzer(
        tmp_path,
        only_analyzers={"phpmd_analyze"},
        languages="php",
        rules_file=_write_rules(tmp_path, "{}"),
    )

    assert analyzer._should_run("phpmd_analyze") is True
    assert analyzer._should_run("php_function_quality") is False
    assert analyzer._should_run("semgrep_analyze") is False
