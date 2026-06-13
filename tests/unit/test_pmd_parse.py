"""Characterization test for PMD CPD XML parsing.

GREEN against current code. Locks the namespace fix: PMD 7.x emits CPD XML with a
default namespace, so the parser must match elements namespace-agnostically. This
test must stay green through the RuleResult refactor.
"""
from pathlib import Path

from logger import Logger
from rules import PMDDuplicatesRule
from rules.context import RuleContext

# Real PMD 7.x CPD output shape: default namespace on the root, one <duplication>
# with two <file> occurrences.
NAMESPACED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<pmd-cpd xmlns="https://pmd-code.org/schema/cpd-report" pmdVersion="7.17.0" timestamp="2026-06-13T00:00:00">
   <duplication lines="27" tokens="205">
      <file column="5" endcolumn="6" endline="47" line="21" path="C:\\proj\\src\\A.php"/>
      <file column="5" endcolumn="6" endline="45" line="19" path="C:\\proj\\src\\B.php"/>
      <codefragment><![CDATA[ duplicated code body ]]></codefragment>
   </duplication>
</pmd-cpd>
"""


def _rule(base_path: Path) -> PMDDuplicatesRule:
    return PMDDuplicatesRule(RuleContext(config={}, base_path=base_path, logger=Logger(quiet=True)))


def test_namespaced_xml_yields_one_violation_per_file_occurrence(tmp_path: Path):
    violations = _rule(tmp_path)._parse_xml_output(NAMESPACED_XML)
    # one <duplication> with two <file> entries -> two violations
    assert len(violations) == 2


def test_namespaced_violations_are_tagged_pmd_duplicates(tmp_path: Path):
    violations = _rule(tmp_path)._parse_xml_output(NAMESPACED_XML)
    assert violations
    assert all(v.rule_name == "pmd_duplicates" for v in violations)
