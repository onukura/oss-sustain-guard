"""
Tests for JavaScript resolver.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.javascript import JavaScriptResolver


class TestJavaScriptResolver:
    """Test JavaScriptResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = JavaScriptResolver()
        assert resolver.ecosystem_name == "javascript"

    def test_get_manifest_files(self):
        """Test manifest files for JavaScript."""
        resolver = JavaScriptResolver()
        manifests = resolver.get_manifest_files()
        assert "package.json" in manifests

    @patch("httpx.Client.get")
    def test_resolve_github_url_success(self, mock_get):
        """Test resolving GitHub URL from npm registry."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": {
                "type": "git",
                "url": "git+https://github.com/facebook/react.git",
            }
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = resolver.resolve_github_url("react")
        assert result == ("facebook", "react")

    @patch("httpx.Client.get")
    def test_resolve_github_url_string_repo(self, mock_get):
        """Test resolving when repository is a string."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": "https://github.com/lodash/lodash"
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = resolver.resolve_github_url("lodash")
        assert result == ("lodash", "lodash")

    @patch("httpx.Client.get")
    def test_resolve_github_url_homepage_fallback(self, mock_get):
        """Test fallback to homepage field."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": {},
            "homepage": "https://github.com/vuejs/vue",
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = resolver.resolve_github_url("vue")
        assert result == ("vuejs", "vue")

    @patch("httpx.Client.get")
    def test_resolve_github_url_not_found(self, mock_get):
        """Test resolving package with no GitHub URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": {},
            "homepage": "https://example.com",
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = resolver.resolve_github_url("some-package")
        assert result is None

    @patch("httpx.Client.get")
    def test_resolve_github_url_network_error(self, mock_get):
        """Test resolving with network error."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = JavaScriptResolver()
        result = resolver.resolve_github_url("react")
        assert result is None

    def test_detect_lockfiles(self, tmp_path):
        """Test detecting JavaScript lockfiles."""
        (tmp_path / "package-lock.json").touch()
        (tmp_path / "package.json").touch()

        resolver = JavaScriptResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) == 1
        assert lockfiles[0].name == "package-lock.json"

    def test_detect_lockfiles_yarn(self, tmp_path):
        """Test detecting yarn.lock."""
        (tmp_path / "yarn.lock").touch()

        resolver = JavaScriptResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) == 1
        assert lockfiles[0].name == "yarn.lock"

    def test_parse_package_lock(self, tmp_path):
        """Test parsing package-lock.json."""
        package_lock = {
            "dependencies": {
                "react": {"version": "18.2.0"},
                "lodash": {"version": "4.17.21"},
            }
        }
        lock_file = tmp_path / "package-lock.json"
        lock_file.write_text(json.dumps(package_lock))

        resolver = JavaScriptResolver()
        packages = resolver.parse_lockfile(str(lock_file))

        assert len(packages) >= 2
        names = {p.name for p in packages}
        assert "react" in names
        assert "lodash" in names
        assert all(p.ecosystem == "javascript" for p in packages)

    def test_parse_yarn_lock(self, tmp_path):
        """Test parsing yarn.lock."""
        yarn_content = """# THIS IS A GENERATED FILE
"react@^18.0.0":
  version "18.2.0"
  dependencies:
    react-dom: "^18.0.0"

"lodash@^4.17.0":
  version "4.17.21"
"""
        lock_file = tmp_path / "yarn.lock"
        lock_file.write_text(yarn_content)

        resolver = JavaScriptResolver()
        packages = resolver.parse_lockfile(str(lock_file))

        assert len(packages) >= 1
        names = {p.name for p in packages}
        assert "react" in names
        assert all(p.ecosystem == "javascript" for p in packages)

    def test_parse_lockfile_not_found(self):
        """Test parsing non-existent lockfile."""
        resolver = JavaScriptResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/nonexistent/package-lock.json")

    def test_parse_lockfile_unknown_type(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown_lock = tmp_path / "unknown.lock"
        unknown_lock.touch()

        resolver = JavaScriptResolver()
        with pytest.raises(ValueError, match="Unknown JavaScript lockfile type"):
            resolver.parse_lockfile(str(unknown_lock))
