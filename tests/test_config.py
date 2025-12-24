"""
Tests for the configuration module.
"""

import tempfile
from pathlib import Path

import pytest

from oss_sustain_guard.config import (
    get_cache_dir,
    get_cache_ttl,
    get_excluded_packages,
    get_output_style,
    is_cache_enabled,
    is_package_excluded,
    is_verbose_enabled,
    set_cache_dir,
    set_cache_ttl,
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
