"""
Tests for Perl resolver.
"""

from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.perl import PerlResolver


class TestPerlResolver:
    """Test PerlResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = PerlResolver()
        assert resolver.ecosystem_name == "perl"

    @patch("httpx.Client.get")
    def test_resolve_repository(self, mock_get):
        """Test resolving repository from MetaCPAN response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "resources": {"repository": {"url": "https://github.com/mojolicious/mojo"}}
        }
        mock_get.return_value = mock_response

        resolver = PerlResolver()
        result = resolver.resolve_repository("Mojolicious")
        assert result is not None
        assert result.owner == "mojolicious"
        assert result.name == "mojo"

    @patch("httpx.Client.get")
    def test_resolve_repository_not_found(self, mock_get):
        """Test handling missing MetaCPAN package."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        resolver = PerlResolver()
        assert resolver.resolve_repository("missing") is None

    def test_parse_lockfile(self, tmp_path):
        """Test parsing cpanfile.snapshot."""
        lockfile = tmp_path / "cpanfile.snapshot"
        lockfile.write_text(
            "DISTRIBUTIONS\n"
            "  distribution: Mojolicious-9.33\n"
            "  distribution: Test-Simple-1.302190\n"
        )

        resolver = PerlResolver()
        packages = resolver.parse_lockfile(lockfile)
        names = {pkg.name for pkg in packages}
        assert names == {"Mojolicious", "Test-Simple"}

    def test_parse_lockfile_not_found(self):
        """Test missing lockfile."""
        resolver = PerlResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/missing/cpanfile.snapshot")

    def test_parse_lockfile_unknown(self, tmp_path):
        """Test unknown lockfile type."""
        unknown = tmp_path / "unknown.lock"
        unknown.touch()

        resolver = PerlResolver()
        with pytest.raises(ValueError, match="Unknown Perl lockfile type"):
            resolver.parse_lockfile(unknown)

    def test_parse_manifest(self, tmp_path):
        """Test parsing cpanfile."""
        manifest = tmp_path / "cpanfile"
        manifest.write_text("requires 'Mojolicious', '9.00';\nrequires \"DBI\";\n")

        resolver = PerlResolver()
        packages = resolver.parse_manifest(manifest)
        names = {pkg.name for pkg in packages}
        assert names == {"Mojolicious", "DBI"}

    def test_parse_manifest_not_found(self):
        """Test missing manifest."""
        resolver = PerlResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_manifest("/missing/cpanfile")

    def test_parse_manifest_unknown(self, tmp_path):
        """Test unknown manifest type."""
        unknown = tmp_path / "unknown"
        unknown.touch()

        resolver = PerlResolver()
        with pytest.raises(ValueError, match="Unknown Perl manifest file type"):
            resolver.parse_manifest(unknown)
