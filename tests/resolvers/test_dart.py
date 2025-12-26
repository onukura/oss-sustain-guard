"""
Tests for Dart resolver.
"""

from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.dart import DartResolver


class TestDartResolver:
    """Test DartResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = DartResolver()
        assert resolver.ecosystem_name == "dart"

    @patch("httpx.Client.get")
    def test_resolve_repository(self, mock_get):
        """Test resolving repository from pub.dev response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "latest": {"pubspec": {"repository": "https://github.com/dart-lang/http"}}
        }
        mock_get.return_value = mock_response

        resolver = DartResolver()
        result = resolver.resolve_repository("http")
        assert result is not None
        assert result.owner == "dart-lang"
        assert result.name == "http"

    @patch("httpx.Client.get")
    def test_resolve_repository_not_found(self, mock_get):
        """Test handling missing pub.dev package."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        resolver = DartResolver()
        assert resolver.resolve_repository("missing") is None

    def test_parse_lockfile(self, tmp_path):
        """Test parsing pubspec.lock."""
        lockfile = tmp_path / "pubspec.lock"
        lockfile.write_text(
            "packages:\n"
            "  http:\n"
            '    dependency: "direct main"\n'
            "  path:\n"
            "    dependency: transitive\n"
        )

        resolver = DartResolver()
        packages = resolver.parse_lockfile(lockfile)
        names = {pkg.name for pkg in packages}
        assert names == {"http", "path"}

    def test_parse_lockfile_not_found(self):
        """Test missing lockfile."""
        resolver = DartResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/missing/pubspec.lock")

    def test_parse_lockfile_unknown(self, tmp_path):
        """Test unknown lockfile type."""
        unknown = tmp_path / "unknown.lock"
        unknown.touch()

        resolver = DartResolver()
        with pytest.raises(ValueError, match="Unknown Dart lockfile type"):
            resolver.parse_lockfile(unknown)

    def test_parse_manifest(self, tmp_path):
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
        packages = resolver.parse_manifest(manifest)
        names = {pkg.name for pkg in packages}
        assert names == {"http", "path", "lints"}

    def test_parse_manifest_not_found(self):
        """Test missing manifest."""
        resolver = DartResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_manifest("/missing/pubspec.yaml")

    def test_parse_manifest_unknown(self, tmp_path):
        """Test unknown manifest type."""
        unknown = tmp_path / "unknown.yaml"
        unknown.touch()

        resolver = DartResolver()
        with pytest.raises(ValueError, match="Unknown Dart manifest file type"):
            resolver.parse_manifest(unknown)
