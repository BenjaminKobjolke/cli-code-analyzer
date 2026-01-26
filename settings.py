"""Settings management for the code analyzer."""
import configparser
from pathlib import Path

from pmd_downloader import download_pmd


class Settings:
    """Manages application settings stored in settings.ini"""

    def __init__(self, settings_file: str | None = None):
        """Initialize settings manager.

        Args:
            settings_file: Path to the settings INI file. If None, uses settings.ini
                          in the cli-code-analyzer directory.
        """
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
            print("\nDownloading PMD...")
            pmd_path = download_pmd()
            if not pmd_path:
                return None
            # Save and return
            self.set_pmd_path(str(pmd_path))
            print(f"PMD path saved to {self.settings_file}")
            return str(pmd_path)

        # Validate user-provided path exists
        pmd_path = Path(user_input)
        if not pmd_path.exists():
            print(f"Error: PMD executable not found at: {user_input}")
            return None

        # Save and return
        self.set_pmd_path(str(pmd_path))
        print(f"PMD path saved to {self.settings_file}")
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
        print("\nDart executable not found in PATH.")
        print("Please ensure Flutter/Dart SDK is installed.")
        print("Download from: https://docs.flutter.dev/get-started/install")
        prompt_msg = "\nEnter path to dart executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        # If user pressed enter (empty input), skip
        if not user_input:
            print("Skipping dart analyze rule. Install Dart SDK and configure later.")
            return None

        # Validate user-provided path exists
        dart_path = Path(user_input)
        if not dart_path.exists():
            print(f"Error: Dart executable not found at: {user_input}")
            return None

        # Save and return
        self.set_dart_path(str(dart_path))
        print(f"Dart path saved to {self.settings_file}")
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
        print("\nFlutter executable not found in PATH.")
        print("Please ensure Flutter SDK is installed.")
        print("Download from: https://docs.flutter.dev/get-started/install")
        prompt_msg = "\nEnter path to flutter executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        # If user pressed enter (empty input), skip
        if not user_input:
            print("Skipping flutter analyze rule. Install Flutter SDK and configure later.")
            return None

        # Validate user-provided path exists
        flutter_path = Path(user_input)
        if not flutter_path.exists():
            print(f"Error: Flutter executable not found at: {user_input}")
            return None

        # Save and return
        self.set_flutter_path(str(flutter_path))
        print(f"Flutter path saved to {self.settings_file}")
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
        print("\nRuff executable not found in PATH.")
        print("Ruff is a fast Python linter written in Rust.")
        print("Install with: pip install ruff")
        print("Or download from: https://docs.astral.sh/ruff/installation/")
        prompt_msg = "\nEnter path to ruff executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        # If user pressed enter (empty input), skip
        if not user_input:
            print("Skipping ruff analyze rule. Install Ruff and configure later.")
            return None

        # Validate user-provided path exists
        ruff_path = Path(user_input)
        if not ruff_path.exists():
            print(f"Error: Ruff executable not found at: {user_input}")
            return None

        # Save and return
        self.set_ruff_path(str(ruff_path))
        print(f"Ruff path saved to {self.settings_file}")
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
        print("\nPHPStan executable not found in PATH.")
        print("Install with: composer require --dev phpstan/phpstan")
        print("Or in the php/ subfolder: cd php && composer install")
        prompt_msg = "\nEnter path to phpstan executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        if not user_input:
            print("Skipping phpstan analyze rule. Install PHPStan and configure later.")
            return None

        phpstan_path = Path(user_input)
        if not phpstan_path.exists():
            print(f"Error: PHPStan executable not found at: {user_input}")
            return None

        self.set_phpstan_path(str(phpstan_path))
        print(f"PHPStan path saved to {self.settings_file}")
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
        print("\nPHP-CS-Fixer executable not found in PATH.")
        print("Install with: composer require --dev friendsofphp/php-cs-fixer")
        print("Or in the php/ subfolder: cd php && composer install")
        prompt_msg = "\nEnter path to php-cs-fixer executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        if not user_input:
            print("Skipping php_cs_fixer rule. Install PHP-CS-Fixer and configure later.")
            return None

        fixer_path = Path(user_input)
        if not fixer_path.exists():
            print(f"Error: PHP-CS-Fixer executable not found at: {user_input}")
            return None

        self.set_php_cs_fixer_path(str(fixer_path))
        print(f"PHP-CS-Fixer path saved to {self.settings_file}")
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
        print("\ndotnet executable not found in PATH.")
        print("Please ensure .NET SDK is installed.")
        print("Download from: https://dotnet.microsoft.com/download")
        prompt_msg = "\nEnter path to dotnet executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        if not user_input:
            print("Skipping dotnet_analyze rule. Install .NET SDK and configure later.")
            return None

        dotnet_path = Path(user_input)
        if not dotnet_path.exists():
            print(f"Error: dotnet executable not found at: {user_input}")
            return None

        self.set_dotnet_path(str(dotnet_path))
        print(f"dotnet path saved to {self.settings_file}")
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
        print("\nESLint executable not found in PATH.")
        print("ESLint is a JavaScript/TypeScript linter.")
        print("Install with: npm install -g eslint")
        print("Or locally: npm install --save-dev eslint")
        prompt_msg = "\nEnter path to eslint executable (or press Enter to skip): "
        user_input = input(prompt_msg).strip()

        # If user pressed enter (empty input), skip
        if not user_input:
            print("Skipping eslint analyze rule. Install ESLint and configure later.")
            return None

        # Validate user-provided path exists
        eslint_path = Path(user_input)
        if not eslint_path.exists():
            print(f"Error: ESLint executable not found at: {user_input}")
            return None

        # Save and return
        self.set_eslint_path(str(eslint_path))
        print(f"ESLint path saved to {self.settings_file}")
        return str(eslint_path)
