"""
Tests for Go resolver.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.go import GoResolver


class TestGoResolver:
    """Test GoResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = GoResolver()
        assert resolver.ecosystem_name == "go"

    async def test_get_manifest_files(self):
        """Test manifest files for Go."""
        resolver = GoResolver()
        manifests = await resolver.get_manifest_files()
        assert "go.mod" in manifests

    async def test_resolve_github_url_direct_path(self):
        """Test resolving GitHub path directly."""
        resolver = GoResolver()
        result = await resolver.resolve_github_url("github.com/golang/go")
        assert result == ("golang", "go")

    async def test_resolve_github_url_with_subdomain(self):
        """Test resolving GitHub path with subdomain."""
        resolver = GoResolver()
        result = await resolver.resolve_github_url("github.com/sirupsen/logrus")
        assert result == ("sirupsen", "logrus")

    async def test_resolve_github_url_with_version_suffix(self):
        """Test resolving GitHub path with Go module version suffix."""
        resolver = GoResolver()
        # go-redis/redis uses /v8 version suffix for v8.x releases
        result = await resolver.resolve_github_url("github.com/go-redis/redis/v8")
        assert result == ("go-redis", "redis")

    async def test_resolve_github_url_with_v2_suffix(self):
        """Test resolving GitHub path with /v2 version suffix."""
        resolver = GoResolver()
        result = await resolver.resolve_github_url("github.com/user/repo/v2")
        assert result == ("user", "repo")

    def test_strip_go_version_suffix(self):
        """Test _strip_go_version_suffix helper method."""
        # Test various version suffixes
        assert (
            GoResolver._strip_go_version_suffix("github.com/go-redis/redis/v8")
            == "github.com/go-redis/redis"
        )
        assert (
            GoResolver._strip_go_version_suffix("github.com/user/repo/v2")
            == "github.com/user/repo"
        )
        assert (
            GoResolver._strip_go_version_suffix("github.com/user/repo/v100")
            == "github.com/user/repo"
        )
        # Test paths without version suffix remain unchanged
        assert (
            GoResolver._strip_go_version_suffix("github.com/golang/go")
            == "github.com/golang/go"
        )
        # Test that it doesn't match version-like strings in the middle
        assert (
            GoResolver._strip_go_version_suffix("github.com/v2ray/v2ray-core")
            == "github.com/v2ray/v2ray-core"
        )

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_golang_org(self, mock_get):
        """Test resolving golang.org package via pkg.go.dev."""
        mock_response = MagicMock()
        mock_response.text = '<a href="https://github.com/golang/text">Repository</a>'
        mock_get.return_value = mock_response

        resolver = GoResolver()
        result = await resolver.resolve_github_url("golang.org/x/text")
        assert result == ("golang", "text")

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_short_name(self, mock_get):
        """Test resolving short package name via pkg.go.dev search."""
        # Mock search response
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.text = """
            <a href="/gorm.io/gorm" data-test-id="snippet-title">
              gorm
            </a>
        """

        # Mock package page response
        package_response = MagicMock()
        package_response.text = """
            <div class="UnitMeta-repo">
                <a href="https://github.com/go-gorm/gorm">github.com/go-gorm/gorm</a>
            </div>
        """

        mock_get.side_effect = [search_response, package_response]

        resolver = GoResolver()
        result = await resolver.resolve_github_url("gorm")
        assert result == ("go-gorm", "gorm")

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_with_unitmeta_repo(self, mock_get):
        """Test resolving with UnitMeta-repo section."""
        mock_response = MagicMock()
        mock_response.text = """
            <h2>Repository</h2>
            <div class="UnitMeta-repo">
                <a href="https://github.com/sirupsen/logrus" title="repo">
                    github.com/sirupsen/logrus
                </a>
            </div>
            <a href="https://github.com/golang/go">Go Language</a>
        """
        mock_get.return_value = mock_response

        resolver = GoResolver()
        result = await resolver.resolve_github_url("github.com/sirupsen/logrus")
        assert result == ("sirupsen", "logrus")

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_fallback_filtering(self, mock_get):
        """Test fallback pattern with golang/go filtering."""
        mock_response = MagicMock()
        mock_response.text = """
            <a href="https://github.com/golang/go">Go logo</a>
            <a href="https://github.com/user/repo">Repository</a>
        """
        mock_get.return_value = mock_response

        resolver = GoResolver()
        result = await resolver.resolve_github_url("example.com/user/repo")
        assert result == ("user", "repo")

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_network_error(self, mock_get):
        """Test resolving with network error."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = GoResolver()
        result = await resolver.resolve_github_url("golang.org/x/net")
        assert result is None

    async def test_detect_lockfiles(self, tmp_path):
        """Test detecting Go lockfiles."""
        (tmp_path / "go.sum").touch()
        (tmp_path / "go.mod").touch()

        resolver = GoResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        lockfile_names = {lockfile.name for lockfile in lockfiles}
        assert lockfile_names == {"go.mod", "go.sum"}

    async def test_parse_go_sum(self, tmp_path):
        """Test parsing go.sum."""
        go_sum_content = """github.com/golang/go v1.21.0 h1:someHash
github.com/sirupsen/logrus v1.9.0 h1:anotherHash
golang.org/x/sys v0.10.0 h1:yetAnotherHash
"""
        sum_file = tmp_path / "go.sum"
        sum_file.write_text(go_sum_content)

        resolver = GoResolver()
        packages = await resolver.parse_lockfile(str(sum_file))

        assert len(packages) == 3
        names = {p.name for p in packages}
        assert "github.com/golang/go" in names
        assert "github.com/sirupsen/logrus" in names
        assert "golang.org/x/sys" in names
        assert all(p.ecosystem == "go" for p in packages)

    async def test_parse_lockfile_not_found(self):
        """Test parsing non-existent lockfile."""
        resolver = GoResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_lockfile("/nonexistent/go.sum")

    async def test_parse_lockfile_unknown_type(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown_file = tmp_path / "unknown.lock"
        unknown_file.touch()

        resolver = GoResolver()
        with pytest.raises(ValueError, match="Unknown Go lockfile type"):
            await resolver.parse_lockfile(str(unknown_file))

    @patch("aiofiles.open")
    async def test_parse_lockfile_read_error(self, mock_aiofiles_open, tmp_path):
        """Test parsing go.sum with read error."""
        # Create a temporary file that exists
        sum_file = tmp_path / "go.sum"
        sum_file.write_text("github.com/golang/go v1.21.0 h1:hash")

        # Create a mock file object that raises OSError when read
        mock_file = AsyncMock()
        mock_file.__aenter__.return_value = mock_file
        mock_file.__aexit__.return_value = None
        mock_file.read.side_effect = OSError("read error")

        mock_aiofiles_open.return_value = mock_file

        resolver = GoResolver()
        packages = await resolver.parse_lockfile(str(sum_file))
        assert packages == []

    async def test_parse_manifest_not_found(self):
        """Test parsing missing go.mod."""
        resolver = GoResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_manifest("/missing/go.mod")

    async def test_parse_manifest_unknown_type(self, tmp_path):
        """Test parsing unknown manifest type."""
        manifest = tmp_path / "go.txt"
        manifest.touch()

        resolver = GoResolver()
        with pytest.raises(ValueError, match="Unknown Go manifest file type"):
            await resolver.parse_manifest(manifest)

    async def test_parse_manifest_go_mod(self, tmp_path):
        """Test parsing go.mod with block and single-line requires."""
        manifest = tmp_path / "go.mod"
        manifest.write_text(
            "module github.com/example/project\n"
            "go 1.21\n"
            "require (\n"
            "  github.com/user/repo v1.2.3\n"
            "  // comment\n"
            "  github.com/other/repo v0.1.0\n"
            ")\n"
            "require github.com/single/repo v0.9.0\n"
        )

        resolver = GoResolver()
        packages = await resolver.parse_manifest(manifest)

        names = {pkg.name for pkg in packages}
        assert names == {
            "github.com/user/repo",
            "github.com/other/repo",
            "github.com/single/repo",
        }

    @patch("aiofiles.open")
    async def test_parse_manifest_read_error(self, mock_aiofiles_open, tmp_path):
        """Test parsing go.mod with read error."""
        # Create a temporary file that exists
        manifest = tmp_path / "go.mod"
        manifest.write_text("module example\n")

        # Create a mock file object that raises OSError when read
        mock_file = AsyncMock()
        mock_file.__aenter__.return_value = mock_file
        mock_file.__aexit__.return_value = None
        mock_file.read.side_effect = OSError("read error")

        mock_aiofiles_open.return_value = mock_file

        resolver = GoResolver()
        with pytest.raises(ValueError, match="Failed to parse go.mod"):
            await resolver.parse_manifest(manifest)
