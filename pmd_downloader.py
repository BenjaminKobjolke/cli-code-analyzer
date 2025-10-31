"""PMD downloader and installer."""
import urllib.request
import zipfile
import shutil
from pathlib import Path
from typing import Optional


PMD_VERSION = "7.17.0"
PMD_DOWNLOAD_URL = f"https://github.com/pmd/pmd/releases/download/pmd_releases%2F{PMD_VERSION}/pmd-dist-{PMD_VERSION}-bin.zip"
PMD_INSTALL_DIR = Path("bin")
PMD_EXTRACTED_DIR = f"pmd-bin-{PMD_VERSION}"


def get_pmd_install_path() -> Path:
    """Get the expected path to the installed PMD executable.

    Returns:
        Path to pmd.bat
    """
    return PMD_INSTALL_DIR / PMD_EXTRACTED_DIR / "bin" / "pmd.bat"


def download_pmd() -> Optional[Path]:
    """Download and extract PMD from GitHub.

    Returns:
        Path to pmd.bat if successful, None otherwise
    """
    try:
        # Create bin directory if it doesn't exist
        PMD_INSTALL_DIR.mkdir(parents=True, exist_ok=True)

        # Download PMD
        print(f"Downloading PMD {PMD_VERSION}...")
        zip_path = PMD_INSTALL_DIR / f"pmd-{PMD_VERSION}.zip"

        # Download with progress
        urllib.request.urlretrieve(PMD_DOWNLOAD_URL, zip_path)
        print("Download complete")

        # Extract ZIP
        print(f"Extracting to {PMD_INSTALL_DIR}/...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(PMD_INSTALL_DIR)

        # Clean up ZIP file
        zip_path.unlink()
        print("Extraction complete")

        # Verify installation
        pmd_path = get_pmd_install_path()
        if pmd_path.exists():
            print(f"PMD installed successfully at: {pmd_path}")
            return pmd_path
        else:
            print(f"Error: PMD executable not found at expected path: {pmd_path}")
            return None

    except Exception as e:
        print(f"Error downloading/extracting PMD: {e}")
        return None


def is_pmd_installed() -> bool:
    """Check if PMD is already installed.

    Returns:
        True if PMD is installed, False otherwise
    """
    return get_pmd_install_path().exists()
