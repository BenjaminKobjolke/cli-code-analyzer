"""
Configuration loading and validation
"""

import json
import sys
from typing import Dict, Any


class Config:
    """Handles loading and accessing rule configurations"""

    def __init__(self, rules_file: str):
        self.rules_file = rules_file
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, Any]:
        """Load rules from JSON file"""
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Rules file '{self.rules_file}' not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in rules file: {e}")
            sys.exit(1)

    def get_rule(self, rule_name: str) -> Dict[str, Any]:
        """Get configuration for a specific rule"""
        return self.rules.get(rule_name, {})

    def is_rule_enabled(self, rule_name: str) -> bool:
        """Check if a rule is enabled"""
        rule = self.get_rule(rule_name)
        return rule.get('enabled', False)

    def get_global_log_level(self) -> str:
        """Get global log level from rules configuration.

        Returns:
            Global log level string ('error', 'warning', or 'all'), or None if not set
        """
        return self.rules.get('log_level')

    def get_rule_log_level(self, rule_name: str) -> str:
        """Get log level for a specific rule.

        Args:
            rule_name: Name of the rule

        Returns:
            Rule-specific log level string ('error', 'warning', or 'all'), or None if not set
        """
        rule = self.get_rule(rule_name)
        return rule.get('log_level')
