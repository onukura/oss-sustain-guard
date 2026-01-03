"""
Tests for R resolver.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.r import RResolver


class TestRResolver:
    """Test RResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = RResolver()
        assert resolver.ecosystem_name == "r"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository(self, mock_get):
        """Test resolving repository from CRAN response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "URL": "https://github.com/tidyverse/ggplot2",
        }
        mock_get.return_value = mock_response

        resolver = RResolver()
        result = await resolver.resolve_repository("ggplot2")
        assert result is not None
        assert result.owner == "tidyverse"
        assert result.name == "ggplot2"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_not_found(self, mock_get):
        """Test handling missing CRAN package."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        resolver = RResolver()
        assert await resolver.resolve_repository("missing") is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_request_error(self, mock_get):
        """Test handling CRAN request errors."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = RResolver()
        assert await resolver.resolve_repository("ggplot2") is None

    async def test_parse_lockfile(self, tmp_path):
        """Test parsing renv.lock."""
        lock_data = {
            "Packages": {
                "dplyr": {"Version": "1.1.0"},
                "ggplot2": {"Version": "3.4.1"},
            }
        }
        lockfile = tmp_path / "renv.lock"
        lockfile.write_text(json.dumps(lock_data))

        resolver = RResolver()
        packages = await resolver.parse_lockfile(lockfile)

        assert len(packages) == 2
        names = {pkg.name for pkg in packages}
        assert names == {"dplyr", "ggplot2"}

    async def test_parse_lockfile_skips_invalid_entries(self, tmp_path):
        """Test parsing renv.lock with invalid package entries."""
        lock_data = {"Packages": {"": {}, "valid": {"Version": "1.0.0"}}}
        lockfile = tmp_path / "renv.lock"
        lockfile.write_text(json.dumps(lock_data))

        resolver = RResolver()
        packages = await resolver.parse_lockfile(lockfile)

        assert len(packages) == 1
        assert packages[0].name == "valid"

    async def test_parse_lockfile_not_found(self):
        """Test parsing missing lockfile."""
        resolver = RResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_lockfile("/missing/renv.lock")

    async def test_parse_lockfile_unknown(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown = tmp_path / "unknown.lock"
        unknown.touch()

        resolver = RResolver()
        with pytest.raises(ValueError, match="Unknown R lockfile type"):
            await resolver.parse_lockfile(unknown)

    async def test_parse_lockfile_invalid_json(self, tmp_path):
        """Test parsing invalid renv.lock."""
        lockfile = tmp_path / "renv.lock"
        lockfile.write_text("{ invalid json }")

        resolver = RResolver()
        with pytest.raises(ValueError, match="Failed to parse renv.lock"):
            await resolver.parse_lockfile(lockfile)

    async def test_parse_manifest(self, tmp_path):
        """Test parsing DESCRIPTION manifest."""
        description = tmp_path / "DESCRIPTION"
        description.write_text(
            "Package: example\nImports: dplyr, ggplot2 (>= 3.0.0)\nSuggests: testthat\n"
        )

        resolver = RResolver()
        packages = await resolver.parse_manifest(description)

        names = {pkg.name for pkg in packages}
        assert names == {"dplyr", "ggplot2", "testthat"}

    async def test_parse_manifest_continuation_lines(self, tmp_path):
        """Test parsing DESCRIPTION with continuation lines."""
        description = tmp_path / "DESCRIPTION"
        description.write_text(
            "Imports: dplyr,\n ggplot2,\nDepends: dplyr\nSuggests: dplyr\n"
        )

        resolver = RResolver()
        packages = await resolver.parse_manifest(description)

        names = {pkg.name for pkg in packages}
        assert names == {"dplyr", "ggplot2"}

    async def test_parse_manifest_not_found(self):
        """Test missing DESCRIPTION."""
        resolver = RResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_manifest("/missing/DESCRIPTION")

    async def test_parse_manifest_unknown(self, tmp_path):
        """Test unknown manifest type."""
        unknown = tmp_path / "unknown.txt"
        unknown.touch()

        resolver = RResolver()
        with pytest.raises(ValueError, match="Unknown R manifest file type"):
            await resolver.parse_manifest(unknown)

    async def test_parse_manifest_read_error(self, tmp_path, monkeypatch):
        """Test error reading DESCRIPTION."""
        description = tmp_path / "DESCRIPTION"
        description.write_text("Imports: dplyr\n")

        def _raise(*_args, **_kwargs):
            raise OSError("read error")

        monkeypatch.setattr("aiofiles.open", _raise)

        resolver = RResolver()
        with pytest.raises(ValueError, match="Failed to read DESCRIPTION"):
            await resolver.parse_manifest(description)

    def test_split_urls_non_string(self):
        """Test splitting URL fields with non-string values."""
        from oss_sustain_guard.resolvers.r import _split_urls

        assert _split_urls(None) == []
