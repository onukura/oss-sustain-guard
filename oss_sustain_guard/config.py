"""
Configuration management for OSS Sustain Guard.

Loads excluded packages from:
1. .oss-sustain-guard.toml (local config)
2. pyproject.toml (project-level config)
"""

import os
import ssl

try:
    import tomllib  # ty:ignore[unresolved-import]
except ImportError:  # pragma: no cover - fallback for Python < 3.11
    import tomli as tomllib
from pathlib import Path
from typing import Union

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# PROJECT_ROOT defaults to the current working directory for config discovery
PROJECT_ROOT = Path.cwd()

# Global configuration for SSL verification
# Default: None (uses environment variable or default True)
# Can be set by CLI --ca-cert, --insecure, or environment variable
VERIFY_SSL: Union[bool, str, None] = None

# Cache configuration
# Default cache directory: ~/.cache/oss-sustain-guard
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "oss-sustain-guard"
# Default TTL: 7 days (in seconds)
DEFAULT_CACHE_TTL = 7 * 24 * 60 * 60

# Global cache settings (can be overridden)
_CACHE_DIR: Path | None = None
_CACHE_TTL: int | None = None

# Scan depth configuration for GitHub/GitLab API sampling
# Options: "shallow", "default", "deep"
_SCAN_DEPTH: str = "default"

# Days to look back for temporal filtering (None = no time limit)
_DAYS_LOOKBACK: int | None = None

# Scan depth configuration for GitHub API sampling
# Options: "shallow", "default", "deep"
_SCAN_DEPTH: str = "default"

# Days to look back for temporal filtering (None = no time limit)
_DAYS_LOOKBACK: int | None = None


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


def get_excluded_users() -> list[str]:
    """
    Load excluded users (bots) from configuration files.

    Priority:
    1. .oss-sustain-guard.toml (local config, highest priority)
    2. pyproject.toml (project-level config, fallback)

    This allows users to configure which accounts should be treated as bots.
    Useful for CI/CD accounts or internal automation accounts not in the default list.

    Example in .oss-sustain-guard.toml:
        [tool.oss-sustain-guard]
        exclude-users = ["my-ci-user", "release-bot"]

    Returns:
        List of excluded user logins.
    """
    excluded = []

    # Try .oss-sustain-guard.toml first (highest priority)
    local_config_path = PROJECT_ROOT / ".oss-sustain-guard.toml"
    if local_config_path.exists():
        config = load_config_file(local_config_path)
        # Support both "exclude-users" (TOML style) and "exclude_users" (Python style)
        excluded.extend(
            config.get("tool", {}).get("oss-sustain-guard", {}).get("exclude-users", [])
        )
        excluded.extend(
            config.get("tool", {}).get("oss-sustain-guard", {}).get("exclude_users", [])
        )

    # Try pyproject.toml (fallback)
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if pyproject_path.exists() and not excluded:
        config = load_config_file(pyproject_path)
        # Support both "exclude-users" (TOML style) and "exclude_users" (Python style)
        excluded.extend(
            config.get("tool", {}).get("oss-sustain-guard", {}).get("exclude-users", [])
        )
        excluded.extend(
            config.get("tool", {}).get("oss-sustain-guard", {}).get("exclude_users", [])
        )

    return list(set(excluded))  # Remove duplicates


def get_default_exclusion_patterns() -> set[str]:
    """
    Get default directory exclusion patterns for recursive scanning.

    These are common build outputs, caches, and virtual environments
    that should typically be excluded from scanning.

    Returns:
        Set of directory names to exclude.
    """
    return {
        # Node.js
        "node_modules",
        ".npm",
        ".yarn",
        # Python
        "__pycache__",
        "venv",
        ".venv",
        "env",
        ".env",
        ".virtualenv",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "*.egg-info",
        # Rust
        "target",
        # Go
        "vendor",
        # Java/Kotlin/Scala
        ".gradle",
        ".m2",
        ".ivy2",
        # PHP (uses same "vendor" as Go)
        # Ruby
        ".bundle",
        # .NET/C#
        "bin",
        "obj",
        "packages",
        # Build outputs (general)
        "build",
        "dist",
        "out",
        ".output",
        # Version control
        ".git",
        ".svn",
        ".hg",
        ".bzr",
        # IDEs
        ".idea",
        ".vscode",
        ".vs",
        # OS
        ".DS_Store",
        "Thumbs.db",
    }


def get_exclusion_config() -> dict:
    """
    Load exclusion configuration from config files.

    Returns:
        Dictionary with exclusion settings.
    """
    config_defaults = {
        "patterns": [],
        "use_defaults": True,
        "use_gitignore": True,
    }

    # Try .oss-sustain-guard.toml first (highest priority)
    local_config_path = PROJECT_ROOT / ".oss-sustain-guard.toml"
    if local_config_path.exists():
        config = load_config_file(local_config_path)
        exclude_config = (
            config.get("tool", {}).get("oss-sustain-guard", {}).get("exclude-dirs", {})
        )
        if exclude_config:
            return {**config_defaults, **exclude_config}

    # Try pyproject.toml (fallback)
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if pyproject_path.exists():
        config = load_config_file(pyproject_path)
        exclude_config = (
            config.get("tool", {}).get("oss-sustain-guard", {}).get("exclude-dirs", {})
        )
        if exclude_config:
            return {**config_defaults, **exclude_config}

    return config_defaults


def parse_gitignore(gitignore_path: Path) -> set[str]:
    """
    Parse .gitignore file and extract directory patterns.

    This is a simple parser that extracts directory names.
    It does not support complex glob patterns or negation.

    Args:
        gitignore_path: Path to .gitignore file.

    Returns:
        Set of directory names to exclude.
    """
    if not gitignore_path.exists():
        return set()

    patterns = set()
    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                # Skip negations
                if line.startswith("!"):
                    continue

                # Extract directory patterns
                # Remove trailing slashes
                pattern = line.rstrip("/")
                # Remove leading slashes and wildcards for simple matching
                pattern = pattern.lstrip("/")

                # Only add simple directory names (no path separators, no complex globs)
                if "/" not in pattern and "*" not in pattern:
                    patterns.add(pattern)
                # Also handle patterns like "*/dirname" which means any dirname
                elif pattern.startswith("*/"):
                    dir_name = pattern[2:]
                    if "/" not in dir_name and "*" not in dir_name:
                        patterns.add(dir_name)

    except Exception:
        # Silently ignore errors parsing .gitignore
        pass

    return patterns


def get_exclusion_patterns(directory: Path | None = None) -> set[str]:
    """
    Get combined exclusion patterns from defaults, config, and .gitignore.

    Args:
        directory: Directory to check for .gitignore (defaults to PROJECT_ROOT).

    Returns:
        Set of directory names to exclude during recursive scanning.
    """
    if directory is None:
        directory = PROJECT_ROOT

    exclusion_config = get_exclusion_config()
    patterns = set()

    # Add default patterns if enabled
    if exclusion_config.get("use_defaults", True):
        patterns.update(get_default_exclusion_patterns())

    # Add custom patterns from config
    custom_patterns = exclusion_config.get("patterns", [])
    patterns.update(custom_patterns)

    # Add patterns from .gitignore if enabled
    if exclusion_config.get("use_gitignore", True):
        gitignore_path = Path(directory) / ".gitignore"
        patterns.update(parse_gitignore(gitignore_path))

    return patterns


def set_verify_ssl(verify: Union[bool, str, None]) -> None:
    """
    Set the SSL verification setting globally.

    Args:
        verify: Whether to verify SSL certificates (bool), path to CA cert file (str), or None to use default.
    """
    global VERIFY_SSL
    VERIFY_SSL = verify


def get_verify_ssl() -> ssl.SSLContext | bool:
    """
    Get the current SSL verification setting.

    Priority:
    1. Explicitly set value via set_verify_ssl() (e.g., from CLI --ca-cert)
    2. OSS_SUSTAIN_GUARD_CA_CERT environment variable
    3. Default: True

    Returns:
        SSL verification setting: True (verify), False (no verify), or str (CA cert file path).
    """
    # Return explicitly set value (highest priority)
    if VERIFY_SSL is not None:
        if isinstance(VERIFY_SSL, bool):
            return VERIFY_SSL
        if isinstance(VERIFY_SSL, str):
            return ssl.create_default_context(cafile=VERIFY_SSL)
        if isinstance(VERIFY_SSL, ssl.SSLContext):
            return VERIFY_SSL
        raise ValueError(f"Invalid SSL verification setting: {VERIFY_SSL}")

    # Check environment variable
    env_ca_cert = os.getenv("OSS_SUSTAIN_GUARD_CA_CERT")
    if isinstance(env_ca_cert, str):
        if os.path.isdir(env_ca_cert):
            return ssl.create_default_context(capath=env_ca_cert)
        return ssl.create_default_context(cafile=env_ca_cert)

    # Default: verify SSL
    return True


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


def set_scan_depth(depth: str) -> None:
    """Set the scan depth for data collection.

    Args:
        depth: One of "shallow", "default", "deep", "very_deep"

    Raises:
        ValueError: If depth is not a valid option
    """
    global _SCAN_DEPTH
    valid_depths = {"shallow", "default", "deep", "very_deep"}
    if depth not in valid_depths:
        raise ValueError(
            f"Invalid scan depth: {depth}. Must be one of: {', '.join(sorted(valid_depths))}"
        )
    _SCAN_DEPTH = depth


def get_scan_depth() -> str:
    """Get the configured scan depth (shallow, default, or deep)."""
    return _SCAN_DEPTH


def set_days_lookback(days: int | None) -> None:
    """Set the number of days to look back for temporal filtering.

    Args:
        days: Number of days to look back, or None for no time limit

    Raises:
        ValueError: If days is negative
    """
    global _DAYS_LOOKBACK
    if days is not None and days < 0:
        raise ValueError(f"Days lookback must be non-negative, got {days}")
    _DAYS_LOOKBACK = days


def get_days_lookback() -> int | None:
    """Get the configured days lookback value (None = no time limit)."""
    return _DAYS_LOOKBACK


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


def get_output_style() -> str:
    """
    Get the default output style from configuration.

    Priority:
    1. .oss-sustain-guard.toml config
    2. pyproject.toml config
    3. Default: "normal"

    Returns:
        Output style: "compact", "normal", or "detail".
    """
    # Try .oss-sustain-guard.toml first
    local_config_path = PROJECT_ROOT / ".oss-sustain-guard.toml"
    if local_config_path.exists():
        config = load_config_file(local_config_path)
        output_style = (
            config.get("tool", {}).get("oss-sustain-guard", {}).get("output_style")
        )
        if output_style in ["compact", "normal", "detail"]:
            return output_style

    # Try pyproject.toml (fallback)
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if pyproject_path.exists():
        config = load_config_file(pyproject_path)
        output_style = (
            config.get("tool", {}).get("oss-sustain-guard", {}).get("output_style")
        )
        if output_style in ["compact", "normal", "detail"]:
            return output_style

    # Default
    return "normal"


def _extract_profile_config(config: dict) -> dict[str, dict[str, object]]:
    """
    Extract scoring profile configuration from a TOML config dict.

    Supports:
    - [tool.oss-sustain-guard.profiles] (pyproject.toml or .oss-sustain-guard.toml)
    - [profiles] (standalone profile file)
    """
    tool_profiles = (
        config.get("tool", {}).get("oss-sustain-guard", {}).get("profiles", {})
    )
    if tool_profiles:
        return tool_profiles
    return config.get("profiles", {})


def load_profile_config(
    profile_path: Path | None = None,
) -> dict[str, dict[str, object]]:
    """
    Load scoring profile configuration from config files.

    Priority:
    1. Explicit profile_path if provided
    2. .oss-sustain-guard.toml config
    3. pyproject.toml config

    Returns:
        Dictionary of profile configurations (may be empty).
    """
    if profile_path is not None:
        if not profile_path.exists():
            raise ValueError(f"Profile file not found: {profile_path}")
        config = load_config_file(profile_path)
        profiles = _extract_profile_config(config)
        if not profiles:
            raise ValueError(
                f"No profiles found in {profile_path}. "
                "Expected [profiles.<name>] tables."
            )
        return profiles

    local_config_path = PROJECT_ROOT / ".oss-sustain-guard.toml"
    if local_config_path.exists():
        config = load_config_file(local_config_path)
        profiles = _extract_profile_config(config)
        if profiles:
            return profiles

    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if pyproject_path.exists():
        config = load_config_file(pyproject_path)
        profiles = _extract_profile_config(config)
        if profiles:
            return profiles

    return {}


def is_verbose_enabled() -> bool:
    """
    Check if verbose logging is enabled by default in configuration.

    Priority:
    1. .oss-sustain-guard.toml config
    2. pyproject.toml config
    3. Default: False

    Returns:
        Whether verbose logging is enabled by default.
    """
    # Try .oss-sustain-guard.toml first
    local_config_path = PROJECT_ROOT / ".oss-sustain-guard.toml"
    if local_config_path.exists():
        config = load_config_file(local_config_path)
        verbose = config.get("tool", {}).get("oss-sustain-guard", {}).get("verbose")
        if verbose is not None:
            return bool(verbose)

    # Try pyproject.toml (fallback)
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if pyproject_path.exists():
        config = load_config_file(pyproject_path)
        verbose = config.get("tool", {}).get("oss-sustain-guard", {}).get("verbose")
        if verbose is not None:
            return bool(verbose)

    # Default: disabled
    return False


def get_lfx_config() -> dict:
    """
    Load LFX Insights integration configuration.

    Returns:
        Dictionary with LFX configuration:
        - enabled: bool (default: True)
        - badges: list of badge types (default: ["health-score", "active-contributors"])
        - project_map: dict mapping package names to LFX project slugs (default: {})

    Priority:
    1. .oss-sustain-guard.toml
    2. pyproject.toml
    3. Default values
    """
    default_config = {
        "enabled": True,
        "badges": ["health-score", "active-contributors"],
        "project_map": {},
    }

    # Try .oss-sustain-guard.toml first
    local_config_path = PROJECT_ROOT / ".oss-sustain-guard.toml"
    if local_config_path.exists():
        config = load_config_file(local_config_path)
        lfx_config = (
            config.get("tool", {})
            .get("oss-sustain-guard", {})
            .get("integrations", {})
            .get("lfx", {})
        )
        if lfx_config:
            return {**default_config, **lfx_config}

    # Try pyproject.toml (fallback)
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if pyproject_path.exists():
        config = load_config_file(pyproject_path)
        lfx_config = (
            config.get("tool", {})
            .get("oss-sustain-guard", {})
            .get("integrations", {})
            .get("lfx", {})
        )
        if lfx_config:
            return {**default_config, **lfx_config}

    return default_config
