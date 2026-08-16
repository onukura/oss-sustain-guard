"""
Tests for the configuration module.
"""

import ssl
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.config import (
    get_cache_dir,
    get_cache_ttl,
    get_excluded_packages,
    get_excluded_users,
    get_output_style,
    get_verify_ssl,
    is_cache_enabled,
    is_package_excluded,
    is_verbose_enabled,
    load_profile_config,
    set_cache_dir,
    set_cache_ttl,
    set_verify_ssl,
)


@pytest.fixture
def temp_project_root(monkeypatch):
    """Create a temporary project root for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Patch PROJECT_ROOT
        import oss_sustain_guard.config

        original_root = oss_sustain_guard.config.PROJECT_ROOT
        oss_sustain_guard.config.PROJECT_ROOT = tmpdir_path

        yield tmpdir_path

        # Restore
        oss_sustain_guard.config.PROJECT_ROOT = original_root


def test_get_excluded_packages_from_local_config(temp_project_root):
    """Test loading excluded packages from .oss-sustain-guard.toml."""
    config_file = temp_project_root / ".oss-sustain-guard.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard]
exclude = ["flask", "django"]
"""
    )

    excluded = get_excluded_packages()
    assert "flask" in excluded
    assert "django" in excluded


def test_get_excluded_packages_from_pyproject(temp_project_root):
    """Test loading excluded packages from pyproject.toml."""
    config_file = temp_project_root / "pyproject.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard]
exclude = ["requests", "numpy"]
"""
    )

    excluded = get_excluded_packages()
    assert "requests" in excluded
    assert "numpy" in excluded


def test_local_config_takes_priority(temp_project_root):
    """Test that .oss-sustain-guard.toml takes priority over pyproject.toml."""
    # Create pyproject.toml
    pyproject = temp_project_root / "pyproject.toml"
    pyproject.write_text(
        """
[tool.oss-sustain-guard]
exclude = ["requests"]
"""
    )

    # Create local config (should take priority)
    local_config = temp_project_root / ".oss-sustain-guard.toml"
    local_config.write_text(
        """
[tool.oss-sustain-guard]
exclude = ["flask"]
"""
    )

    excluded = get_excluded_packages()
    assert "flask" in excluded
    # pyproject.toml should be ignored when local config exists
    assert "requests" not in excluded


def test_is_package_excluded_case_insensitive(temp_project_root):
    """Test that package exclusion check is case-insensitive."""
    config_file = temp_project_root / ".oss-sustain-guard.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard]
exclude = ["Flask", "DJANGO"]
"""
    )

    assert is_package_excluded("flask")
    assert is_package_excluded("FLASK")
    assert is_package_excluded("Flask")
    assert is_package_excluded("django")
    assert is_package_excluded("DJANGO")
    assert is_package_excluded("Django")


def test_is_package_excluded_returns_false_for_non_excluded():
    """Test that non-excluded packages return False."""
    # With empty config
    assert not is_package_excluded("some-unknown-package")


def test_get_excluded_packages_empty_config(temp_project_root):
    """Test that empty config returns empty list."""
    excluded = get_excluded_packages()
    assert excluded == []


def test_get_excluded_packages_missing_files(temp_project_root):
    """Test that missing files return empty list."""
    # No config files created
    excluded = get_excluded_packages()
    assert excluded == []


def test_get_cache_dir_default():
    """Test default cache directory."""
    cache_dir = get_cache_dir()
    assert cache_dir == Path.home() / ".cache" / "oss-sustain-guard"


def test_get_cache_dir_from_env(monkeypatch, tmp_path):
    """Test cache directory from environment variable."""
    custom_dir = tmp_path / "custom_cache"
    monkeypatch.setenv("OSS_SUSTAIN_GUARD_CACHE_DIR", str(custom_dir))

    # Reset cached value
    import oss_sustain_guard.config

    oss_sustain_guard.config._CACHE_DIR = None

    cache_dir = get_cache_dir()
    assert cache_dir == custom_dir


def test_get_cache_dir_from_config(temp_project_root):
    """Test cache directory from config file."""
    config_file = temp_project_root / ".oss-sustain-guard.toml"
    custom_dir = temp_project_root / "my_cache"
    # Use POSIX path format to avoid Windows backslash escaping issues in TOML
    config_file.write_text(
        f"""
[tool.oss-sustain-guard.cache]
directory = "{custom_dir.as_posix()}"
"""
    )

    # Reset cached value
    import oss_sustain_guard.config

    oss_sustain_guard.config._CACHE_DIR = None

    cache_dir = get_cache_dir()
    assert cache_dir == custom_dir


def test_set_cache_dir(tmp_path):
    """Test setting cache directory explicitly."""
    custom_dir = tmp_path / "custom_cache"
    set_cache_dir(custom_dir)

    cache_dir = get_cache_dir()
    assert cache_dir == custom_dir


def test_get_cache_ttl_default():
    """Test default cache TTL."""
    ttl = get_cache_ttl()
    assert ttl == 7 * 24 * 60 * 60  # 7 days


def test_get_cache_ttl_from_env(monkeypatch):
    """Test cache TTL from environment variable."""
    monkeypatch.setenv("OSS_SUSTAIN_GUARD_CACHE_TTL", "86400")  # 1 day

    # Reset cached value
    import oss_sustain_guard.config

    oss_sustain_guard.config._CACHE_TTL = None

    ttl = get_cache_ttl()
    assert ttl == 86400


def test_get_cache_ttl_from_config(temp_project_root):
    """Test cache TTL from config file."""
    config_file = temp_project_root / ".oss-sustain-guard.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard.cache]
ttl_seconds = 3600
"""
    )

    # Reset cached value
    import oss_sustain_guard.config

    oss_sustain_guard.config._CACHE_TTL = None

    ttl = get_cache_ttl()
    assert ttl == 3600


def test_set_cache_ttl():
    """Test setting cache TTL explicitly."""
    set_cache_ttl(1800)

    ttl = get_cache_ttl()
    assert ttl == 1800


def test_is_cache_enabled_default():
    """Test cache is enabled by default."""
    assert is_cache_enabled() is True


def test_is_cache_enabled_from_config(temp_project_root):
    """Test cache enabled setting from config file."""
    config_file = temp_project_root / ".oss-sustain-guard.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard.cache]
enabled = false
"""
    )

    assert is_cache_enabled() is False


def test_get_output_style_default():
    """Test default output style is 'normal'."""
    assert get_output_style() == "normal"


def test_get_output_style_from_local_config(temp_project_root):
    """Test loading output style from .oss-sustain-guard.toml."""
    config_file = temp_project_root / ".oss-sustain-guard.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard]
output_style = "compact"
"""
    )

    assert get_output_style() == "compact"


def test_get_output_style_from_pyproject(temp_project_root):
    """Test loading output style from pyproject.toml."""
    config_file = temp_project_root / "pyproject.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard]
output_style = "detail"
"""
    )

    assert get_output_style() == "detail"


def test_get_output_style_invalid_falls_back_to_default(temp_project_root):
    """Test invalid output style falls back to 'normal'."""
    config_file = temp_project_root / ".oss-sustain-guard.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard]
output_style = "invalid"
"""
    )

    assert get_output_style() == "normal"


def test_is_verbose_enabled_default():
    """Test default verbose is False."""
    assert is_verbose_enabled() is False


def test_is_verbose_enabled_from_local_config(temp_project_root):
    """Test loading verbose from .oss-sustain-guard.toml."""
    config_file = temp_project_root / ".oss-sustain-guard.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard]
verbose = true
"""
    )

    assert is_verbose_enabled() is True


def test_is_verbose_enabled_from_pyproject(temp_project_root):
    """Test loading verbose from pyproject.toml."""
    config_file = temp_project_root / "pyproject.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard]
verbose = false
"""
    )

    assert is_verbose_enabled() is False


def test_load_profile_config_from_local_config(temp_project_root):
    """Test loading profile config from .oss-sustain-guard.toml."""
    config_file = temp_project_root / ".oss-sustain-guard.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard.profiles.custom]
name = "Custom"
description = "Custom profile"

[tool.oss-sustain-guard.profiles.custom.weights]
"Contributor Redundancy" = 1
"""
    )

    profiles = load_profile_config()
    assert "custom" in profiles
    custom_profile = profiles.get("custom")
    assert isinstance(custom_profile, dict)
    assert custom_profile.get("name") == "Custom"
    weights = custom_profile.get("weights")
    assert isinstance(weights, dict)
    assert "Contributor Redundancy" in weights
    assert weights["Contributor Redundancy"] == 1  # type: ignore


def test_load_profile_config_from_profile_file(tmp_path):
    """Test loading profile config from explicit profile file."""
    profile_file = tmp_path / "profiles.toml"
    profile_file.write_text(
        """
[profiles.custom_profile]
name = "Custom Profile"

[profiles.custom_profile.weights]
"Contributor Redundancy" = 2
"""
    )

    profiles = load_profile_config(profile_file)
    assert "custom_profile" in profiles
    custom_profile = profiles.get("custom_profile")
    assert isinstance(custom_profile, dict)
    weights = custom_profile.get("weights")
    assert isinstance(weights, dict)
    assert "Contributor Redundancy" in weights
    assert weights["Contributor Redundancy"] == 2  # type: ignore


def test_load_profile_config_missing_profiles_raises(tmp_path):
    """Test missing profiles in explicit profile file raises."""
    profile_file = tmp_path / "profiles.toml"
    profile_file.write_text(
        """
[tool.oss-sustain-guard]
output_style = "compact"
"""
    )

    with pytest.raises(ValueError, match="No profiles found"):
        load_profile_config(profile_file)


def test_get_verify_ssl_default(monkeypatch):
    """Test get_verify_ssl returns True by default."""
    monkeypatch.delenv("OSS_SUSTAIN_GUARD_CA_CERT", raising=False)
    set_verify_ssl(None)  # Reset to default
    assert get_verify_ssl() is True


def test_set_verify_ssl_with_bool():
    """Test set_verify_ssl with boolean value."""
    set_verify_ssl(False)
    assert get_verify_ssl() is False

    set_verify_ssl(True)
    assert get_verify_ssl() is True


def test_set_verify_ssl_with_cert_path(tmp_path):
    """Test set_verify_ssl with certificate file path."""
    cert_path = tmp_path / "custom-ca.crt"
    cert_path.write_text("dummy cert")
    set_verify_ssl(str(cert_path))

    with patch("ssl.create_default_context") as mock_create_context:
        mock_context = MagicMock(spec=ssl.SSLContext)
        mock_create_context.return_value = mock_context

        result = get_verify_ssl()
        assert result is mock_context
        mock_create_context.assert_called_once_with(cafile=str(cert_path))


def test_get_verify_ssl_from_env(monkeypatch, tmp_path):
    """Test get_verify_ssl respects OSS_SUSTAIN_GUARD_CA_CERT environment variable."""
    set_verify_ssl(None)  # Reset to use env var
    cert_path = tmp_path / "test-ca.crt"
    cert_path.write_text("dummy cert")

    monkeypatch.setenv("OSS_SUSTAIN_GUARD_CA_CERT", str(cert_path))

    with patch("ssl.create_default_context") as mock_create_context:
        mock_context = MagicMock(spec=ssl.SSLContext)
        mock_create_context.return_value = mock_context

        result = get_verify_ssl()
        assert result is mock_context
        mock_create_context.assert_called_once_with(cafile=str(cert_path))


def test_get_verify_ssl_explicit_overrides_env(monkeypatch, tmp_path):
    """Test that explicit set_verify_ssl overrides environment variable."""
    env_cert = tmp_path / "env-ca.crt"
    env_cert.write_text("dummy cert")
    explicit_cert = tmp_path / "explicit-ca.crt"
    explicit_cert.write_text("dummy cert")

    monkeypatch.setenv("OSS_SUSTAIN_GUARD_CA_CERT", str(env_cert))
    set_verify_ssl(str(explicit_cert))

    # Explicit set should take priority
    with patch("ssl.create_default_context") as mock_create_context:
        mock_context = MagicMock(spec=ssl.SSLContext)
        mock_create_context.return_value = mock_context

        result = get_verify_ssl()
        assert result is mock_context
        mock_create_context.assert_called_once_with(cafile=str(explicit_cert))


def test_get_verify_ssl_env_when_reset(monkeypatch, tmp_path):
    """Test that resetting to None uses environment variable."""
    env_cert = tmp_path / "env-ca.crt"
    env_cert.write_text("dummy cert")

    monkeypatch.setenv("OSS_SUSTAIN_GUARD_CA_CERT", str(env_cert))
    set_verify_ssl(None)

    # Should use env var
    with patch("ssl.create_default_context") as mock_create_context:
        mock_context = MagicMock(spec=ssl.SSLContext)
        mock_create_context.return_value = mock_context

        result = get_verify_ssl()
        assert result is mock_context
        mock_create_context.assert_called_once_with(cafile=str(env_cert))


def test_get_verify_ssl_default_when_no_env(monkeypatch):
    """Test that default True is returned when no explicit set and no env var."""
    monkeypatch.delenv("OSS_SUSTAIN_GUARD_CA_CERT", raising=False)
    set_verify_ssl(None)

    # Should return default True
    assert get_verify_ssl() is True


def test_get_excluded_users_from_local_config(temp_project_root):
    """Test loading excluded users from .oss-sustain-guard.toml."""
    config_file = temp_project_root / ".oss-sustain-guard.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard]
exclude-users = ["my-ci-user", "release-bot"]
"""
    )

    excluded = get_excluded_users()
    assert "my-ci-user" in excluded
    assert "release-bot" in excluded


def test_get_excluded_users_from_pyproject(temp_project_root):
    """Test loading excluded users from pyproject.toml."""
    config_file = temp_project_root / "pyproject.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard]
exclude-users = ["trusted-ci", "internal-bot"]
"""
    )

    excluded = get_excluded_users()
    assert "trusted-ci" in excluded
    assert "internal-bot" in excluded


def test_local_config_excluded_users_priority(temp_project_root):
    """Test that .oss-sustain-guard.toml takes priority for exclude-users."""
    # Create pyproject.toml
    pyproject = temp_project_root / "pyproject.toml"
    pyproject.write_text(
        """
[tool.oss-sustain-guard]
exclude-users = ["user-from-pyproject"]
"""
    )

    # Create local config (should take priority)
    local_config = temp_project_root / ".oss-sustain-guard.toml"
    local_config.write_text(
        """
[tool.oss-sustain-guard]
exclude-users = ["user-from-local"]
"""
    )

    excluded = get_excluded_users()
    assert "user-from-local" in excluded
    # pyproject.toml should be ignored when local config exists
    assert "user-from-pyproject" not in excluded


def test_excluded_users_empty_when_no_config(temp_project_root):
    """Test that empty list is returned when no config exists."""
    excluded = get_excluded_users()
    assert excluded == []


def test_excluded_users_with_both_formats(temp_project_root):
    """Test that both exclude-users (TOML) and exclude_users (Python) formats work."""
    # Test with underscore format
    config_file = temp_project_root / ".oss-sustain-guard.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard]
exclude_users = ["python-style-user"]
"""
    )

    excluded = get_excluded_users()
    assert "python-style-user" in excluded
