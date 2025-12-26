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

    @patch("httpx.Client.get")
    def test_resolve_repository(self, mock_get):
        """Test resolving repository from CRAN response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "URL": "https://github.com/tidyverse/ggplot2",
        }
        mock_get.return_value = mock_response

        resolver = RResolver()
        result = resolver.resolve_repository("ggplot2")
        assert result is not None
        assert result.owner == "tidyverse"
        assert result.name == "ggplot2"

    @patch("httpx.Client.get")
    def test_resolve_repository_not_found(self, mock_get):
        """Test handling missing CRAN package."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        resolver = RResolver()
        assert resolver.resolve_repository("missing") is None

    def test_parse_lockfile(self, tmp_path):
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
        packages = resolver.parse_lockfile(lockfile)

        assert len(packages) == 2
        names = {pkg.name for pkg in packages}
        assert names == {"dplyr", "ggplot2"}

    def test_parse_lockfile_not_found(self):
        """Test parsing missing lockfile."""
        resolver = RResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/missing/renv.lock")

    def test_parse_lockfile_unknown(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown = tmp_path / "unknown.lock"
        unknown.touch()

        resolver = RResolver()
        with pytest.raises(ValueError, match="Unknown R lockfile type"):
            resolver.parse_lockfile(unknown)

    def test_parse_manifest(self, tmp_path):
        """Test parsing DESCRIPTION manifest."""
        description = tmp_path / "DESCRIPTION"
        description.write_text(
            "Package: example\nImports: dplyr, ggplot2 (>= 3.0.0)\nSuggests: testthat\n"
        )

        resolver = RResolver()
        packages = resolver.parse_manifest(description)

        names = {pkg.name for pkg in packages}
        assert names == {"dplyr", "ggplot2", "testthat"}

    def test_parse_manifest_not_found(self):
        """Test missing DESCRIPTION."""
        resolver = RResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_manifest("/missing/DESCRIPTION")

    def test_parse_manifest_unknown(self, tmp_path):
        """Test unknown manifest type."""
        unknown = tmp_path / "unknown.txt"
        unknown.touch()

        resolver = RResolver()
        with pytest.raises(ValueError, match="Unknown R manifest file type"):
            resolver.parse_manifest(unknown)
