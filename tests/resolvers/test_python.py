"""
Tests for Python resolver.
"""

import builtins
import json
import textwrap
from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.python import PythonResolver


class TestPythonResolver:
    """Test PythonResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = PythonResolver()
        assert resolver.ecosystem_name == "python"

    async def test_get_manifest_files(self):
        """Test manifest files for Python."""
        resolver = PythonResolver()
        manifests = await resolver.get_manifest_files()
        assert "requirements.txt" in manifests
        assert "pyproject.toml" in manifests
        assert "Pipfile" in manifests

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_success(self, mock_get):
        """Test resolving GitHub URL from PyPI."""
        # Mock successful PyPI response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "info": {"project_urls": {"Source": "https://github.com/psf/requests"}}
        }
        mock_get.return_value = mock_response

        resolver = PythonResolver()
        result = await resolver.resolve_github_url("requests")
        assert result == ("psf", "requests")

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_project_url_fallback(self, mock_get):
        """Test resolving repository when earlier URL candidates are unsupported."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "info": {
                "project_urls": {
                    "Source": "https://example.com/not-supported",
                    "Repository": "https://gitlab.com/group/project",
                }
            }
        }
        mock_get.return_value = mock_response

        resolver = PythonResolver()
        result = await resolver.resolve_repository("project")
        assert result and result.provider == "gitlab"
        assert result.owner == "group"
        assert result.name == "project"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_home_page_fallback(self, mock_get):
        """Test resolving repository from home_page when project_urls is empty."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "info": {
                "project_urls": {},
                "home_page": "https://github.com/psf/requests",
            }
        }
        mock_get.return_value = mock_response

        resolver = PythonResolver()
        result = await resolver.resolve_repository("requests")
        assert result and result.owner == "psf" and result.name == "requests"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_not_found(self, mock_get):
        """Test resolving package with no GitHub URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"info": {"project_urls": {}}}
        mock_get.return_value = mock_response

        resolver = PythonResolver()
        result = await resolver.resolve_github_url("some-package")
        assert result is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_network_error(self, mock_get):
        """Test resolving with network error."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = PythonResolver()
        result = await resolver.resolve_github_url("requests")
        assert result is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_repository_http_status_error(self, mock_get):
        """Test resolving with HTTP status error."""
        import httpx

        request = httpx.Request("GET", "https://pypi.org/pypi/requests/json")
        response = httpx.Response(404, request=request)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=request, response=response
        )
        mock_get.return_value = mock_response

        resolver = PythonResolver()
        result = await resolver.resolve_repository("requests")
        assert result is None

    async def test_detect_lockfiles(self, tmp_path):
        """Test detecting Python lockfiles."""
        # Create temporary lockfiles
        (tmp_path / "poetry.lock").touch()
        (tmp_path / "other.txt").touch()

        resolver = PythonResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        # Should only detect poetry.lock
        assert len(lockfiles) == 1
        assert lockfiles[0].name == "poetry.lock"

    async def test_detect_lockfiles_multiple(self, tmp_path):
        """Test detecting multiple lockfiles."""
        (tmp_path / "poetry.lock").touch()
        (tmp_path / "uv.lock").touch()

        resolver = PythonResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) == 2
        names = {lf.name for lf in lockfiles}
        assert names == {"poetry.lock", "uv.lock"}

    async def test_detect_lockfiles_pipfile_lock(self, tmp_path):
        """Test detecting Pipfile.lock."""
        (tmp_path / "Pipfile.lock").touch()

        resolver = PythonResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) == 1
        assert lockfiles[0].name == "Pipfile.lock"

    async def test_parse_lockfile_not_found(self):
        """Test parsing non-existent lockfile."""
        resolver = PythonResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_lockfile("/nonexistent/poetry.lock")

    async def test_parse_lockfile_unknown_type(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown_lock = tmp_path / "unknown.lock"
        unknown_lock.touch()

        resolver = PythonResolver()
        with pytest.raises(ValueError, match="Unknown Python lockfile type"):
            await resolver.parse_lockfile(str(unknown_lock))

    async def test_parse_manifest_requirements_read_error(self, tmp_path):
        """Test requirements parsing when read fails."""
        missing = tmp_path / "missing.txt"

        packages = await PythonResolver._parse_manifest_requirements(missing)

        assert packages == []

    async def test_parse_lockfile_poetry(self, tmp_path):
        """Test parsing poetry.lock."""
        lockfile = tmp_path / "poetry.lock"
        lockfile.write_text(
            textwrap.dedent(
                """
                [[package]]
                name = "requests"
                version = "2.31.0"

                [[package]]
                name = "rich"
                version = "13.7.0"
                """
            ).strip()
        )

        resolver = PythonResolver()
        packages = await resolver.parse_lockfile(str(lockfile))

        names = {p.name for p in packages}
        assert names == {"requests", "rich"}
        versions = {p.name: p.version for p in packages}
        assert versions["requests"] == "2.31.0"
        assert versions["rich"] == "13.7.0"

    async def test_parse_lockfile_uv(self, tmp_path):
        """Test parsing uv.lock."""
        lockfile = tmp_path / "uv.lock"
        lockfile.write_text(
            textwrap.dedent(
                """
                [[package]]
                name = "fastapi"
                version = "0.110.0"
                """
            ).strip()
        )

        resolver = PythonResolver()
        packages = await resolver.parse_lockfile(str(lockfile))

        assert len(packages) == 1
        assert packages[0].name == "fastapi"
        assert packages[0].version == "0.110.0"

    async def test_parse_lockfile_poetry_invalid_toml(self, tmp_path):
        """Test parsing poetry.lock with invalid TOML."""
        lockfile = tmp_path / "poetry.lock"
        lockfile.write_text("not = [toml")

        resolver = PythonResolver()
        packages = await resolver.parse_lockfile(str(lockfile))

        assert packages == []

    async def test_parse_lockfile_uv_invalid_toml(self, tmp_path):
        """Test parsing uv.lock with invalid TOML."""
        lockfile = tmp_path / "uv.lock"
        lockfile.write_text("not = [toml")

        resolver = PythonResolver()
        packages = await resolver.parse_lockfile(str(lockfile))

        assert packages == []

    async def test_parse_lockfile_pipenv(self, tmp_path):
        """Test parsing Pipfile.lock."""
        lockfile = tmp_path / "Pipfile.lock"
        lock_data = {
            "default": {
                "requests": {"version": "==2.31.0"},
                "flask": "*",
            },
            "develop": {"pytest": {"version": "==7.4.0"}},
        }
        lockfile.write_text(json.dumps(lock_data))

        resolver = PythonResolver()
        packages = await resolver.parse_lockfile(str(lockfile))

        names = {p.name for p in packages}
        assert names == {"requests", "flask", "pytest"}
        versions = {p.name: p.version for p in packages}
        assert versions["requests"] == "==2.31.0"
        assert versions["flask"] is None
        assert versions["pytest"] == "==7.4.0"

    async def test_parse_lockfile_pipenv_invalid_json(self, tmp_path):
        """Test parsing Pipfile.lock with invalid JSON."""
        lockfile = tmp_path / "Pipfile.lock"
        lockfile.write_text("{not: valid json")

        resolver = PythonResolver()
        packages = await resolver.parse_lockfile(str(lockfile))

        assert packages == []

    async def test_parse_manifest_not_found(self):
        """Test parsing non-existent manifest file."""
        resolver = PythonResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_manifest("/nonexistent/requirements.txt")

    async def test_parse_manifest_unknown_type(self, tmp_path):
        """Test parsing unknown manifest file type."""
        manifest = tmp_path / "unknown.txt"
        manifest.touch()

        resolver = PythonResolver()
        with pytest.raises(ValueError, match="Unknown Python manifest file type"):
            await resolver.parse_manifest(str(manifest))

    async def test_parse_manifest_requirements(self, tmp_path):
        """Test parsing requirements.txt."""
        manifest = tmp_path / "requirements.txt"
        manifest.write_text(
            textwrap.dedent(
                """
                # comment
                requests==2.31.0
                django>=4.2
                """
            ).strip()
        )

        resolver = PythonResolver()
        packages = await resolver.parse_manifest(str(manifest))

        names = {p.name for p in packages}
        assert names == {"requests", "django"}
        assert all(p.ecosystem == "python" for p in packages)

    async def test_parse_manifest_pyproject_invalid_toml(self, tmp_path):
        """Test parsing pyproject.toml with invalid TOML."""
        manifest = tmp_path / "pyproject.toml"
        manifest.write_text("not = [toml")

        resolver = PythonResolver()
        packages = await resolver.parse_manifest(str(manifest))

        assert packages == []

    async def test_parse_manifest_pyproject(self, tmp_path):
        """Test parsing pyproject.toml."""
        manifest = tmp_path / "pyproject.toml"
        manifest.write_text(
            textwrap.dedent(
                """
                [project]
                dependencies = [
                  "requests>=2.31",
                  "django==4.2",
                  "uvicorn[standard]>=0.20",
                ]

                [project.optional-dependencies]
                dev = ["pytest>=7"]

                [dependency-groups]
                lint = ["ruff>=0.1"]

                [tool.poetry.dependencies]
                python = ">=3.11"
                rich = "^13.0"
                tomli = {version = "^2.0"}
                """
            ).strip()
        )

        resolver = PythonResolver()
        packages = await resolver.parse_manifest(str(manifest))

        names = {p.name for p in packages}
        assert "python" not in names
        assert "tomli" not in names
        assert {"requests", "django", "uvicorn", "pytest", "ruff", "rich"} <= names

    async def test_parse_manifest_pipfile_invalid_toml(self, tmp_path):
        """Test parsing Pipfile with invalid TOML."""
        manifest = tmp_path / "Pipfile"
        manifest.write_text("not = [toml")

        resolver = PythonResolver()
        packages = await resolver.parse_manifest(str(manifest))

        assert packages == []

    async def test_parse_manifest_pipfile(self, tmp_path):
        """Test parsing Pipfile."""
        manifest = tmp_path / "Pipfile"
        manifest.write_text(
            textwrap.dedent(
                """
                [packages]
                requests = "*"
                flask = ">=2.0"

                [dev-packages]
                pytest = "*"
                """
            ).strip()
        )

        resolver = PythonResolver()
        packages = await resolver.parse_manifest(str(manifest))

        names = {p.name for p in packages}
        assert names == {"requests", "flask", "pytest"}

    async def test_parse_manifest_pyproject_missing_tomllib(
        self, tmp_path, monkeypatch
    ):
        """Test parsing pyproject.toml without TOML parsers."""
        manifest = tmp_path / "pyproject.toml"
        manifest.write_text('[project]\nname = "demo"\n')

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"tomllib", "tomli"}:
                raise ImportError("missing")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        packages = await PythonResolver._parse_manifest_pyproject(manifest)

        assert packages == []

    async def test_parse_manifest_pipfile_missing_tomllib(self, tmp_path, monkeypatch):
        """Test parsing Pipfile without TOML parsers."""
        manifest = tmp_path / "Pipfile"
        manifest.write_text('[packages]\nrequests = "*"\n')

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"tomllib", "tomli"}:
                raise ImportError("missing")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        packages = await PythonResolver._parse_manifest_pipfile(manifest)

        assert packages == []

    async def test_parse_lockfile_poetry_missing_tomllib(self, tmp_path, monkeypatch):
        """Test parsing poetry.lock without TOML parsers."""
        lockfile = tmp_path / "poetry.lock"
        lockfile.write_text('[[package]]\nname = "requests"\n')

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"tomllib", "tomli"}:
                raise ImportError("missing")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        packages = await PythonResolver._parse_lockfile_poetry(lockfile)

        assert packages == []

    async def test_parse_lockfile_uv_missing_tomllib(self, tmp_path, monkeypatch):
        """Test parsing uv.lock without TOML parsers."""
        lockfile = tmp_path / "uv.lock"
        lockfile.write_text('[[package]]\nname = "fastapi"\n')

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"tomllib", "tomli"}:
                raise ImportError("missing")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        packages = await PythonResolver._parse_lockfile_uv(lockfile)

        assert packages == []
