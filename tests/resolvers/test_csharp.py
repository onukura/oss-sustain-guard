"""
Tests for C# resolver.
"""

from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.csharp import CSharpResolver


class TestCSharpResolver:
    """Test CSharpResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = CSharpResolver()
        assert resolver.ecosystem_name == "csharp"

    def test_get_manifest_files(self):
        """Test manifest files for C#."""
        resolver = CSharpResolver()
        manifests = resolver.get_manifest_files()
        assert "*.csproj" in manifests
        assert "*.vbproj" in manifests
        assert "packages.config" in manifests
        assert "packages.lock.json" in manifests

    @patch("oss_sustain_guard.resolvers.csharp.httpx.Client")
    def test_resolve_github_url_success(self, mock_client_class):
        """Test resolving GitHub URL from NuGet."""
        mock_client_inst = MagicMock()
        mock_client_class.return_value = mock_client_inst

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

        # Setup context manager
        mock_client_inst.__enter__ = MagicMock(return_value=mock_client_inst)
        mock_client_inst.__exit__ = MagicMock(return_value=False)
        mock_client_inst.get.side_effect = [versions_response, nuspec_response]

        resolver = CSharpResolver()
        result = resolver.resolve_github_url("Newtonsoft.Json")
        assert result == ("JamesNK", "Newtonsoft.Json")

    @patch("oss_sustain_guard.resolvers.csharp.httpx.Client")
    def test_resolve_github_url_not_found(self, mock_client_class):
        """Test resolving package not in NuGet."""
        mock_client_inst = MagicMock()
        mock_client_class.return_value = mock_client_inst

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

        # Setup context manager
        mock_client_inst.__enter__ = MagicMock(return_value=mock_client_inst)
        mock_client_inst.__exit__ = MagicMock(return_value=False)
        mock_client_inst.get.side_effect = [index_response, pkg_response]

        resolver = CSharpResolver()
        result = resolver.resolve_github_url("NonExistentPackage")
        assert result is None

    @patch("httpx.Client.get")
    def test_resolve_github_url_network_error(self, mock_get):
        """Test resolving with network error."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = CSharpResolver()
        result = resolver.resolve_github_url("Newtonsoft.Json")
        assert result is None

    def test_detect_lockfiles(self, tmp_path):
        """Test detecting C# lockfiles."""
        (tmp_path / "packages.lock.json").touch()
        (tmp_path / "other.txt").touch()

        resolver = CSharpResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) >= 1
        assert any(lf.name == "packages.lock.json" for lf in lockfiles)

    def test_parse_lockfile_success(self, tmp_path):
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
        packages = resolver.parse_lockfile(str(lockfile))

        assert len(packages) == 2
        assert packages[0].name == "Newtonsoft.Json"
        assert packages[0].version == "13.0.0"
        assert packages[0].ecosystem == "csharp"
        assert packages[1].name == "Microsoft.Extensions.Logging"
        assert packages[1].version == "5.0.0"

    def test_parse_lockfile_not_found(self):
        """Test parsing non-existent lockfile."""
        resolver = CSharpResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/nonexistent/packages.lock.json")

    def test_parse_lockfile_invalid_json(self, tmp_path):
        """Test parsing invalid JSON lockfile."""
        lockfile = tmp_path / "packages.lock.json"
        lockfile.write_text("{ invalid json }")

        resolver = CSharpResolver()
        with pytest.raises(ValueError):
            resolver.parse_lockfile(str(lockfile))

    def test_parse_github_url_valid(self):
        """Test parsing valid GitHub URL."""
        resolver = CSharpResolver()
        result = resolver._parse_github_url(
            "https://github.com/JamesNK/Newtonsoft.Json"
        )
        assert result == ("JamesNK", "Newtonsoft.Json")

    def test_parse_github_url_with_git_suffix(self):
        """Test parsing GitHub URL with .git suffix."""
        resolver = CSharpResolver()
        result = resolver._parse_github_url(
            "https://github.com/JamesNK/Newtonsoft.Json.git"
        )
        assert result == ("JamesNK", "Newtonsoft.Json")

    def test_parse_github_url_non_github(self):
        """Test parsing non-GitHub URL."""
        resolver = CSharpResolver()
        result = resolver._parse_github_url("https://gitlab.com/user/repo")
        # Non-GitHub URLs still extract owner/repo, just not from GitHub
        assert result == ("user", "repo")

    def test_parse_github_url_invalid(self):
        """Test parsing invalid URL."""
        resolver = CSharpResolver()
        assert resolver._parse_github_url("") is None
