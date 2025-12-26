"""
Tests for Elixir resolver.
"""

from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.elixir import ElixirResolver


class TestElixirResolver:
    """Test ElixirResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = ElixirResolver()
        assert resolver.ecosystem_name == "elixir"

    @patch("httpx.Client.get")
    def test_resolve_repository(self, mock_get):
        """Test resolving repository from Hex.pm response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meta": {"links": {"GitHub": "https://github.com/phoenixframework/phoenix"}}
        }
        mock_get.return_value = mock_response

        resolver = ElixirResolver()
        result = resolver.resolve_repository("phoenix")
        assert result is not None
        assert result.owner == "phoenixframework"
        assert result.name == "phoenix"

    @patch("httpx.Client.get")
    def test_resolve_repository_not_found(self, mock_get):
        """Test handling missing Hex.pm package."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        resolver = ElixirResolver()
        assert resolver.resolve_repository("missing") is None

    def test_parse_lockfile(self, tmp_path):
        """Test parsing mix.lock."""
        lockfile = tmp_path / "mix.lock"
        lockfile.write_text(
            '%{"phoenix": {:hex, :phoenix, "1.7.0"}, "ecto": {:hex, :ecto, "3.10"}}'
        )

        resolver = ElixirResolver()
        packages = resolver.parse_lockfile(lockfile)
        names = {pkg.name for pkg in packages}
        assert names == {"phoenix", "ecto"}

    def test_parse_lockfile_not_found(self):
        """Test missing lockfile."""
        resolver = ElixirResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/missing/mix.lock")

    def test_parse_lockfile_unknown(self, tmp_path):
        """Test unknown lockfile type."""
        unknown = tmp_path / "unknown.lock"
        unknown.touch()

        resolver = ElixirResolver()
        with pytest.raises(ValueError, match="Unknown Elixir lockfile type"):
            resolver.parse_lockfile(unknown)

    def test_parse_manifest(self, tmp_path):
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
        packages = resolver.parse_manifest(manifest)
        names = {pkg.name for pkg in packages}
        assert "phoenix" in names
        assert "ecto_sql" in names
        assert "example" not in names

    def test_parse_manifest_not_found(self):
        """Test missing manifest."""
        resolver = ElixirResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_manifest("/missing/mix.exs")

    def test_parse_manifest_unknown(self, tmp_path):
        """Test unknown manifest type."""
        unknown = tmp_path / "unknown.exs"
        unknown.touch()

        resolver = ElixirResolver()
        with pytest.raises(ValueError, match="Unknown Elixir manifest file type"):
            resolver.parse_manifest(unknown)
