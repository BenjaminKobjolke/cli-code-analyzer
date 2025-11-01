"""
Rules module
"""

from rules.base import BaseRule
from rules.max_lines import MaxLinesRule
from rules.pmd_duplicates import PMDDuplicatesRule
from rules.dart_analyze import DartAnalyzeRule

__all__ = ['BaseRule', 'MaxLinesRule', 'PMDDuplicatesRule', 'DartAnalyzeRule']
