"""Settings management for the code analyzer."""
import configparser
from pathlib import Path
from typing import Optional
from pmd_downloader import download_pmd, get_pmd_install_path


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

    def get_pmd_path(self) -> Optional[str]:
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

    def prompt_and_save_pmd_path(self) -> Optional[str]:
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
