"""
Tests for Elixir resolver.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.elixir import ElixirResolver


class TestElixirResolver:
    """Test ElixirResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = ElixirResolver()
        assert resolver.ecosystem_name == "elixir"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository(self, mock_get):
        """Test resolving repository from Hex.pm response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meta": {"links": {"GitHub": "https://github.com/phoenixframework/phoenix"}}
        }
        mock_get.return_value = mock_response

        resolver = ElixirResolver()
        result = await resolver.resolve_repository("phoenix")
        assert result is not None
        assert result.owner == "phoenixframework"
        assert result.name == "phoenix"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_not_found(self, mock_get):
        """Test handling missing Hex.pm package."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        resolver = ElixirResolver()
        assert await resolver.resolve_repository("missing") is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_request_error(self, mock_get):
        """Test handling Hex.pm request errors."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = ElixirResolver()
        assert await resolver.resolve_repository("phoenix") is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_no_supported_url(self, mock_get):
        """Test resolving package with no supported repository URLs."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"meta": {"links": {"Docs": 123}}}
        mock_get.return_value = mock_response

        resolver = ElixirResolver()
        assert await resolver.resolve_repository("phoenix") is None

    async def test_parse_lockfile(self, tmp_path):
        """Test parsing mix.lock."""
        lockfile = tmp_path / "mix.lock"
        lockfile.write_text(
            '%{"phoenix": {:hex, :phoenix, "1.7.0"}, "ecto": {:hex, :ecto, "3.10"}}'
        )

        resolver = ElixirResolver()
        packages = await resolver.parse_lockfile(lockfile)
        names = {pkg.name for pkg in packages}
        assert names == {"phoenix", "ecto"}

    async def test_parse_lockfile_duplicates(self, tmp_path):
        """Test parsing mix.lock with duplicate entries."""
        lockfile = tmp_path / "mix.lock"
        lockfile.write_text(
            '%{"phoenix": {:hex, :phoenix, "1.7.0"}, "phoenix": {:hex, :phoenix, "1.7.0"}}'
        )

        resolver = ElixirResolver()
        packages = await resolver.parse_lockfile(lockfile)
        assert len(packages) == 1
        assert packages[0].name == "phoenix"

    async def test_parse_lockfile_not_found(self):
        """Test missing lockfile."""
        resolver = ElixirResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_lockfile("/missing/mix.lock")

    async def test_parse_lockfile_unknown(self, tmp_path):
        """Test unknown lockfile type."""
        unknown = tmp_path / "unknown.lock"
        unknown.touch()

        resolver = ElixirResolver()
        with pytest.raises(ValueError, match="Unknown Elixir lockfile type"):
            await resolver.parse_lockfile(unknown)

    @patch("aiofiles.open")
    async def test_parse_lockfile_read_error(self, mock_aiofiles_open, tmp_path):
        """Test error reading mix.lock."""
        # Create a temporary file that exists
        lockfile = tmp_path / "mix.lock"
        lockfile.write_text("content")

        # Create a mock file object that raises OSError when read
        mock_file = AsyncMock()
        mock_file.__aenter__.return_value = mock_file
        mock_file.__aexit__.return_value = None
        mock_file.read.side_effect = OSError("read error")

        mock_aiofiles_open.return_value = mock_file

        resolver = ElixirResolver()
        with pytest.raises(ValueError, match="Failed to read mix.lock"):
            await resolver.parse_lockfile(lockfile)

    async def test_parse_manifest(self, tmp_path):
        """Test parsing mix.exs."""
        manifest = tmp_path / "mix.exs"
        manifest.write_text(
            "defmodule Example.MixProject do\n"
            "defp deps do\n"
            "  [\n"
            '    {:phoenix, "~> 1.7"},\n'
            '    {:ecto_sql, "~> 3.10"}\n'
            "  ]\n"
            "end\n"
        )

        resolver = ElixirResolver()
        packages = await resolver.parse_manifest(manifest)
        names = {pkg.name for pkg in packages}
        assert "phoenix" in names
        assert "ecto_sql" in names
        assert "example" not in names

    async def test_parse_manifest_not_found(self):
        """Test missing manifest."""
        resolver = ElixirResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_manifest("/missing/mix.exs")

    async def test_parse_manifest_unknown(self, tmp_path):
        """Test unknown manifest type."""
        unknown = tmp_path / "unknown.exs"
        unknown.touch()

        resolver = ElixirResolver()
        with pytest.raises(ValueError, match="Unknown Elixir manifest file type"):
            await resolver.parse_manifest(unknown)

    async def test_parse_manifest_no_deps(self, tmp_path):
        """Test parsing mix.exs without deps block."""
        manifest = tmp_path / "mix.exs"
        manifest.write_text("defmodule Example do\nend\n")

        resolver = ElixirResolver()
        packages = await resolver.parse_manifest(manifest)

        assert packages == []

    @patch("aiofiles.open")
    async def test_parse_manifest_read_error(self, mock_aiofiles_open, tmp_path):
        """Test error reading mix.exs."""
        # Create a temporary file that exists
        manifest = tmp_path / "mix.exs"
        manifest.write_text("defmodule Example do\nend\n")

        # Create a mock file object that raises OSError when read
        mock_file = AsyncMock()
        mock_file.__aenter__.return_value = mock_file
        mock_file.__aexit__.return_value = None
        mock_file.read.side_effect = OSError("read error")

        mock_aiofiles_open.return_value = mock_file

        resolver = ElixirResolver()
        with pytest.raises(ValueError, match="Failed to read mix.exs"):
            await resolver.parse_manifest(manifest)
