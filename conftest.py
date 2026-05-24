"""Make the project root importable for tests without installing the package."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
