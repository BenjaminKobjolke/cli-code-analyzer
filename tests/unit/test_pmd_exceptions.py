"""Tests for pmd_duplicates per-pair / per-file `exceptions` suppression.

Exercises PMDDuplicatesRule._parse_xml_output directly (the same entry point as
test_pmd_parse.py), feeding hand-built PMD 7.x CPD XML whose <file> paths live
under tmp_path so relative_to(base_path) resolves.
"""
from pathlib import Path

from logger import Logger
from rules import PMDDuplicatesRule
from rules.context import RuleContext

PMD_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<pmd-cpd xmlns="https://pmd-code.org/schema/cpd-report" pmdVersion="7.17.0" '
    'timestamp="2026-06-13T00:00:00">'
)


def _duplication(paths: list[Path], lines: int = 27, tokens: int = 205) -> str:
    files = ''.join(
        f'<file column="5" endcolumn="6" endline="47" line="19" path="{p}"/>'
        for p in paths
    )
    return f'<duplication lines="{lines}" tokens="{tokens}">{files}<codefragment><![CDATA[ body ]]></codefragment></duplication>'


def _xml(*groups: str) -> str:
    return f"{PMD_HEADER}{''.join(groups)}</pmd-cpd>"


def _rule(tmp_path: Path, exceptions=None) -> PMDDuplicatesRule:
    config = {'exceptions': exceptions} if exceptions is not None else {}
    return PMDDuplicatesRule(RuleContext(config=config, base_path=tmp_path, logger=Logger(quiet=True)))


def _paths(tmp_path: Path, *names: str) -> list[Path]:
    out = []
    for name in names:
        p = tmp_path / 'src' / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
        out.append(p)
    return out


def test_no_exceptions_yields_two_violations(tmp_path: Path):
    a, b = _paths(tmp_path, "A.php", "B.php")
    violations = _rule(tmp_path)._parse_xml_output(_xml(_duplication([a, b])))
    assert len(violations) == 2


def test_pair_exception_suppresses_both_occurrences(tmp_path: Path):
    a, b = _paths(tmp_path, "A.php", "B.php")
    rule = _rule(tmp_path, [
        {"file": "src/A.php", "duplicate_of": "src/B.php", "reason": "data models"},
    ])
    violations = rule._parse_xml_output(_xml(_duplication([a, b])))
    assert violations == []


def test_pair_exception_is_symmetric_regardless_of_order(tmp_path: Path):
    a, b = _paths(tmp_path, "A.php", "B.php")
    # exception names B first; the B<->A duplication must still be fully suppressed
    rule = _rule(tmp_path, [
        {"file": "src/B.php", "duplicate_of": "src/A.php", "reason": "data models"},
    ])
    violations = rule._parse_xml_output(_xml(_duplication([a, b])))
    assert violations == []


def test_file_level_exception_drops_only_that_file(tmp_path: Path):
    a, b = _paths(tmp_path, "A.php", "B.php")
    rule = _rule(tmp_path, [{"file": "src/A.php", "reason": "generated-ish"}])
    violations = rule._parse_xml_output(_xml(_duplication([a, b])))
    assert len(violations) == 1
    assert violations[0].file_path.endswith("B.php")


def test_exception_without_reason_is_ignored(tmp_path: Path):
    a, b = _paths(tmp_path, "A.php", "B.php")
    rule = _rule(tmp_path, [{"file": "src/A.php", "duplicate_of": "src/B.php"}])
    violations = rule._parse_xml_output(_xml(_duplication([a, b])))
    assert len(violations) == 2


def test_other_pair_still_reported_when_one_pair_excepted(tmp_path: Path):
    a, b, c = _paths(tmp_path, "A.php", "B.php", "C.php")
    rule = _rule(tmp_path, [
        {"file": "src/A.php", "duplicate_of": "src/B.php", "reason": "data models"},
    ])
    # group 1: A<->B (suppressed)   group 2: A<->C (must survive)
    violations = rule._parse_xml_output(_xml(_duplication([a, b]), _duplication([a, c])))
    assert len(violations) == 2
    reported = sorted(v.file_path.replace("\\", "/").rsplit("/", 1)[-1] for v in violations)
    assert reported == ["A.php", "C.php"]


def test_glob_file_level_exception(tmp_path: Path):
    bal, tx = _paths(tmp_path, "Controller/BankBalanceController.php",
                     "Controller/BankTransactionController.php")
    rule = _rule(tmp_path, [
        {"file": "src/Controller/Bank*Controller.php", "reason": "CRUD boilerplate"},
    ])
    violations = rule._parse_xml_output(_xml(_duplication([bal, tx])))
    assert violations == []
