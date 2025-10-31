"""
Rules module
"""

from rules.base import BaseRule
from rules.max_lines import MaxLinesRule
from rules.pmd_duplicates import PMDDuplicatesRule

__all__ = ['BaseRule', 'MaxLinesRule', 'PMDDuplicatesRule']
