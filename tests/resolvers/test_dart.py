"""
Tests for Dart resolver.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.dart import DartResolver


class TestDartResolver:
    """Test DartResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = DartResolver()
        assert resolver.ecosystem_name == "dart"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository(self, mock_get):
        """Test resolving repository from pub.dev response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "latest": {"pubspec": {"repository": "https://github.com/dart-lang/http"}}
        }
        mock_get.return_value = mock_response

        resolver = DartResolver()
        result = await resolver.resolve_repository("http")
        assert result is not None
        assert result.owner == "dart-lang"
        assert result.name == "http"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_not_found(self, mock_get):
        """Test handling missing pub.dev package."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        resolver = DartResolver()
        assert await resolver.resolve_repository("missing") is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_request_error(self, mock_get):
        """Test handling pub.dev request errors."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = DartResolver()
        assert await resolver.resolve_repository("http") is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_no_supported_url(self, mock_get):
        """Test resolving package with no supported repository URLs."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "latest": {"pubspec": {"homepage": "https://example.com"}}
        }
        mock_get.return_value = mock_response

        resolver = DartResolver()
        assert await resolver.resolve_repository("http") is None

    async def test_parse_lockfile(self, tmp_path):
        """Test parsing pubspec.lock."""
        lockfile = tmp_path / "pubspec.lock"
        lockfile.write_text(
            "sdks:\n"
            "  dart: '>=2.19.0'\n"
            "packages:\n"
            "  http:\n"
            '    dependency: "direct main"\n'
            "  path:\n"
            "    dependency: transitive\n"
            "environment:\n"
            "  sdk: '>=2.19.0'\n"
        )

        resolver = DartResolver()
        packages = await resolver.parse_lockfile(lockfile)
        names = {pkg.name for pkg in packages}
        assert names == {"http", "path"}

    async def test_parse_lockfile_not_found(self):
        """Test missing lockfile."""
        resolver = DartResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_lockfile("/missing/pubspec.lock")

    async def test_parse_lockfile_unknown(self, tmp_path):
        """Test unknown lockfile type."""
        unknown = tmp_path / "unknown.lock"
        unknown.touch()

        resolver = DartResolver()
        with pytest.raises(ValueError, match="Unknown Dart lockfile type"):
            await resolver.parse_lockfile(unknown)

    @patch("aiofiles.open")
    async def test_parse_lockfile_read_error(self, mock_aiofiles_open, tmp_path):
        """Test error reading pubspec.lock."""
        # Create a temporary file that exists
        lockfile = tmp_path / "pubspec.lock"
        lockfile.write_text("packages:\n  http:\n")

        # Create a mock file object that raises OSError when read
        mock_file = AsyncMock()
        mock_file.__aenter__.return_value = mock_file
        mock_file.__aexit__.return_value = None
        mock_file.read.side_effect = OSError("read error")

        mock_aiofiles_open.return_value = mock_file

        resolver = DartResolver()
        with pytest.raises(ValueError, match="Failed to read pubspec.lock"):
            await resolver.parse_lockfile(lockfile)

    async def test_parse_manifest(self, tmp_path):
        """Test parsing pubspec.yaml."""
        manifest = tmp_path / "pubspec.yaml"
        manifest.write_text(
            "name: example\n"
            "dependencies:\n"
            "  http: ^0.13.0\n"
            "  path: any\n"
            "dev_dependencies:\n"
            "  lints: ^2.1.0\n"
        )

        resolver = DartResolver()
        packages = await resolver.parse_manifest(manifest)
        names = {pkg.name for pkg in packages}
        assert names == {"http", "path", "lints"}

    async def test_parse_manifest_not_found(self):
        """Test missing manifest."""
        resolver = DartResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_manifest("/missing/pubspec.yaml")

    async def test_parse_manifest_unknown(self, tmp_path):
        """Test unknown manifest type."""
        unknown = tmp_path / "unknown.yaml"
        unknown.touch()

        resolver = DartResolver()
        with pytest.raises(ValueError, match="Unknown Dart manifest file type"):
            await resolver.parse_manifest(unknown)

    @patch("aiofiles.open")
    async def test_parse_manifest_read_error(self, mock_aiofiles_open, tmp_path):
        """Test error reading pubspec.yaml."""
        # Create a temporary file that exists
        manifest = tmp_path / "pubspec.yaml"
        manifest.write_text("dependencies:\n  http: ^0.13.0\n")

        # Create a mock file object that raises OSError when read
        mock_file = AsyncMock()
        mock_file.__aenter__.return_value = mock_file
        mock_file.__aexit__.return_value = None
        mock_file.read.side_effect = OSError("read error")

        mock_aiofiles_open.return_value = mock_file

        resolver = DartResolver()
        with pytest.raises(ValueError, match="Failed to read pubspec.yaml"):
            await resolver.parse_manifest(manifest)
