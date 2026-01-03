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

    async def test_get_manifest_files(self):
        """Test manifest files for PHP."""
        resolver = PhpResolver()
        manifests = await resolver.get_manifest_files()
        assert "composer.json" in manifests
        assert "composer.lock" in manifests

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_success(self, mock_get):
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
        result = await resolver.resolve_github_url("symfony/console")
        assert result == ("symfony", "console")

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_not_found(self, mock_get):
        """Test resolving package with no GitHub URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"packages": {}}
        mock_get.return_value = mock_response

        resolver = PhpResolver()
        result = await resolver.resolve_github_url("nonexistent/package")
        assert result is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_network_error(self, mock_get):
        """Test resolving with network error."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = PhpResolver()
        result = await resolver.resolve_github_url("symfony/console")
        assert result is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_empty_version_list(self, mock_get):
        """Test resolving when package version list is empty."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "packages": {
                "vendor/package": [],
            }
        }
        mock_get.return_value = mock_response

        resolver = PhpResolver()
        result = await resolver.resolve_github_url("vendor/package")
        assert result is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_support_fallback(self, mock_get):
        """Test resolving repository from support source URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "packages": {
                "vendor/package": [
                    {
                        "source": {"url": "https://example.com/repo.git"},
                        "support": {"source": "https://github.com/vendor/package"},
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        resolver = PhpResolver()
        result = await resolver.resolve_github_url("vendor/package")
        assert result == ("vendor", "package")

    async def test_detect_lockfiles(self, tmp_path):
        """Test detecting PHP lockfiles."""
        (tmp_path / "composer.lock").touch()
        (tmp_path / "other.txt").touch()

        resolver = PhpResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) >= 1
        assert any(lf.name == "composer.lock" for lf in lockfiles)

    async def test_detect_lockfiles_nested(self, tmp_path):
        """Test detecting nested composer.lock files."""
        (tmp_path / "composer.lock").touch()
        subdir = tmp_path / "vendor" / "package"
        subdir.mkdir(parents=True, exist_ok=True)
        # Note: We don't expect to find composer.lock in vendor typically

        resolver = PhpResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        # Should find at least the root composer.lock
        assert len(lockfiles) >= 1
        assert any(lf.name == "composer.lock" for lf in lockfiles)

    async def test_parse_lockfile_not_found(self):
        """Test parsing non-existent lockfile."""
        resolver = PhpResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_lockfile("/nonexistent/composer.lock")

    async def test_parse_lockfile_success(self, tmp_path):
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
        packages = await resolver.parse_lockfile(str(lockfile))

        assert len(packages) == 2
        assert packages[0].name == "symfony/console"
        assert packages[0].version == "6.0.0"
        assert packages[0].ecosystem == "php"
        assert packages[1].name == "guzzlehttp/guzzle"

    async def test_parse_lockfile_invalid_json(self, tmp_path):
        """Test parsing invalid JSON lockfile."""
        lockfile = tmp_path / "composer.lock"
        lockfile.write_text("{ invalid json }")

        resolver = PhpResolver()
        with pytest.raises(ValueError):
            await resolver.parse_lockfile(str(lockfile))

    async def test_parse_manifest(self, tmp_path):
        """Test parsing composer.json."""
        manifest = tmp_path / "composer.json"
        manifest.write_text(
            """{
            "require": {
                "symfony/console": "^6.0"
            },
            "require-dev": {
                "phpunit/phpunit": "^10.0"
            }
        }"""
        )

        resolver = PhpResolver()
        packages = await resolver.parse_manifest(manifest)

        names = {pkg.name for pkg in packages}
        assert names == {"symfony/console", "phpunit/phpunit"}

    async def test_parse_manifest_invalid(self, tmp_path):
        """Test parsing invalid composer.json."""
        manifest = tmp_path / "composer.json"
        manifest.write_text("{ invalid json }")

        resolver = PhpResolver()
        with pytest.raises(ValueError, match="Failed to parse composer.json"):
            await resolver.parse_manifest(manifest)

    async def test_parse_manifest_not_found(self):
        """Test parsing missing composer.json."""
        resolver = PhpResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_manifest("/missing/composer.json")

    async def test_parse_manifest_unknown(self, tmp_path):
        """Test parsing unknown manifest type."""
        manifest = tmp_path / "composer.lock"
        manifest.touch()

        resolver = PhpResolver()
        with pytest.raises(ValueError, match="Unknown PHP manifest file type"):
            await resolver.parse_manifest(manifest)

    def test_parse_repository_url_github(self):
        """Test parsing valid GitHub URL."""
        from oss_sustain_guard.repository import parse_repository_url

        result = parse_repository_url("https://github.com/symfony/console")
        assert result is not None
        assert result.provider == "github"
        assert result.owner == "symfony"
        assert result.name == "console"

    def test_parse_repository_url_github_with_git_suffix(self):
        """Test parsing GitHub URL with .git suffix."""
        from oss_sustain_guard.repository import parse_repository_url

        result = parse_repository_url("https://github.com/symfony/console.git")
        assert result is not None
        assert result.provider == "github"
        assert result.owner == "symfony"
        assert result.name == "console"

    def test_parse_repository_url_gitlab(self):
        """Test parsing GitLab URL."""
        from oss_sustain_guard.repository import parse_repository_url

        result = parse_repository_url("https://gitlab.com/user/repo")
        assert result is not None
        assert result.provider == "gitlab"
        assert result.owner == "user"
        assert result.name == "repo"

    def test_parse_repository_url_invalid(self):
        """Test parsing invalid URL."""
        from oss_sustain_guard.repository import parse_repository_url

        assert parse_repository_url("") is None
        assert parse_repository_url("invalid") is None
