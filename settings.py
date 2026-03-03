"""Settings management for the code analyzer."""
import configparser
from pathlib import Path

from pmd_downloader import download_pmd
from logger import Logger


class Settings:
    """Manages application settings stored in settings.ini"""

    def __init__(self, settings_file: str | None = None, logger=None):
        """Initialize settings manager.

        Args:
            settings_file: Path to the settings INI file. If None, uses settings.ini
                          in the cli-code-analyzer directory.
            logger: Logger instance for output. If None, a default Logger is created.
        """
        self.logger = logger or Logger()
        if settings_file is None:
            # Default to settings.ini in the cli-code-analyzer directory
            script_dir = Path(__file__).parent
            self.settings_file = script_dir / "settings.ini"
        else:
            self.settings_file = Path(settings_file)
        self.config = configparser.ConfigParser()
        self._load()

    def _load(self):
        """Load settings from INI file. Creates file if it doesn't exist."""
        if self.settings_file.exists():
            self.config.read(self.settings_file)

    def _save(self):
        """Save current settings to INI file."""
        with open(self.settings_file, 'w') as f:
            self.config.write(f)

    def get_pmd_path(self) -> str | None:
        """Get the PMD executable path from settings.

        Returns:
            Path to PMD executable or None if not set
        """
        if 'pmd' in self.config and 'pmd_path' in self.config['pmd']:
            return self.config['pmd']['pmd_path']
        return None

    def set_pmd_path(self, path: str):
        """Set the PMD executable path and save to settings.

        Args:
            path: Path to PMD executable
        """
        if 'pmd' not in self.config:
            self.config['pmd'] = {}
        self.config['pmd']['pmd_path'] = path
        self._save()

    def prompt_and_save_pmd_path(self) -> str | None:
        """Prompt user for PMD path or download PMD, validate it, and save to settings.

        Returns:
            Validated PMD path, or None if download/validation failed
        """
        prompt_msg = "PMD path not configured. Enter path to pmd.bat (leave empty to download): "
        user_input = input(prompt_msg).strip()

        # If user pressed enter (empty input), download PMD
        if not user_input:
            self.logger.info("\nDownloading PMD...")
            pmd_path = download_pmd(logger=self.logger)
            if not pmd_path:
                return None
            # Save and return
            self.set_pmd_path(str(pmd_path))
            self.logger.info(f"PMD path saved to {self.settings_file}")
            return str(pmd_path)

        # Validate user-provided path exists
        pmd_path = Path(user_input)
        if not pmd_path.exists():
            self.logger.error(f"Error: PMD executable not found at: {user_input}")
            return None

        # Save and return
        self.set_pmd_path(str(pmd_path))
        self.logger.info(f"PMD path saved to {self.settings_file}")
        return str(pmd_path)

    def get_dart_path(self) -> str | None:
        """Get the Dart executable path from settings.

        Returns:
            Path to Dart executable or None if not set
        """
        if 'dart' in self.config and 'dart_path' in self.config['dart']:
            return self.config['dart']['dart_path']
        return None

    def set_dart_path(self, path: str):
        """Set the Dart executable path and save to settings.

        Args:
            path: Path to Dart executable
        """
        if 'dart' not in self.config:
            self.config['dart'] = {}
        self.config['dart']['dart_path'] = path
        self._save()

    def prompt_and_save_dart_path(self) -> str | None:
        """Prompt user for Dart path, validate it, and save to settings.

        Returns:
            Validated Dart path, or None if validation failed
        """
        self.logger.info("\nDart executable not found in PATH.")
        self.logger.info("Please ensure Flutter/Dart SDK is installed.")
        self.logger.info("Download from: https://docs.flutter.dev/get-started/install")
        prompt_msg = "\nEnter path to dart executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        # If user pressed enter (empty input), skip
        if not user_input:
            self.logger.info("Skipping dart analyze rule. Install Dart SDK and configure later.")
            return None

        # Validate user-provided path exists
        dart_path = Path(user_input)
        if not dart_path.exists():
            self.logger.error(f"Error: Dart executable not found at: {user_input}")
            return None

        # Save and return
        self.set_dart_path(str(dart_path))
        self.logger.info(f"Dart path saved to {self.settings_file}")
        return str(dart_path)

    def get_flutter_path(self) -> str | None:
        """Get the Flutter executable path from settings.

        Returns:
            Path to Flutter executable or None if not set
        """
        if 'flutter' in self.config and 'flutter_path' in self.config['flutter']:
            return self.config['flutter']['flutter_path']
        return None

    def set_flutter_path(self, path: str):
        """Set the Flutter executable path and save to settings.

        Args:
            path: Path to Flutter executable
        """
        if 'flutter' not in self.config:
            self.config['flutter'] = {}
        self.config['flutter']['flutter_path'] = path
        self._save()

    def prompt_and_save_flutter_path(self) -> str | None:
        """Prompt user for Flutter path, validate it, and save to settings.

        Returns:
            Validated Flutter path, or None if validation failed
        """
        self.logger.info("\nFlutter executable not found in PATH.")
        self.logger.info("Please ensure Flutter SDK is installed.")
        self.logger.info("Download from: https://docs.flutter.dev/get-started/install")
        prompt_msg = "\nEnter path to flutter executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        # If user pressed enter (empty input), skip
        if not user_input:
            self.logger.info("Skipping flutter analyze rule. Install Flutter SDK and configure later.")
            return None

        # Validate user-provided path exists
        flutter_path = Path(user_input)
        if not flutter_path.exists():
            self.logger.error(f"Error: Flutter executable not found at: {user_input}")
            return None

        # Save and return
        self.set_flutter_path(str(flutter_path))
        self.logger.info(f"Flutter path saved to {self.settings_file}")
        return str(flutter_path)

    def get_ruff_path(self) -> str | None:
        """Get the Ruff executable path from settings.

        Returns:
            Path to Ruff executable or None if not set
        """
        if 'ruff' in self.config and 'ruff_path' in self.config['ruff']:
            return self.config['ruff']['ruff_path']
        return None

    def set_ruff_path(self, path: str):
        """Set the Ruff executable path and save to settings.

        Args:
            path: Path to Ruff executable
        """
        if 'ruff' not in self.config:
            self.config['ruff'] = {}
        self.config['ruff']['ruff_path'] = path
        self._save()

    def prompt_and_save_ruff_path(self) -> str | None:
        """Prompt user for Ruff path, validate it, and save to settings.

        Returns:
            Validated Ruff path, or None if validation failed
        """
        self.logger.info("\nRuff executable not found in PATH.")
        self.logger.info("Ruff is a fast Python linter written in Rust.")
        self.logger.info("Install with: pip install ruff")
        self.logger.info("Or download from: https://docs.astral.sh/ruff/installation/")
        prompt_msg = "\nEnter path to ruff executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        # If user pressed enter (empty input), skip
        if not user_input:
            self.logger.info("Skipping ruff analyze rule. Install Ruff and configure later.")
            return None

        # Validate user-provided path exists
        ruff_path = Path(user_input)
        if not ruff_path.exists():
            self.logger.error(f"Error: Ruff executable not found at: {user_input}")
            return None

        # Save and return
        self.set_ruff_path(str(ruff_path))
        self.logger.info(f"Ruff path saved to {self.settings_file}")
        return str(ruff_path)

    def get_phpstan_path(self) -> str | None:
        """Get the PHPStan executable path from settings."""
        if 'phpstan' in self.config and 'phpstan_path' in self.config['phpstan']:
            return self.config['phpstan']['phpstan_path']
        return None

    def set_phpstan_path(self, path: str):
        """Set the PHPStan executable path and save to settings."""
        if 'phpstan' not in self.config:
            self.config['phpstan'] = {}
        self.config['phpstan']['phpstan_path'] = path
        self._save()

    def prompt_and_save_phpstan_path(self) -> str | None:
        """Prompt user for PHPStan path, validate it, and save to settings."""
        self.logger.info("\nPHPStan executable not found in PATH.")
        self.logger.info("Install with: composer require --dev phpstan/phpstan")
        self.logger.info("Or in the php/ subfolder: cd php && composer install")
        prompt_msg = "\nEnter path to phpstan executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        if not user_input:
            self.logger.info("Skipping phpstan analyze rule. Install PHPStan and configure later.")
            return None

        phpstan_path = Path(user_input)
        if not phpstan_path.exists():
            self.logger.error(f"Error: PHPStan executable not found at: {user_input}")
            return None

        self.set_phpstan_path(str(phpstan_path))
        self.logger.info(f"PHPStan path saved to {self.settings_file}")
        return str(phpstan_path)

    def get_php_cs_fixer_path(self) -> str | None:
        """Get the PHP-CS-Fixer executable path from settings."""
        if 'php_cs_fixer' in self.config and 'php_cs_fixer_path' in self.config['php_cs_fixer']:
            return self.config['php_cs_fixer']['php_cs_fixer_path']
        return None

    def set_php_cs_fixer_path(self, path: str):
        """Set the PHP-CS-Fixer executable path and save to settings."""
        if 'php_cs_fixer' not in self.config:
            self.config['php_cs_fixer'] = {}
        self.config['php_cs_fixer']['php_cs_fixer_path'] = path
        self._save()

    def prompt_and_save_php_cs_fixer_path(self) -> str | None:
        """Prompt user for PHP-CS-Fixer path, validate it, and save to settings."""
        self.logger.info("\nPHP-CS-Fixer executable not found in PATH.")
        self.logger.info("Install with: composer require --dev friendsofphp/php-cs-fixer")
        self.logger.info("Or in the php/ subfolder: cd php && composer install")
        prompt_msg = "\nEnter path to php-cs-fixer executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        if not user_input:
            self.logger.info("Skipping php_cs_fixer rule. Install PHP-CS-Fixer and configure later.")
            return None

        fixer_path = Path(user_input)
        if not fixer_path.exists():
            self.logger.error(f"Error: PHP-CS-Fixer executable not found at: {user_input}")
            return None

        self.set_php_cs_fixer_path(str(fixer_path))
        self.logger.info(f"PHP-CS-Fixer path saved to {self.settings_file}")
        return str(fixer_path)

    def get_dotnet_path(self) -> str | None:
        """Get the dotnet executable path from settings."""
        if 'dotnet' in self.config and 'dotnet_path' in self.config['dotnet']:
            return self.config['dotnet']['dotnet_path']
        return None

    def set_dotnet_path(self, path: str):
        """Set the dotnet executable path and save to settings."""
        if 'dotnet' not in self.config:
            self.config['dotnet'] = {}
        self.config['dotnet']['dotnet_path'] = path
        self._save()

    def prompt_and_save_dotnet_path(self) -> str | None:
        """Prompt user for dotnet path, validate it, and save to settings."""
        self.logger.info("\ndotnet executable not found in PATH.")
        self.logger.info("Please ensure .NET SDK is installed.")
        self.logger.info("Download from: https://dotnet.microsoft.com/download")
        prompt_msg = "\nEnter path to dotnet executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        if not user_input:
            self.logger.info("Skipping dotnet_analyze rule. Install .NET SDK and configure later.")
            return None

        dotnet_path = Path(user_input)
        if not dotnet_path.exists():
            self.logger.error(f"Error: dotnet executable not found at: {user_input}")
            return None

        self.set_dotnet_path(str(dotnet_path))
        self.logger.info(f"dotnet path saved to {self.settings_file}")
        return str(dotnet_path)

    def get_eslint_path(self) -> str | None:
        """Get the ESLint executable path from settings.

        Returns:
            Path to ESLint executable or None if not set
        """
        if 'eslint' in self.config and 'eslint_path' in self.config['eslint']:
            return self.config['eslint']['eslint_path']
        return None

    def set_eslint_path(self, path: str):
        """Set the ESLint executable path and save to settings.

        Args:
            path: Path to ESLint executable
        """
        if 'eslint' not in self.config:
            self.config['eslint'] = {}
        self.config['eslint']['eslint_path'] = path
        self._save()

    def prompt_and_save_eslint_path(self) -> str | None:
        """Prompt user for ESLint path, validate it, and save to settings.

        Returns:
            Validated ESLint path, or None if validation failed
        """
        self.logger.info("\nESLint executable not found in PATH.")
        self.logger.info("ESLint is a JavaScript/TypeScript linter.")
        self.logger.info("Install with: npm install -g eslint")
        self.logger.info("Or locally: npm install --save-dev eslint")
        prompt_msg = "\nEnter path to eslint executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        # If user pressed enter (empty input), skip
        if not user_input:
            self.logger.info("Skipping eslint analyze rule. Install ESLint and configure later.")
            return None

        # Validate user-provided path exists
        eslint_path = Path(user_input)
        if not eslint_path.exists():
            self.logger.error(f"Error: ESLint executable not found at: {user_input}")
            return None

        # Save and return
        self.set_eslint_path(str(eslint_path))
        self.logger.info(f"ESLint path saved to {self.settings_file}")
        return str(eslint_path)

    def get_svelte_check_path(self) -> str | None:
        """Get the svelte-check executable path from settings."""
        if 'svelte_check' in self.config and 'svelte_check_path' in self.config['svelte_check']:
            return self.config['svelte_check']['svelte_check_path']
        return None

    def set_svelte_check_path(self, path: str):
        """Set the svelte-check executable path and save to settings."""
        if 'svelte_check' not in self.config:
            self.config['svelte_check'] = {}
        self.config['svelte_check']['svelte_check_path'] = path
        self._save()

    def prompt_and_save_svelte_check_path(self) -> str | None:
        """Prompt user for svelte-check path, validate it, and save to settings."""
        self.logger.info("\nsvelte-check executable not found in PATH.")
        self.logger.info("svelte-check is a type checker for Svelte projects.")
        self.logger.info("Install with: npm install --save-dev svelte-check")
        prompt_msg = "\nEnter path to svelte-check executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        if not user_input:
            self.logger.info("Skipping svelte_check rule. Install svelte-check and configure later.")
            return None

        svelte_check_path = Path(user_input)
        if not svelte_check_path.exists():
            self.logger.error(f"Error: svelte-check executable not found at: {user_input}")
            return None

        self.set_svelte_check_path(str(svelte_check_path))
        self.logger.info(f"svelte-check path saved to {self.settings_file}")
        return str(svelte_check_path)

    def get_tsc_path(self) -> str | None:
        """Get the tsc executable path from settings."""
        if 'tsc' in self.config and 'tsc_path' in self.config['tsc']:
            return self.config['tsc']['tsc_path']
        return None

    def set_tsc_path(self, path: str):
        """Set the tsc executable path and save to settings."""
        if 'tsc' not in self.config:
            self.config['tsc'] = {}
        self.config['tsc']['tsc_path'] = path
        self._save()

    def prompt_and_save_tsc_path(self) -> str | None:
        """Prompt user for tsc path, validate it, and save to settings."""
        self.logger.info("\ntsc executable not found in PATH.")
        self.logger.info("TypeScript compiler is required for type checking.")
        self.logger.info("Install with: npm install --save-dev typescript")
        self.logger.info("Or globally: npm install -g typescript")
        prompt_msg = "\nEnter path to tsc executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        if not user_input:
            self.logger.info("Skipping tsc_analyze rule. Install TypeScript and configure later.")
            return None

        tsc_path = Path(user_input)
        if not tsc_path.exists():
            self.logger.error(f"Error: tsc executable not found at: {user_input}")
            return None

        self.set_tsc_path(str(tsc_path))
        self.logger.info(f"tsc path saved to {self.settings_file}")
        return str(tsc_path)

    def get_dart_lsp_mcp_path(self) -> str | None:
        """Get the dart-lsp-mcp path from settings."""
        if 'dart_lsp_mcp' in self.config and 'dart_lsp_mcp_path' in self.config['dart_lsp_mcp']:
            return self.config['dart_lsp_mcp']['dart_lsp_mcp_path']
        return None

    def set_dart_lsp_mcp_path(self, path: str):
        """Set the dart-lsp-mcp path and save to settings."""
        if 'dart_lsp_mcp' not in self.config:
            self.config['dart_lsp_mcp'] = {}
        self.config['dart_lsp_mcp']['dart_lsp_mcp_path'] = path
        self._save()

    def prompt_and_save_dart_lsp_mcp_path(self) -> str | None:
        """Prompt user for dart-lsp-mcp path, validate it, and save to settings."""
        self.logger.info("\ndart-lsp-mcp not found.")
        self.logger.info("Required for dart_unused_code and dart_missing_dispose analyzers.")
        self.logger.info("Install from: https://github.com/BenjaminKobjolke/dart-lsp-mcp")
        prompt_msg = "\nEnter path to dart-lsp-mcp directory (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        if not user_input:
            self.logger.info("Skipping dart-lsp-mcp dependent analyzers.")
            return None

        lsp_path = Path(user_input)
        if not lsp_path.exists():
            self.logger.error(f"Error: dart-lsp-mcp not found at: {user_input}")
            return None

        self.set_dart_lsp_mcp_path(str(lsp_path))
        self.logger.info(f"dart-lsp-mcp path saved to {self.settings_file}")
        return str(lsp_path)
