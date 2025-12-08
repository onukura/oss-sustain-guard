"""
Tests for PHP resolver.
"""

from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.php import PhpResolver


class TestPhpResolver:
    """Test PhpResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = PhpResolver()
        assert resolver.ecosystem_name == "php"

    def test_get_manifest_files(self):
        """Test manifest files for PHP."""
        resolver = PhpResolver()
        manifests = resolver.get_manifest_files()
        assert "composer.json" in manifests
        assert "composer.lock" in manifests

    @patch("httpx.Client.get")
    def test_resolve_github_url_success(self, mock_get):
        """Test resolving GitHub URL from Packagist."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "packages": {
                "symfony/console": [
                    {
                        "name": "symfony/console",
                        "version": "6.0.0",
                        "source": {
                            "type": "git",
                            "url": "https://github.com/symfony/console",
                            "reference": "abc123",
                        },
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        resolver = PhpResolver()
        result = resolver.resolve_github_url("symfony/console")
        assert result == ("symfony", "console")

    @patch("httpx.Client.get")
    def test_resolve_github_url_not_found(self, mock_get):
        """Test resolving package with no GitHub URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"packages": {}}
        mock_get.return_value = mock_response

        resolver = PhpResolver()
        result = resolver.resolve_github_url("nonexistent/package")
        assert result is None

    @patch("httpx.Client.get")
    def test_resolve_github_url_network_error(self, mock_get):
        """Test resolving with network error."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = PhpResolver()
        result = resolver.resolve_github_url("symfony/console")
        assert result is None

    def test_detect_lockfiles(self, tmp_path):
        """Test detecting PHP lockfiles."""
        (tmp_path / "composer.lock").touch()
        (tmp_path / "other.txt").touch()

        resolver = PhpResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) >= 1
        assert any(lf.name == "composer.lock" for lf in lockfiles)

    def test_detect_lockfiles_nested(self, tmp_path):
        """Test detecting nested composer.lock files."""
        (tmp_path / "composer.lock").touch()
        subdir = tmp_path / "vendor" / "package"
        subdir.mkdir(parents=True, exist_ok=True)
        # Note: We don't expect to find composer.lock in vendor typically

        resolver = PhpResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        # Should find at least the root composer.lock
        assert len(lockfiles) >= 1
        assert any(lf.name == "composer.lock" for lf in lockfiles)

    def test_parse_lockfile_not_found(self):
        """Test parsing non-existent lockfile."""
        resolver = PhpResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/nonexistent/composer.lock")

    def test_parse_lockfile_success(self, tmp_path):
        """Test parsing valid composer.lock."""
        lockfile = tmp_path / "composer.lock"
        lockfile.write_text(
            """{
            "packages": [
                {
                    "name": "symfony/console",
                    "version": "6.0.0"
                },
                {
                    "name": "guzzlehttp/guzzle",
                    "version": "7.0.0"
                }
            ]
        }"""
        )

        resolver = PhpResolver()
        packages = resolver.parse_lockfile(str(lockfile))

        assert len(packages) == 2
        assert packages[0].name == "symfony/console"
        assert packages[0].version == "6.0.0"
        assert packages[0].ecosystem == "php"
        assert packages[1].name == "guzzlehttp/guzzle"

    def test_parse_lockfile_invalid_json(self, tmp_path):
        """Test parsing invalid JSON lockfile."""
        lockfile = tmp_path / "composer.lock"
        lockfile.write_text("{ invalid json }")

        resolver = PhpResolver()
        with pytest.raises(ValueError):
            resolver.parse_lockfile(str(lockfile))

    def test_parse_github_url_valid(self):
        """Test parsing valid GitHub URL."""
        resolver = PhpResolver()
        result = resolver._parse_github_url("https://github.com/symfony/console")
        assert result == ("symfony", "console")

    def test_parse_github_url_with_git_suffix(self):
        """Test parsing GitHub URL with .git suffix."""
        resolver = PhpResolver()
        result = resolver._parse_github_url("https://github.com/symfony/console.git")
        assert result == ("symfony", "console")

    def test_parse_github_url_non_github(self):
        """Test parsing non-GitHub URL."""
        resolver = PhpResolver()
        result = resolver._parse_github_url("https://gitlab.com/user/repo")
        # Non-GitHub URLs still extract owner/repo, just not from GitHub
        assert result == ("user", "repo")

    def test_parse_github_url_invalid(self):
        """Test parsing invalid URL."""
        resolver = PhpResolver()
        assert resolver._parse_github_url("") is None
        assert resolver._parse_github_url("invalid") is None
