"""
Tests for Haskell resolver.
"""

from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.haskell import (
    HaskellResolver,
    _extract_cabal_repo_urls,
)


class TestHaskellResolver:
    """Test HaskellResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = HaskellResolver()
        assert resolver.ecosystem_name == "haskell"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository(self, mock_get):
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
        result = await resolver.resolve_repository("text")
        assert result is not None
        assert result.owner == "haskell"
        assert result.name == "text"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_not_found(self, mock_get):
        """Test handling missing Hackage package."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        resolver = HaskellResolver()
        assert await resolver.resolve_repository("missing") is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_no_versions(self, mock_get):
        """Test handling package with no versions."""
        versions_response = MagicMock()
        versions_response.status_code = 200
        versions_response.json.return_value = {}
        mock_get.return_value = versions_response

        resolver = HaskellResolver()
        assert await resolver.resolve_repository("empty") is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_non_numeric_version(self, mock_get):
        """Test resolving with non-numeric version strings."""
        versions_response = MagicMock()
        versions_response.status_code = 200
        versions_response.json.return_value = {
            "x.y": "normal",
            "1.2.3": "normal",
        }

        cabal_response = MagicMock()
        cabal_response.status_code = 200
        cabal_response.text = "bug-reports: https://github.com/haskell/text/issues\n"

        mock_get.side_effect = [versions_response, cabal_response]

        resolver = HaskellResolver()
        result = await resolver.resolve_repository("text")
        assert result is not None
        assert result.owner == "haskell"
        assert result.name == "text"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_cabal_not_found(self, mock_get):
        """Test handling missing cabal file."""
        versions_response = MagicMock()
        versions_response.status_code = 200
        versions_response.json.return_value = {"1.2.3": "normal"}

        cabal_response = MagicMock()
        cabal_response.status_code = 404

        mock_get.side_effect = [versions_response, cabal_response]

        resolver = HaskellResolver()
        assert await resolver.resolve_repository("text") is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_request_error(self, mock_get):
        """Test handling Hackage request errors."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = HaskellResolver()
        assert await resolver.resolve_repository("text") is None

    async def test_parse_cabal_freeze(self, tmp_path):
        """Test parsing cabal.project.freeze."""
        content = "constraints: any.text ==1.2.5.0, any.bytestring ==0.11.5.2"
        lockfile = tmp_path / "cabal.project.freeze"
        lockfile.write_text(content)

        resolver = HaskellResolver()
        packages = await resolver.parse_lockfile(lockfile)

        names = {pkg.name for pkg in packages}
        assert names == {"text", "bytestring"}

    async def test_parse_stack_lock(self, tmp_path):
        """Test parsing stack.yaml.lock."""
        content = "hackage: text-1.2.5.0@sha256:abc,456\n"
        lockfile = tmp_path / "stack.yaml.lock"
        lockfile.write_text(content)

        resolver = HaskellResolver()
        packages = await resolver.parse_lockfile(lockfile)

        assert len(packages) == 1
        assert packages[0].name == "text"

    async def test_parse_cabal_freeze_duplicates(self, tmp_path):
        """Test parsing cabal.project.freeze with duplicates."""
        content = "constraints: any.text ==1.2.5.0, any.text ==1.2.5.0"
        lockfile = tmp_path / "cabal.project.freeze"
        lockfile.write_text(content)

        resolver = HaskellResolver()
        packages = await resolver.parse_lockfile(lockfile)

        assert len(packages) == 1
        assert packages[0].name == "text"

    async def test_parse_cabal_freeze_read_error(self, tmp_path, monkeypatch):
        """Test read errors for cabal.project.freeze."""
        lockfile = tmp_path / "cabal.project.freeze"
        lockfile.write_text("constraints: any.text ==1.2.5.0")

        def _raise(*_args, **_kwargs):
            raise OSError("read error")

        monkeypatch.setattr(lockfile.__class__, "read_text", _raise)

        resolver = HaskellResolver()
        with pytest.raises(ValueError, match="Failed to read cabal.project.freeze"):
            await resolver.parse_lockfile(lockfile)

    async def test_parse_stack_lock_duplicates(self, tmp_path):
        """Test parsing stack.yaml.lock with duplicates."""
        content = (
            "hackage: text-1.2.5.0@sha256:abc,456\n"
            "hackage: text-1.2.5.0@sha256:def,789\n"
        )
        lockfile = tmp_path / "stack.yaml.lock"
        lockfile.write_text(content)

        resolver = HaskellResolver()
        packages = await resolver.parse_lockfile(lockfile)

        assert len(packages) == 1
        assert packages[0].name == "text"

    async def test_parse_stack_lock_read_error(self, tmp_path, monkeypatch):
        """Test read errors for stack.yaml.lock."""
        lockfile = tmp_path / "stack.yaml.lock"
        lockfile.write_text("hackage: text-1.2.5.0@sha256:abc,456\n")

        def _raise(*_args, **_kwargs):
            raise OSError("read error")

        monkeypatch.setattr(lockfile.__class__, "read_text", _raise)

        resolver = HaskellResolver()
        with pytest.raises(ValueError, match="Failed to read stack.yaml.lock"):
            await resolver.parse_lockfile(lockfile)

    async def test_parse_lockfile_not_found(self):
        """Test parsing missing lockfile."""
        resolver = HaskellResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_lockfile("/missing/cabal.project.freeze")

    async def test_parse_lockfile_unknown(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown = tmp_path / "unknown.lock"
        unknown.touch()

        resolver = HaskellResolver()
        with pytest.raises(ValueError, match="Unknown Haskell lockfile type"):
            await resolver.parse_lockfile(unknown)

    async def test_parse_manifest_cabal_project(self, tmp_path):
        """Test parsing cabal.project manifest."""
        manifest = tmp_path / "cabal.project"
        manifest.write_text("constraints: any.text, any.bytestring")

        resolver = HaskellResolver()
        packages = await resolver.parse_manifest(manifest)

        names = {pkg.name for pkg in packages}
        assert names == {"text", "bytestring"}

    async def test_parse_manifest_stack_yaml(self, tmp_path):
        """Test parsing stack.yaml manifest."""
        manifest = tmp_path / "stack.yaml"
        manifest.write_text("extra-deps:\n  - text-1.2.5.0\n")

        resolver = HaskellResolver()
        packages = await resolver.parse_manifest(manifest)

        assert len(packages) == 1
        assert packages[0].name == "text"

    async def test_parse_manifest_cabal_project_duplicates(self, tmp_path):
        """Test parsing cabal.project with duplicate constraints."""
        manifest = tmp_path / "cabal.project"
        manifest.write_text("constraints: any.text, any.text\n")

        resolver = HaskellResolver()
        packages = await resolver.parse_manifest(manifest)

        assert len(packages) == 1
        assert packages[0].name == "text"

    async def test_parse_manifest_cabal_project_read_error(self, tmp_path, monkeypatch):
        """Test read errors for cabal.project."""
        manifest = tmp_path / "cabal.project"
        manifest.write_text("constraints: any.text\n")

        def _raise(*_args, **_kwargs):
            raise OSError("read error")

        monkeypatch.setattr(manifest.__class__, "read_text", _raise)

        resolver = HaskellResolver()
        with pytest.raises(ValueError, match="Failed to read cabal.project"):
            await resolver.parse_manifest(manifest)

    async def test_parse_manifest_stack_read_error(self, tmp_path, monkeypatch):
        """Test read errors for stack.yaml."""
        manifest = tmp_path / "stack.yaml"
        manifest.write_text("extra-deps:\n  - text-1.2.5.0\n")

        def _raise(*_args, **_kwargs):
            raise OSError("read error")

        monkeypatch.setattr(manifest.__class__, "read_text", _raise)

        resolver = HaskellResolver()
        with pytest.raises(ValueError, match="Failed to read stack.yaml"):
            await resolver.parse_manifest(manifest)

    async def test_parse_manifest_stack_duplicates(self, tmp_path):
        """Test parsing stack manifest with duplicate entries."""
        manifest = tmp_path / "package.yaml"
        manifest.write_text("extra-deps:\n  - text-1.2.5.0\n  - text-1.2.5.0\n")

        resolver = HaskellResolver()
        packages = await resolver.parse_manifest(manifest)

        assert len(packages) == 1
        assert packages[0].name == "text"

    async def test_parse_manifest_not_found(self):
        """Test missing manifest."""
        resolver = HaskellResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_manifest("/missing/cabal.project")

    async def test_parse_manifest_unknown(self, tmp_path):
        """Test unknown manifest type."""
        unknown = tmp_path / "unknown.yaml"
        unknown.touch()

        resolver = HaskellResolver()
        with pytest.raises(ValueError, match="Unknown Haskell manifest file type"):
            await resolver.parse_manifest(unknown)

    async def test_detect_lockfiles_both(self, tmp_path):
        """Test detecting both Haskell lockfiles."""
        (tmp_path / "cabal.project.freeze").touch()
        (tmp_path / "stack.yaml.lock").touch()

        resolver = HaskellResolver()
        lockfiles = await resolver.detect_lockfiles(tmp_path)

        assert {lf.name for lf in lockfiles} == {
            "cabal.project.freeze",
            "stack.yaml.lock",
        }

    def test_extract_cabal_repo_urls_bug_reports(self):
        """Test extracting repository URLs from bug-reports entries."""
        content = "bug-reports: https://github.com/haskell/text/issues\n"
        urls = _extract_cabal_repo_urls(content)

        assert urls == ["https://github.com/haskell/text"]
