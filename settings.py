"""Settings management for the code analyzer."""
import configparser
from pathlib import Path

from pmd_downloader import download_pmd


class Settings:
    """Manages application settings stored in settings.ini"""

    def __init__(self, settings_file: str = "settings.ini"):
        """Initialize settings manager.

        Args:
            settings_file: Path to the settings INI file
        """
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
