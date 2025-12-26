"""
Tests for Haskell resolver.
"""

from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.haskell import HaskellResolver


class TestHaskellResolver:
    """Test HaskellResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = HaskellResolver()
        assert resolver.ecosystem_name == "haskell"

    @patch("httpx.Client.get")
    def test_resolve_repository(self, mock_get):
        """Test resolving repository from Hackage metadata."""
        # First call: get versions
        versions_response = MagicMock()
        versions_response.status_code = 200
        versions_response.json.return_value = {
            "1.2.5.0": "normal",
            "1.2.5.1": "normal",
        }

        # Second call: get cabal file
        cabal_response = MagicMock()
        cabal_response.status_code = 200
        cabal_response.text = """
source-repository head
  type: git
  location: https://github.com/haskell/text
"""

        # Mock returns different responses on subsequent calls
        mock_get.side_effect = [versions_response, cabal_response]

        resolver = HaskellResolver()
        result = resolver.resolve_repository("text")
        assert result is not None
        assert result.owner == "haskell"
        assert result.name == "text"

    @patch("httpx.Client.get")
    def test_resolve_repository_not_found(self, mock_get):
        """Test handling missing Hackage package."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        resolver = HaskellResolver()
        assert resolver.resolve_repository("missing") is None

    def test_parse_cabal_freeze(self, tmp_path):
        """Test parsing cabal.project.freeze."""
        content = "constraints: any.text ==1.2.5.0, any.bytestring ==0.11.5.2"
        lockfile = tmp_path / "cabal.project.freeze"
        lockfile.write_text(content)

        resolver = HaskellResolver()
        packages = resolver.parse_lockfile(lockfile)

        names = {pkg.name for pkg in packages}
        assert names == {"text", "bytestring"}

    def test_parse_stack_lock(self, tmp_path):
        """Test parsing stack.yaml.lock."""
        content = "hackage: text-1.2.5.0@sha256:abc,456\n"
        lockfile = tmp_path / "stack.yaml.lock"
        lockfile.write_text(content)

        resolver = HaskellResolver()
        packages = resolver.parse_lockfile(lockfile)

        assert len(packages) == 1
        assert packages[0].name == "text"

    def test_parse_lockfile_not_found(self):
        """Test parsing missing lockfile."""
        resolver = HaskellResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/missing/cabal.project.freeze")

    def test_parse_lockfile_unknown(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown = tmp_path / "unknown.lock"
        unknown.touch()

        resolver = HaskellResolver()
        with pytest.raises(ValueError, match="Unknown Haskell lockfile type"):
            resolver.parse_lockfile(unknown)

    def test_parse_manifest_cabal_project(self, tmp_path):
        """Test parsing cabal.project manifest."""
        manifest = tmp_path / "cabal.project"
        manifest.write_text("constraints: any.text, any.bytestring")

        resolver = HaskellResolver()
        packages = resolver.parse_manifest(manifest)

        names = {pkg.name for pkg in packages}
        assert names == {"text", "bytestring"}

    def test_parse_manifest_stack_yaml(self, tmp_path):
        """Test parsing stack.yaml manifest."""
        manifest = tmp_path / "stack.yaml"
        manifest.write_text("extra-deps:\n  - text-1.2.5.0\n")

        resolver = HaskellResolver()
        packages = resolver.parse_manifest(manifest)

        assert len(packages) == 1
        assert packages[0].name == "text"

    def test_parse_manifest_not_found(self):
        """Test missing manifest."""
        resolver = HaskellResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_manifest("/missing/cabal.project")

    def test_parse_manifest_unknown(self, tmp_path):
        """Test unknown manifest type."""
        unknown = tmp_path / "unknown.yaml"
        unknown.touch()

        resolver = HaskellResolver()
        with pytest.raises(ValueError, match="Unknown Haskell manifest file type"):
            resolver.parse_manifest(unknown)
