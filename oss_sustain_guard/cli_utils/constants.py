"""Shared constants for CLI commands."""

from pathlib import Path

from rich.console import Console

# Schema version for cached data compatibility
ANALYSIS_VERSION = "1.5"

# project_root is the parent directory of oss_sustain_guard/
project_root = Path(__file__).resolve().parent.parent.parent
LATEST_DIR = project_root / "data" / "latest"

# Shared console instance
console = Console()
