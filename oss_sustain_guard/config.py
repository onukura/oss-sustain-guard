"""
Configuration management for OSS Sustain Guard.

Loads excluded packages from:
1. .oss-sustain-guard.toml (local config)
2. pyproject.toml (project-level config)
"""

import tomllib
from pathlib import Path

# project_root is the parent directory of oss_sustain_guard/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Global configuration for SSL verification
# Default: True (verify SSL certificates)
# Can be set to False by CLI --insecure flag
VERIFY_SSL = True


def load_config_file(config_path: Path) -> dict:
    """Load a TOML configuration file."""
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        raise ValueError(f"Failed to load config from {config_path}: {e}") from e


def get_excluded_packages() -> list[str]:
    """
    Load excluded packages from configuration files.

    Priority:
    1. .oss-sustain-guard.toml (local config, highest priority)
    2. pyproject.toml (project-level config, fallback)

    Returns:
        List of excluded package names.
    """
    excluded = []

    # Try .oss-sustain-guard.toml first (highest priority)
    local_config_path = PROJECT_ROOT / ".oss-sustain-guard.toml"
    if local_config_path.exists():
        config = load_config_file(local_config_path)
        excluded.extend(
            config.get("tool", {}).get("oss-sustain-guard", {}).get("exclude", [])
        )

    # Try pyproject.toml (fallback)
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if pyproject_path.exists() and not excluded:
        config = load_config_file(pyproject_path)
        excluded.extend(
            config.get("tool", {}).get("oss-sustain-guard", {}).get("exclude", [])
        )

    return list(set(excluded))  # Remove duplicates


def is_package_excluded(package_name: str) -> bool:
    """
    Check if a package is in the excluded list.

    Args:
        package_name: Name of the package to check.

    Returns:
        True if the package is excluded, False otherwise.
    """
    excluded = get_excluded_packages()
    return package_name.lower() in [pkg.lower() for pkg in excluded]


def set_verify_ssl(verify: bool) -> None:
    """
    Set the SSL verification setting globally.

    Args:
        verify: Whether to verify SSL certificates.
    """
    global VERIFY_SSL
    VERIFY_SSL = verify


def get_verify_ssl() -> bool:
    """
    Get the current SSL verification setting.

    Returns:
        Whether SSL verification is enabled.
    """
    return VERIFY_SSL
