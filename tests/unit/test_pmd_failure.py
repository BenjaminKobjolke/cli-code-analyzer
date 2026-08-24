"""Spec for the PMD invariant guard (RED until _result_from_pmd_stdout exists).

The original silent bug: PMD output clearly contained <duplication> markers, but
the parser matched zero (namespace mismatch), so the rule returned "clean". The
guard turns that exact contradiction — marker present, parsed zero — into a loud
FAILED instead of a false clean.
"""
from pathlib import Path

from logger import Logger
from models import RuleStatus
from rules import PMDDuplicatesRule
from rules.context import RuleContext

GOOD_NAMESPACED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<pmd-cpd xmlns="https://pmd-code.org/schema/cpd-report" pmdVersion="7.17.0" timestamp="2026-06-13T00:00:00">
   <duplication lines="27" tokens="205">
      <file column="5" endcolumn="6" endline="47" line="21" path="C:\\proj\\src\\A.php"/>
      <file column="5" endcolumn="6" endline="45" line="19" path="C:\\proj\\src\\B.php"/>
      <codefragment><![CDATA[ duplicated code body ]]></codefragment>
   </duplication>
</pmd-cpd>
"""

# Well-formed XML that contains the literal "<duplication" marker (here inside a
# comment) but yields zero parsed duplications — the schema/namespace-mismatch shape.
MARKER_BUT_ZERO_PARSED = (
    '<pmd-cpd xmlns="https://pmd-code.org/schema/cpd-report">'
    '<!-- <duplication lines="3" tokens="120"> would-be content --></pmd-cpd>'
)

# No marker at all -> genuinely no duplicates -> OK with empty violations.
NO_DUPLICATES = '<pmd-cpd xmlns="https://pmd-code.org/schema/cpd-report"></pmd-cpd>'


def _rule(base_path: Path) -> PMDDuplicatesRule:
    return PMDDuplicatesRule(RuleContext(config={}, base_path=base_path, logger=Logger(quiet=True)))


def test_good_output_is_ok_with_violations(tmp_path: Path):
    res = _rule(tmp_path)._result_from_pmd_stdout(GOOD_NAMESPACED_XML)
    assert res.status == RuleStatus.OK
    assert len(res.violations) == 2


def test_marker_present_but_zero_parsed_is_failed(tmp_path: Path):
    res = _rule(tmp_path)._result_from_pmd_stdout(MARKER_BUT_ZERO_PARSED)
    assert res.status == RuleStatus.FAILED


def test_no_duplicates_is_ok_and_empty(tmp_path: Path):
    res = _rule(tmp_path)._result_from_pmd_stdout(NO_DUPLICATES)
    assert res.status == RuleStatus.OK
    assert res.violations == []


def test_all_suppressed_by_exceptions_is_ok_not_failed(tmp_path: Path):
    """A duplication that parses but is fully suppressed by exceptions is a
    clean OK — not the schema-mismatch FAILED (regression: the guard used to key
    off surviving violations, so suppressing every finding tripped a false
    failure)."""
    a = tmp_path / "src" / "A.php"
    b = tmp_path / "src" / "B.php"
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_text("")
    b.write_text("")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<pmd-cpd xmlns="https://pmd-code.org/schema/cpd-report" pmdVersion="7.17.0">'
        '<duplication lines="27" tokens="205">'
        f'<file column="5" endcolumn="6" endline="47" line="19" path="{a}"/>'
        f'<file column="5" endcolumn="6" endline="45" line="17" path="{b}"/>'
        '<codefragment><![CDATA[ body ]]></codefragment>'
        '</duplication></pmd-cpd>'
    )
    rule = PMDDuplicatesRule(RuleContext(
        config={'exceptions': [
            {"file": "src/A.php", "duplicate_of": "src/B.php", "reason": "data models"},
        ]},
        base_path=tmp_path,
        logger=Logger(quiet=True),
    ))
    res = rule._result_from_pmd_stdout(xml)
    assert res.status == RuleStatus.OK
    assert res.violations == []
