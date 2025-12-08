"""
Tests for the configuration module.
"""

import tempfile
from pathlib import Path

import pytest

from oss_sustain_guard.config import get_excluded_packages, is_package_excluded


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
