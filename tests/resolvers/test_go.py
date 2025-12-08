"""
Tests for Go resolver.
"""

from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.go import GoResolver


class TestGoResolver:
    """Test GoResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = GoResolver()
        assert resolver.ecosystem_name == "go"

    def test_get_manifest_files(self):
        """Test manifest files for Go."""
        resolver = GoResolver()
        manifests = resolver.get_manifest_files()
        assert "go.mod" in manifests

    def test_resolve_github_url_direct_path(self):
        """Test resolving GitHub path directly."""
        resolver = GoResolver()
        result = resolver.resolve_github_url("github.com/golang/go")
        assert result == ("golang", "go")

    def test_resolve_github_url_with_subdomain(self):
        """Test resolving GitHub path with subdomain."""
        resolver = GoResolver()
        result = resolver.resolve_github_url("github.com/sirupsen/logrus")
        assert result == ("sirupsen", "logrus")

    @patch("httpx.Client.get")
    def test_resolve_github_url_golang_org(self, mock_get):
        """Test resolving golang.org package via pkg.go.dev."""
        mock_response = MagicMock()
        mock_response.text = '<a href="https://github.com/golang/text">Repository</a>'
        mock_get.return_value = mock_response

        resolver = GoResolver()
        result = resolver.resolve_github_url("golang.org/x/text")
        assert result == ("golang", "text")

    @patch("httpx.Client.get")
    def test_resolve_github_url_network_error(self, mock_get):
        """Test resolving with network error."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = GoResolver()
        result = resolver.resolve_github_url("golang.org/x/net")
        assert result is None

    def test_detect_lockfiles(self, tmp_path):
        """Test detecting Go lockfiles."""
        (tmp_path / "go.sum").touch()
        (tmp_path / "go.mod").touch()

        resolver = GoResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) == 1
        assert lockfiles[0].name == "go.sum"

    def test_parse_go_sum(self, tmp_path):
        """Test parsing go.sum."""
        go_sum_content = """github.com/golang/go v1.21.0 h1:someHash
github.com/sirupsen/logrus v1.9.0 h1:anotherHash
golang.org/x/sys v0.10.0 h1:yetAnotherHash
"""
        sum_file = tmp_path / "go.sum"
        sum_file.write_text(go_sum_content)

        resolver = GoResolver()
        packages = resolver.parse_lockfile(str(sum_file))

        assert len(packages) == 3
        names = {p.name for p in packages}
        assert "github.com/golang/go" in names
        assert "github.com/sirupsen/logrus" in names
        assert "golang.org/x/sys" in names
        assert all(p.ecosystem == "go" for p in packages)

    def test_parse_lockfile_not_found(self):
        """Test parsing non-existent lockfile."""
        resolver = GoResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/nonexistent/go.sum")

    def test_parse_lockfile_unknown_type(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown_file = tmp_path / "unknown.lock"
        unknown_file.touch()

        resolver = GoResolver()
        with pytest.raises(ValueError, match="Unknown Go lockfile type"):
            resolver.parse_lockfile(str(unknown_file))
