"""
Configuration management for OSS Sustain Guard.

Loads excluded packages from:
1. .oss-sustain-guard.toml (local config)
2. pyproject.toml (project-level config)
"""

import os
import tomllib
from pathlib import Path

# project_root is the parent directory of oss_sustain_guard/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Global configuration for SSL verification
# Default: True (verify SSL certificates)
# Can be set to False by CLI --insecure flag
VERIFY_SSL = True

# Cache configuration
# Default cache directory: ~/.cache/oss-sustain-guard
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "oss-sustain-guard"
# Default TTL: 7 days (in seconds)
DEFAULT_CACHE_TTL = 7 * 24 * 60 * 60

# Global cache settings (can be overridden)
_CACHE_DIR: Path | None = None
_CACHE_TTL: int | None = None


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


def get_cache_dir() -> Path:
    """
    Get the cache directory path.

    Priority:
    1. Explicitly set value via set_cache_dir()
    2. OSS_SUSTAIN_GUARD_CACHE_DIR environment variable
    3. .oss-sustain-guard.toml config
    4. Default: ~/.cache/oss-sustain-guard

    Returns:
        Path to the cache directory.
    """
    global _CACHE_DIR

    # Return explicitly set value
    if _CACHE_DIR is not None:
        return _CACHE_DIR

    # Check environment variable
    env_cache_dir = os.getenv("OSS_SUSTAIN_GUARD_CACHE_DIR")
    if env_cache_dir:
        return Path(env_cache_dir).expanduser()

    # Check config files
    local_config_path = PROJECT_ROOT / ".oss-sustain-guard.toml"
    if local_config_path.exists():
        config = load_config_file(local_config_path)
        cache_config = (
            config.get("tool", {}).get("oss-sustain-guard", {}).get("cache", {})
        )
        if "directory" in cache_config:
            return Path(cache_config["directory"]).expanduser()

    # Return default
    return DEFAULT_CACHE_DIR


def set_cache_dir(path: Path | str) -> None:
    """
    Set the cache directory path explicitly.

    Args:
        path: Path to the cache directory.
    """
    global _CACHE_DIR
    _CACHE_DIR = Path(path).expanduser()


def get_cache_ttl() -> int:
    """
    Get the cache TTL (Time To Live) in seconds.

    Priority:
    1. Explicitly set value via set_cache_ttl()
    2. OSS_SUSTAIN_GUARD_CACHE_TTL environment variable
    3. .oss-sustain-guard.toml config
    4. Default: 604800 (7 days)

    Returns:
        TTL in seconds.
    """
    global _CACHE_TTL

    # Return explicitly set value
    if _CACHE_TTL is not None:
        return _CACHE_TTL

    # Check environment variable
    env_cache_ttl = os.getenv("OSS_SUSTAIN_GUARD_CACHE_TTL")
    if env_cache_ttl:
        try:
            return int(env_cache_ttl)
        except ValueError:
            pass

    # Check config files
    local_config_path = PROJECT_ROOT / ".oss-sustain-guard.toml"
    if local_config_path.exists():
        config = load_config_file(local_config_path)
        cache_config = (
            config.get("tool", {}).get("oss-sustain-guard", {}).get("cache", {})
        )
        if "ttl_seconds" in cache_config:
            return int(cache_config["ttl_seconds"])

    # Return default
    return DEFAULT_CACHE_TTL


def set_cache_ttl(seconds: int) -> None:
    """
    Set the cache TTL (Time To Live) explicitly.

    Args:
        seconds: TTL in seconds.
    """
    global _CACHE_TTL
    _CACHE_TTL = seconds


def is_cache_enabled() -> bool:
    """
    Check if cache is enabled.

    Priority:
    1. .oss-sustain-guard.toml config
    2. Default: True

    Returns:
        Whether cache is enabled.
    """
    # Check config files
    local_config_path = PROJECT_ROOT / ".oss-sustain-guard.toml"
    if local_config_path.exists():
        config = load_config_file(local_config_path)
        cache_config = (
            config.get("tool", {}).get("oss-sustain-guard", {}).get("cache", {})
        )
        if "enabled" in cache_config:
            return bool(cache_config["enabled"])

    # Default: enabled
    return True
