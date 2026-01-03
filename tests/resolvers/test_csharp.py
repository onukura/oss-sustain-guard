"""
Tests for C# resolver.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.csharp import CSharpResolver


class TestCSharpResolver:
    """Test CSharpResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = CSharpResolver()
        assert resolver.ecosystem_name == "csharp"

    async def test_get_manifest_files(self):
        """Test manifest files for C#."""
        resolver = CSharpResolver()
        manifests = await resolver.get_manifest_files()
        assert "*.csproj" in manifests
        assert "*.vbproj" in manifests
        assert "packages.config" in manifests
        assert "packages.lock.json" in manifests

    @patch("oss_sustain_guard.resolvers.csharp._get_async_http_client")
    async def test_resolve_github_url_success(self, mock_get_client):
        """Test resolving GitHub URL from NuGet."""
        mock_client_inst = MagicMock()
        mock_get_client.return_value = mock_client_inst

        # Create response mocks for flat container API
        versions_response = MagicMock()
        versions_response.raise_for_status = MagicMock()
        versions_response.json.return_value = {"versions": ["1.0.0", "2.0.0", "3.14.0"]}

        nuspec_response = MagicMock()
        nuspec_response.raise_for_status = MagicMock()
        nuspec_response.text = (
            '<?xml version="1.0"?>'
            "<package>"
            '<repository url="https://github.com/JamesNK/Newtonsoft.Json" />'
            "</package>"
        )

        # Setup async mocks for get method
        mock_client_inst.get = AsyncMock(
            side_effect=[versions_response, nuspec_response]
        )

        resolver = CSharpResolver()
        result = await resolver.resolve_github_url("Newtonsoft.Json")
        assert result == ("JamesNK", "Newtonsoft.Json")

    @patch("oss_sustain_guard.resolvers.csharp._get_async_http_client")
    async def test_resolve_github_url_missing_repo(self, mock_get_client):
        """Test resolving NuGet package with no repository entry."""
        mock_client_inst = MagicMock()
        mock_get_client.return_value = mock_client_inst

        versions_response = MagicMock()
        versions_response.raise_for_status = MagicMock()
        versions_response.json.return_value = {"versions": ["1.0.0"]}

        nuspec_response = MagicMock()
        nuspec_response.raise_for_status = MagicMock()
        nuspec_response.text = '<?xml version="1.0"?><package></package>'

        mock_client_inst.get = AsyncMock(
            side_effect=[versions_response, nuspec_response]
        )

        resolver = CSharpResolver()
        result = await resolver.resolve_github_url("NoRepo")
        assert result is None

    @patch("oss_sustain_guard.resolvers.csharp._get_async_http_client")
    async def test_resolve_github_url_not_found(self, mock_get_client):
        """Test resolving package not in NuGet."""
        mock_client_inst = MagicMock()
        mock_get_client.return_value = mock_client_inst

        # Create response mocks
        index_response = MagicMock()
        index_response.raise_for_status = MagicMock()
        index_response.json.return_value = {
            "resources": [
                {
                    "@type": "RegistrationBaseUrl/3.6.0",
                    "@id": "https://api.nuget.org/v3/registration5-semver1/",
                }
            ]
        }

        pkg_response = MagicMock()
        pkg_response.raise_for_status = MagicMock()
        pkg_response.json.return_value = {"items": []}

        mock_client_inst.get = AsyncMock(side_effect=[index_response, pkg_response])

        resolver = CSharpResolver()
        result = await resolver.resolve_github_url("NonExistentPackage")
        assert result is None

    @patch("oss_sustain_guard.resolvers.csharp._get_async_http_client")
    async def test_resolve_github_url_network_error(self, mock_get_client):
        """Test resolving with network error."""
        import httpx

        mock_client_inst = MagicMock()
        mock_get_client.return_value = mock_client_inst
        mock_client_inst.get = AsyncMock(
            side_effect=httpx.RequestError("Network error")
        )

        resolver = CSharpResolver()
        result = await resolver.resolve_github_url("Newtonsoft.Json")
        assert result is None

    async def test_detect_lockfiles(self, tmp_path):
        """Test detecting C# lockfiles."""
        (tmp_path / "packages.lock.json").touch()
        (tmp_path / "other.txt").touch()

        resolver = CSharpResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) >= 1
        assert any(lf.name == "packages.lock.json" for lf in lockfiles)

    async def test_detect_lockfiles_nested(self, tmp_path):
        """Test detecting nested packages.lock.json files."""
        (tmp_path / "packages.lock.json").touch()
        nested = tmp_path / "src" / "proj"
        nested.mkdir(parents=True)
        (nested / "packages.lock.json").touch()

        resolver = CSharpResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) == 2
        assert {lf.parent.name for lf in lockfiles} == {"proj", tmp_path.name}

    async def test_parse_lockfile_success(self, tmp_path):
        """Test parsing valid packages.lock.json."""
        lockfile = tmp_path / "packages.lock.json"
        lockfile.write_text(
            """{
            "version": 2,
            "dependencies": {
                ".NETFramework,Version=v4.7.2": {
                    "Newtonsoft.Json": {
                        "type": "Direct",
                        "requested": "13.0.0",
                        "resolved": "13.0.0"
                    },
                    "Microsoft.Extensions.Logging": {
                        "type": "Transitive",
                        "resolved": "5.0.0"
                    }
                }
            }
        }"""
        )

        resolver = CSharpResolver()
        packages = await resolver.parse_lockfile(str(lockfile))

        assert len(packages) == 2
        assert packages[0].name == "Newtonsoft.Json"
        assert packages[0].version == "13.0.0"
        assert packages[0].ecosystem == "csharp"
        assert packages[1].name == "Microsoft.Extensions.Logging"
        assert packages[1].version == "5.0.0"

    async def test_parse_lockfile_not_found(self):
        """Test parsing non-existent lockfile."""
        resolver = CSharpResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_lockfile("/nonexistent/packages.lock.json")

    async def test_parse_lockfile_invalid_json(self, tmp_path):
        """Test parsing invalid JSON lockfile."""
        lockfile = tmp_path / "packages.lock.json"
        lockfile.write_text("{ invalid json }")

        resolver = CSharpResolver()
        with pytest.raises(ValueError):
            await resolver.parse_lockfile(str(lockfile))

    async def test_parse_manifest_csproj(self, tmp_path):
        """Test parsing .csproj manifest."""
        manifest = tmp_path / "example.csproj"
        manifest.write_text(
            "<Project>"
            "<ItemGroup>"
            '<PackageReference Include="Newtonsoft.Json" Version="13.0.0" />'
            '<PackageReference Include="Serilog" />'
            "</ItemGroup>"
            "</Project>"
        )

        resolver = CSharpResolver()
        packages = await resolver.parse_manifest(str(manifest))

        assert len(packages) == 2
        assert packages[0].name == "Newtonsoft.Json"
        assert packages[0].version == "13.0.0"
        assert packages[1].name == "Serilog"

    async def test_parse_manifest_csproj_invalid(self, tmp_path):
        """Test parsing invalid .csproj manifest."""
        manifest = tmp_path / "broken.csproj"
        manifest.write_text("<Project><ItemGroup>")

        resolver = CSharpResolver()
        with pytest.raises(ValueError, match="Failed to parse project file"):
            await resolver.parse_manifest(str(manifest))

    async def test_parse_manifest_packages_config(self, tmp_path):
        """Test parsing packages.config manifest."""
        manifest = tmp_path / "packages.config"
        manifest.write_text(
            "<packages>"
            '<package id="NUnit" version="3.12.0" />'
            '<package id="Moq" version="4.18.4" />'
            "</packages>"
        )

        resolver = CSharpResolver()
        packages = await resolver.parse_manifest(str(manifest))

        assert len(packages) == 2
        assert packages[0].name == "NUnit"
        assert packages[1].version == "4.18.4"

    async def test_parse_manifest_packages_config_invalid(self, tmp_path):
        """Test parsing invalid packages.config manifest."""
        manifest = tmp_path / "packages.config"
        manifest.write_text("<packages><package id='NUnit'>")

        resolver = CSharpResolver()
        with pytest.raises(ValueError, match="Failed to parse packages.config"):
            await resolver.parse_manifest(str(manifest))

    def test_parse_repository_url_github(self):
        """Test parsing valid GitHub URL."""
        from oss_sustain_guard.repository import parse_repository_url

        result = parse_repository_url("https://github.com/JamesNK/Newtonsoft.Json")
        assert result is not None
        assert result.provider == "github"
        assert result.owner == "JamesNK"
        assert result.name == "Newtonsoft.Json"

    def test_parse_repository_url_github_with_git_suffix(self):
        """Test parsing GitHub URL with .git suffix."""
        from oss_sustain_guard.repository import parse_repository_url

        result = parse_repository_url("https://github.com/JamesNK/Newtonsoft.Json.git")
        assert result is not None
        assert result.provider == "github"
        assert result.owner == "JamesNK"
        assert result.name == "Newtonsoft.Json"

    def test_parse_repository_url_gitlab(self):
        """Test parsing GitLab URL."""
        from oss_sustain_guard.repository import parse_repository_url

        result = parse_repository_url("https://gitlab.com/user/repo")
        assert result is not None
        assert result.provider == "gitlab"
        assert result.owner == "user"
        assert result.name == "repo"

    def test_parse_repository_url_invalid(self):
        """Test parsing invalid URL."""
        from oss_sustain_guard.repository import parse_repository_url

        assert parse_repository_url("") is None
