"""
ESLint analyze rule for JavaScript/TypeScript code analysis
"""

import json
from pathlib import Path

from models import RuleResult
from rules.base import ProjectWideRule
from rules.context import RuleContext
from rules.eslint_report import parse_eslint_json, write_eslint_csv


class ESLintAnalyzeRule(ProjectWideRule):
    """Rule to analyze JavaScript/TypeScript code using ESLint linter"""

    rule_name = 'eslint_analyze'

    def __init__(self, ctx: RuleContext):
        super().__init__(ctx)
        self._svelte_files_cache = None

    def _run(self, _file_path: Path) -> RuleResult:
        self.logger.info("\nRunning ESLint check...")

        # Check for local node_modules eslint first
        eslint_path = self._find_local_eslint()
        if not eslint_path:
            # If this looks like a Node.js project, suggest local install
            if (self.base_path / 'package.json').exists():
                self.logger.info("\nESLint is not installed in this project.")
                self.logger.info("Install with:")
                self.logger.info("  npm install --save-dev eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin")
                self.logger.info("\nSkipping ESLint analysis.")
                return self._skipped("ESLint is not installed in this Node.js project")
            # Not a Node.js project — try global/settings path
            eslint_path = self._get_tool_path('eslint', self.settings.get_eslint_path, self.settings.prompt_and_save_eslint_path)
        if not eslint_path:
            return self._failed("ESLint executable not found")

        # Run eslint check
        return self._run_eslint_check(eslint_path)

    def _find_local_eslint(self) -> str | None:
        """Check for ESLint installed locally in the project's node_modules.

        Returns:
            Path to local eslint executable, or None if not found
        """
        import platform
        if platform.system() == 'Windows':
            local_eslint = self.base_path / 'node_modules' / '.bin' / 'eslint.cmd'
        else:
            local_eslint = self.base_path / 'node_modules' / '.bin' / 'eslint'
        if local_eslint.exists():
            return str(local_eslint)
        return None

    def _run_eslint_check(self, eslint_path: str) -> RuleResult:
        """Execute eslint check and parse results.

        Args:
            eslint_path: Path to eslint executable

        Returns:
            RuleResult
        """
        # Build command with JSON format
        cmd = [eslint_path, '--format', 'json']

        # Handle config mode
        config_mode = self.config.get('config_mode', 'auto')

        if config_mode == 'builtin':
            # Use builtin rules, ignore project config
            cmd.append('--no-eslintrc')
            # Add env settings
            env_config = self.config.get('env', {})
            for env_name, enabled in env_config.items():
                if enabled:
                    cmd.extend(['--env', env_name])
            # Add rules from config
            rules_config = self.config.get('rules', {})
            for rule_name, rule_value in rules_config.items():
                cmd.extend(['--rule', f'{rule_name}: {rule_value}'])
        elif config_mode == 'project':
            # Require project config - check if it exists
            if not self._has_project_config():
                self.logger.error("Error: config_mode is 'project' but no ESLint config found")
                self.logger.error("Create eslint.config.js or .eslintrc.* in your project")
                return self._skipped("config_mode is 'project' but no ESLint config found")
        # config_mode == 'auto': ESLint will automatically detect project config or use defaults

        # Add exclude patterns as ignore patterns
        if self.config.get('exclude_patterns'):
            for pattern in self.config['exclude_patterns']:
                cmd.extend(['--ignore-pattern', pattern])

        # Add extensions to analyze
        # If explicitly configured, use that; otherwise auto-detect
        if 'extensions' in self.config:
            extensions = self.config['extensions']
        else:
            extensions = ['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx']
            # Auto-include .svelte if eslint-plugin-svelte is available
            if self._has_svelte_eslint_plugin():
                extensions.append('.svelte')
            elif self._has_svelte_files():
                self.logger.warning("Warning: .svelte files found but eslint-plugin-svelte is not installed — skipping ESLint for .svelte files")
                self.logger.warning("  Install it with: npm install --save-dev eslint-plugin-svelte svelte-eslint-parser")
                self.logger.warning("  Then configure your eslint.config.js to use the Svelte parser (see CLI Code Analyzer README)")
        cmd.extend(['--ext', ','.join(extensions)])

        # Add paths to analyze: changed files when filtering, else the whole base path.
        scope = self._scope_args(('.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.svelte'), [str(self.base_path)])
        if scope is None:
            return self._ok([])
        cmd += scope

        # Execute eslint using base utility
        try:
            result = self._run_subprocess(cmd, self.base_path)

            # ESLint outputs JSON to stdout
            output = result.stdout

            # Parse JSON output
            violations = parse_eslint_json(output, self._get_relative_path, self.logger)

            # Apply log level filter to violations
            violations = self._filter_violations_by_log_level(violations)

            # Apply max_errors limit to returned violations
            if self.max_errors and len(violations) > self.max_errors:
                violations = violations[:self.max_errors]

            # Print summary
            if violations:
                self.logger.info(f"ESLint found {len(violations)} issue(s)")
            else:
                self.logger.info("ESLint: No issues found")

            # Write to CSV file if output folder is specified and violations found
            if self.output_folder and violations:
                output_file = self.output_folder / 'eslint_analyze.csv'
                write_eslint_csv(output_file, output, self.log_level, self.max_errors,
                                 self._get_relative_path, self.logger)

            return self._ok(violations)

        except FileNotFoundError:
            self.logger.error(f"Error: ESLint executable not found: {eslint_path}")
            self.logger.error("Please ensure ESLint is installed: npm install -g eslint")
            return self._failed(f"ESLint executable not found: {eslint_path}")
        except Exception as e:
            self.logger.error(f"Error running eslint check: {e}")
            return self._failed(f"error running eslint check: {e}")

    def _has_project_config(self) -> bool:
        """Check if project has ESLint configuration.

        Returns:
            True if project config exists
        """
        config_files = [
            'eslint.config.js',
            'eslint.config.mjs',
            'eslint.config.cjs',
            '.eslintrc.js',
            '.eslintrc.cjs',
            '.eslintrc.yaml',
            '.eslintrc.yml',
            '.eslintrc.json',
            '.eslintrc',
        ]
        for config_file in config_files:
            if (self.base_path / config_file).exists():
                return True

        # Also check package.json for eslintConfig
        package_json = self.base_path / 'package.json'
        if package_json.exists():
            try:
                with open(package_json) as f:
                    pkg = json.load(f)
                    if 'eslintConfig' in pkg:
                        return True
            except (json.JSONDecodeError, OSError):
                pass

        return False

    def _has_svelte_eslint_plugin(self) -> bool:
        """Check if the project has eslint-plugin-svelte available.

        Checks for the package in node_modules.

        Returns:
            True if eslint-plugin-svelte is installed
        """
        return (self.base_path / 'node_modules' / 'eslint-plugin-svelte').is_dir()

    def _has_svelte_files(self) -> bool:
        """Check if the project contains any .svelte files (cached after first call).

        Skips node_modules to avoid expensive traversal.

        Returns:
            True if at least one .svelte file exists under base_path
        """
        if self._svelte_files_cache is None:
            self._svelte_files_cache = False
            for path in self.base_path.rglob('*.svelte'):
                if 'node_modules' not in path.parts:
                    self._svelte_files_cache = True
                    break
        return self._svelte_files_cache
