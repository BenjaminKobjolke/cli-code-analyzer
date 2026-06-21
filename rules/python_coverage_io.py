"""Shared coverage.py command runner for Python coverage-based rules."""

import shutil
from pathlib import Path


def run_tests_with_coverage(rule, coverage_json: Path) -> bool:
    """Run configured coverage commands for a rule and export coverage JSON."""
    timeout = rule.config.get('test_timeout', 600)
    run_cmd = rule.config.get('run_command') or ['python', '-m', 'coverage', 'run', '-m', 'pytest']
    json_cmd = rule.config.get('json_command') or ['python', '-m', 'coverage', 'json', '-o', str(coverage_json)]

    if not shutil.which(run_cmd[0]):
        rule.logger.warning(f"Warning: '{run_cmd[0]}' not in PATH; install with: pip install coverage pytest")
        return False

    rule.logger.info(f"Running: {' '.join(run_cmd)} (this may take a while)...")
    try:
        run_result = rule._run_subprocess(run_cmd, rule.base_path, timeout=timeout)
        if run_result.returncode != 0 and run_result.stderr:
            rule.logger.info(f"Coverage run stderr: {run_result.stderr.strip()[:500]}")
    except Exception as e:
        rule.logger.error(f"Error running coverage: {e}")
        return False

    rule.logger.info(f"Exporting coverage to {coverage_json}...")
    try:
        json_result = rule._run_subprocess(json_cmd, rule.base_path, timeout=timeout)
        if json_result.returncode != 0:
            if json_result.stderr:
                rule.logger.warning(f"coverage json stderr: {json_result.stderr.strip()[:500]}")
            return False
        return True
    except Exception as e:
        rule.logger.error(f"Error exporting coverage JSON: {e}")
        return False
