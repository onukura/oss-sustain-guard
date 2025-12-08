"""
Tests for Python resolver.
"""

from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.python import PythonResolver


class TestPythonResolver:
    """Test PythonResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = PythonResolver()
        assert resolver.ecosystem_name == "python"

    def test_get_manifest_files(self):
        """Test manifest files for Python."""
        resolver = PythonResolver()
        manifests = resolver.get_manifest_files()
        assert "requirements.txt" in manifests
        assert "pyproject.toml" in manifests
        assert "Pipfile" in manifests

    @patch("httpx.Client.get")
    def test_resolve_github_url_success(self, mock_get):
        """Test resolving GitHub URL from PyPI."""
        # Mock successful PyPI response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "info": {"project_urls": {"Source": "https://github.com/psf/requests"}}
        }
        mock_get.return_value = mock_response

        resolver = PythonResolver()
        result = resolver.resolve_github_url("requests")
        assert result == ("psf", "requests")

    @patch("httpx.Client.get")
    def test_resolve_github_url_not_found(self, mock_get):
        """Test resolving package with no GitHub URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"info": {"project_urls": {}}}
        mock_get.return_value = mock_response

        resolver = PythonResolver()
        result = resolver.resolve_github_url("some-package")
        assert result is None

    @patch("httpx.Client.get")
    def test_resolve_github_url_network_error(self, mock_get):
        """Test resolving with network error."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = PythonResolver()
        result = resolver.resolve_github_url("requests")
        assert result is None

    def test_detect_lockfiles(self, tmp_path):
        """Test detecting Python lockfiles."""
        # Create temporary lockfiles
        (tmp_path / "poetry.lock").touch()
        (tmp_path / "other.txt").touch()

        resolver = PythonResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        # Should only detect poetry.lock
        assert len(lockfiles) == 1
        assert lockfiles[0].name == "poetry.lock"

    def test_detect_lockfiles_multiple(self, tmp_path):
        """Test detecting multiple lockfiles."""
        (tmp_path / "poetry.lock").touch()
        (tmp_path / "uv.lock").touch()

        resolver = PythonResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) == 2
        names = {lf.name for lf in lockfiles}
        assert names == {"poetry.lock", "uv.lock"}

    def test_parse_lockfile_not_found(self):
        """Test parsing non-existent lockfile."""
        resolver = PythonResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/nonexistent/poetry.lock")

    def test_parse_lockfile_unknown_type(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown_lock = tmp_path / "unknown.lock"
        unknown_lock.touch()

        resolver = PythonResolver()
        with pytest.raises(ValueError, match="Unknown Python lockfile type"):
            resolver.parse_lockfile(str(unknown_lock))

    def test_legacy_get_github_url_from_pypi(self):
        """Test legacy backward compatibility function."""
        with patch("httpx.Client.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "info": {
                    "project_urls": {
                        "Repository": "https://github.com/kennethreitz/requests"
                    }
                }
            }
            mock_get.return_value = mock_response

            from oss_sustain_guard.resolvers.python import (
                get_github_url_from_pypi,
            )

            result = get_github_url_from_pypi("requests")
            assert result == ("kennethreitz", "requests")

    def test_legacy_detect_lockfiles(self, tmp_path):
        """Test legacy backward compatibility function."""
        (tmp_path / "poetry.lock").touch()

        from oss_sustain_guard.resolvers.python import detect_lockfiles

        lockfiles = detect_lockfiles(str(tmp_path))
        assert len(lockfiles) == 1
        assert lockfiles[0].name == "poetry.lock"
