"""
Tests for JavaScript resolver.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.javascript import JavaScriptResolver


class TestJavaScriptResolver:
    """Test JavaScriptResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = JavaScriptResolver()
        assert resolver.ecosystem_name == "javascript"

    async def test_get_manifest_files(self):
        """Test manifest files for JavaScript."""
        resolver = JavaScriptResolver()
        manifests = await resolver.get_manifest_files()
        assert "package.json" in manifests

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_success(self, mock_get):
        """Test resolving GitHub URL from npm registry."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": {
                "type": "git",
                "url": "git+https://github.com/facebook/react.git",
            }
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = await resolver.resolve_repository("react")
        assert result and result.owner == "facebook" and result.name == "react"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_string_repo(self, mock_get):
        """Test resolving when repository is a string."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": "https://github.com/lodash/lodash"
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = await resolver.resolve_repository("lodash")
        assert result and result.owner == "lodash" and result.name == "lodash"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_homepage_fallback(self, mock_get):
        """Test fallback to homepage field."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": {},
            "homepage": "https://github.com/vuejs/vue",
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = await resolver.resolve_repository("vue")
        assert result and result.owner == "vuejs" and result.name == "vue"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_not_found(self, mock_get):
        """Test resolving package with no GitHub URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": {},
            "homepage": "https://example.com",
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = await resolver.resolve_repository("some-package")
        assert result is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_url_network_error(self, mock_get):
        """Test resolving with network error."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = JavaScriptResolver()
        result = await resolver.resolve_repository("react")
        assert result is None

    async def test_detect_lockfiles(self, tmp_path):
        """Test detecting JavaScript lockfiles."""
        (tmp_path / "package-lock.json").touch()
        (tmp_path / "package.json").touch()

        resolver = JavaScriptResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) == 1
        assert lockfiles[0].name == "package-lock.json"

    async def test_detect_lockfiles_yarn(self, tmp_path):
        """Test detecting yarn.lock."""
        (tmp_path / "yarn.lock").touch()

        resolver = JavaScriptResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) == 1
        assert lockfiles[0].name == "yarn.lock"

    async def test_parse_package_lock(self, tmp_path):
        """Test parsing package-lock.json."""
        package_lock = {
            "dependencies": {
                "react": {"version": "18.2.0"},
                "lodash": {"version": "4.17.21"},
            }
        }
        lock_file = tmp_path / "package-lock.json"
        lock_file.write_text(json.dumps(package_lock))

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))

        assert len(packages) >= 2
        names = {p.name for p in packages}
        assert "react" in names
        assert "lodash" in names
        assert all(p.ecosystem == "javascript" for p in packages)

    async def test_parse_yarn_lock(self, tmp_path):
        """Test parsing yarn.lock."""
        yarn_content = """# THIS IS A GENERATED FILE
"react@^18.0.0":
  version "18.2.0"
  dependencies:
    react-dom: "^18.0.0"

"lodash@^4.17.0":
  version "4.17.21"
"""
        lock_file = tmp_path / "yarn.lock"
        lock_file.write_text(yarn_content)

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))

        assert len(packages) >= 1
        names = {p.name for p in packages}
        assert "react" in names
        assert all(p.ecosystem == "javascript" for p in packages)

    async def test_parse_lockfile_not_found(self):
        """Test parsing non-existent lockfile."""
        resolver = JavaScriptResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_lockfile("/nonexistent/package-lock.json")

    async def test_parse_lockfile_unknown_type(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown_lock = tmp_path / "unknown.lock"
        unknown_lock.touch()

        resolver = JavaScriptResolver()
        with pytest.raises(ValueError, match="Unknown JavaScript lockfile type"):
            await resolver.parse_lockfile(str(unknown_lock))

    @patch("httpx.AsyncClient.get")
    async def test_resolve_github_prefix(self, mock_get):
        """Test resolving repository with github: prefix."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": {"url": "github:facebook/react"}
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = await resolver.resolve_repository("react")
        assert result and result.owner == "facebook" and result.name == "react"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_gitlab_prefix(self, mock_get):
        """Test resolving repository with gitlab: prefix."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": {"url": "gitlab:gitlab-org/gitlab"}
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = await resolver.resolve_repository("gitlab")
        # GitLab is supported, check correct parsing
        assert result and result.provider == "gitlab"
        assert result.owner == "gitlab-org" and result.name == "gitlab"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_git_protocol(self, mock_get):
        """Test resolving repository with git:// protocol."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": {"url": "git://github.com/jquery/jquery.git"}
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = await resolver.resolve_repository("jquery")
        assert result and result.owner == "jquery" and result.name == "jquery"

    @patch("httpx.AsyncClient.get")
    async def test_resolve_http_status_error(self, mock_get):
        """Test resolving with HTTP status error."""
        import httpx

        mock_get.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock()
        )

        resolver = JavaScriptResolver()
        result = await resolver.resolve_repository("nonexistent-package")
        assert result is None

    async def test_parse_pnpm_lock(self, tmp_path):
        """Test parsing pnpm-lock.yaml."""
        pnpm_content = """lockfileVersion: '6.0'
dependencies:
  react:
    specifier: ^18.2.0
    version: 18.2.0
  lodash:
    specifier: ^4.17.21
    version: 4.17.21
packages:
  /react@18.2.0:
    dependencies:
      loose-envify: 1.4.0
  /lodash@4.17.21:
"""
        lock_file = tmp_path / "pnpm-lock.yaml"
        lock_file.write_text(pnpm_content)

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))

        assert len(packages) >= 1
        names = {p.name for p in packages}
        assert "react" in names or "lodash" in names
        assert all(p.ecosystem == "javascript" for p in packages)

    async def test_detect_lockfiles_pnpm(self, tmp_path):
        """Test detecting pnpm-lock.yaml."""
        (tmp_path / "pnpm-lock.yaml").touch()

        resolver = JavaScriptResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) == 1
        assert lockfiles[0].name == "pnpm-lock.yaml"

    async def test_detect_lockfiles_multiple(self, tmp_path):
        """Test detecting multiple lockfiles."""
        (tmp_path / "package-lock.json").touch()
        (tmp_path / "yarn.lock").touch()
        (tmp_path / "pnpm-lock.yaml").touch()

        resolver = JavaScriptResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) == 3
        names = {lf.name for lf in lockfiles}
        assert "package-lock.json" in names
        assert "yarn.lock" in names
        assert "pnpm-lock.yaml" in names

    async def test_parse_manifest_package_json(self, tmp_path):
        """Test parsing package.json manifest."""
        package_json = {
            "name": "my-project",
            "dependencies": {"react": "^18.2.0", "lodash": "^4.17.21"},
            "devDependencies": {"typescript": "^5.0.0"},
            "optionalDependencies": {"fsevents": "^2.3.2"},
            "peerDependencies": {"react-dom": "^18.2.0"},
        }
        manifest_file = tmp_path / "package.json"
        manifest_file.write_text(json.dumps(package_json))

        resolver = JavaScriptResolver()
        packages = await resolver.parse_manifest(str(manifest_file))

        assert len(packages) == 5
        names = {p.name for p in packages}
        assert "react" in names
        assert "lodash" in names
        assert "typescript" in names
        assert "fsevents" in names
        assert "react-dom" in names
        assert all(p.ecosystem == "javascript" for p in packages)

    async def test_parse_manifest_not_found(self):
        """Test parsing non-existent manifest."""
        resolver = JavaScriptResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_manifest("/nonexistent/package.json")

    async def test_parse_manifest_unknown_type(self, tmp_path):
        """Test parsing unknown manifest type."""
        unknown_manifest = tmp_path / "unknown.json"
        unknown_manifest.touch()

        resolver = JavaScriptResolver()
        with pytest.raises(ValueError, match="Unknown JavaScript manifest file type"):
            await resolver.parse_manifest(str(unknown_manifest))

    async def test_parse_manifest_invalid_json(self, tmp_path):
        """Test parsing invalid JSON manifest."""
        manifest_file = tmp_path / "package.json"
        manifest_file.write_text("{ invalid json }")

        resolver = JavaScriptResolver()
        with pytest.raises(ValueError, match="Failed to parse package.json"):
            await resolver.parse_manifest(str(manifest_file))

    async def test_parse_package_lock_with_packages_field(self, tmp_path):
        """Test parsing package-lock.json with packages field (v3 format)."""
        package_lock = {
            "lockfileVersion": 3,
            "dependencies": {"react": {"version": "18.2.0"}},
            "packages": {
                "": {"name": "my-project"},
                "node_modules/react": {"version": "18.2.0"},
                "node_modules/lodash": {"version": "4.17.21"},
            },
        }
        lock_file = tmp_path / "package-lock.json"
        lock_file.write_text(json.dumps(package_lock))

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))

        names = {p.name for p in packages}
        assert "react" in names
        assert "lodash" in names

    async def test_parse_yarn_lock_scoped_package(self, tmp_path):
        """Test parsing yarn.lock with scoped packages."""
        yarn_content = """# THIS IS A GENERATED FILE
"@babel/core@^7.0.0":
  version "7.22.5"

"@types/node@^20.0.0":
  version "20.3.1"
"""
        lock_file = tmp_path / "yarn.lock"
        lock_file.write_text(yarn_content)

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))

        names = {p.name for p in packages}
        # Parser returns full scoped package names
        assert "@babel/core" in names or "@types/node" in names

    async def test_parse_yarn_lock_with_comments(self, tmp_path):
        """Test parsing yarn.lock with comments."""
        yarn_content = """# THIS IS A GENERATED FILE
# yarn lockfile v1

"react@^18.0.0":
  version "18.2.0"
  # Some comment
  dependencies:
    react-dom: "^18.0.0"
"""
        lock_file = tmp_path / "yarn.lock"
        lock_file.write_text(yarn_content)

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))

        names = {p.name for p in packages}
        assert "react" in names

    async def test_parse_package_lock_malformed(self, tmp_path):
        """Test parsing malformed package-lock.json returns empty list."""
        lock_file = tmp_path / "package-lock.json"
        lock_file.write_text("{ invalid json }")

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))
        assert packages == []

    async def test_parse_yarn_lock_malformed(self, tmp_path):
        """Test parsing malformed yarn.lock returns empty list."""
        lock_file = tmp_path / "yarn.lock"
        # Create a file that will cause an exception during parsing
        lock_file.write_bytes(b"\xff\xfe")

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))
        assert packages == []

    async def test_parse_pnpm_lock_malformed(self, tmp_path):
        """Test parsing malformed pnpm-lock.yaml returns empty list."""
        lock_file = tmp_path / "pnpm-lock.yaml"
        lock_file.write_text("invalid: yaml: content: [")

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))
        assert packages == []

    async def test_parse_package_json_non_dict_dependencies(self, tmp_path):
        """Test parsing package.json with non-dict dependencies."""
        package_json = {
            "name": "my-project",
            "dependencies": "invalid",
            "devDependencies": {"typescript": "^5.0.0"},
        }
        manifest_file = tmp_path / "package.json"
        manifest_file.write_text(json.dumps(package_json))

        resolver = JavaScriptResolver()
        packages = await resolver.parse_manifest(str(manifest_file))

        # Should only include devDependencies
        assert len(packages) == 1
        assert packages[0].name == "typescript"

    async def test_parse_package_json_non_string_version(self, tmp_path):
        """Test parsing package.json with non-string version."""
        package_json = {
            "name": "my-project",
            "dependencies": {"react": {"version": "18.2.0"}},
        }
        manifest_file = tmp_path / "package.json"
        manifest_file.write_text(json.dumps(package_json))

        resolver = JavaScriptResolver()
        packages = await resolver.parse_manifest(str(manifest_file))

        assert len(packages) == 1
        assert packages[0].name == "react"
        assert packages[0].version is None

    @patch("httpx.AsyncClient.get")
    async def test_resolve_homepage_non_string(self, mock_get):
        """Test resolving when homepage is not a string."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "repository": {},
            "homepage": ["https://github.com/vuejs/vue"],
        }
        mock_get.return_value = mock_response

        resolver = JavaScriptResolver()
        result = await resolver.resolve_repository("vue")
        assert result is None

    async def test_parse_pnpm_lock_with_packages_section(self, tmp_path):
        """Test parsing pnpm-lock.yaml with packages section."""
        pnpm_content = """lockfileVersion: '6.0'
dependencies:
  react:
    specifier: ^18.2.0
    version: 18.2.0
packages:
  /react@18.2.0_abc123:
    resolution: {integrity: sha512-...}
  /lodash@4.17.21:
    resolution: {integrity: sha512-...}
"""
        lock_file = tmp_path / "pnpm-lock.yaml"
        lock_file.write_text(pnpm_content)

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))

        names = {p.name for p in packages}
        assert "react" in names or "lodash" in names

    async def test_parse_pnpm_lock_v9_format(self, tmp_path):
        """Test parsing pnpm-lock.yaml v9 format with versioned package keys."""
        pnpm_content = """lockfileVersion: '9.0'
dependencies:
  react:
    specifier: ^18.2.0
    version: 18.3.1
packages:
  accepts@1.3.8:
    resolution: {integrity: sha512-...}
  acorn@8.15.0:
    resolution: {integrity: sha512-...}
  '@babel/core@7.28.5':
    resolution: {integrity: sha512-...}
  '@types/react@18.3.27':
    resolution: {integrity: sha512-...}
"""
        lock_file = tmp_path / "pnpm-lock.yaml"
        lock_file.write_text(pnpm_content)

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))

        names = {p.name for p in packages}
        # Verify package names are extracted without version numbers
        assert "accepts" in names
        assert "acorn" in names
        assert "@babel/core" in names
        assert "@types/react" in names
        # Ensure versioned names are not included
        assert "accepts@1.3.8" not in names
        assert "@babel/core@7.28.5" not in names

    async def test_parse_pnpm_lock_non_dict_packages(self, tmp_path):
        """Test parsing pnpm-lock.yaml with non-dict packages."""
        pnpm_content = """lockfileVersion: '6.0'
dependencies: invalid
packages: []
"""
        lock_file = tmp_path / "pnpm-lock.yaml"
        lock_file.write_text(pnpm_content)

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))
        # Should return empty list or handle gracefully
        assert isinstance(packages, list)

    async def test_parse_deno_lock(self, tmp_path):
        """Test parsing deno.lock file."""
        deno_lock_content = {
            "version": "5",
            "specifiers": {
                "npm:react@^18.2.0": "18.3.1",
                "npm:lodash@^4.17.21": "4.17.21",
                "npm:@types/react@^18.2.0": "18.3.27",
            },
            "npm": {},
        }
        lock_file = tmp_path / "deno.lock"
        lock_file.write_text(json.dumps(deno_lock_content))

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))

        names = {p.name for p in packages}
        assert "react" in names
        assert "lodash" in names
        assert "@types/react" in names
        assert len(packages) == 3

    async def test_parse_deno_json(self, tmp_path):
        """Test parsing deno.json file."""
        deno_json_content = {
            "name": "test-project",
            "version": "1.0.0",
            "imports": {
                "react": "npm:react@^18.2.0",
                "lodash": "npm:lodash@^4.17.21",
                "@types/react": "npm:@types/react@^18.2.0",
            },
        }
        manifest_file = tmp_path / "deno.json"
        manifest_file.write_text(json.dumps(deno_json_content))

        resolver = JavaScriptResolver()
        packages = await resolver.parse_manifest(str(manifest_file))

        names = {p.name for p in packages}
        assert "react" in names
        assert "lodash" in names
        assert "@types/react" in names
        assert len(packages) == 3

    async def test_parse_deno_lock_legacy_format(self, tmp_path):
        """Test parsing deno.lock in legacy format with remote section."""
        deno_lock_content = {
            "version": "4",
            "remote": {
                "https://registry.npmjs.org/react/18.3.1/": {"integrity": "..."},
            },
        }
        lock_file = tmp_path / "deno.lock"
        lock_file.write_text(json.dumps(deno_lock_content))

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(lock_file))
        assert isinstance(packages, list)

    async def test_get_manifest_files_includes_deno_json(self):
        """Test that manifest files include deno.json."""
        resolver = JavaScriptResolver()
        manifests = await resolver.get_manifest_files()
        assert "package.json" in manifests
        assert "deno.json" in manifests

    async def test_detect_lockfiles_includes_deno_lock(self, tmp_path):
        """Test that detect_lockfiles includes deno.lock."""
        # Create deno.lock file
        deno_lock = tmp_path / "deno.lock"
        deno_lock.write_text("{}")

        resolver = JavaScriptResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        assert str(deno_lock) in [str(f) for f in lockfiles]

    async def test_parse_bun_lock_json(self, tmp_path):
        """Test parsing bun.lock file (JSON format)."""
        bun_lock_content = {
            "lockfileVersion": 1,
            "configVersion": 1,
            "workspaces": {
                "": {
                    "name": "test-project",
                    "dependencies": {
                        "react": "^18.2.0",
                        "lodash": "^4.17.21",
                    },
                    "devDependencies": {
                        "@types/react": "^18.2.0",
                    },
                }
            },
            "packages": {},
        }
        bun_lock = tmp_path / "bun.lock"
        bun_lock.write_text(json.dumps(bun_lock_content))

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(bun_lock))

        names = {p.name for p in packages}
        assert "react" in names
        assert "lodash" in names
        assert "@types/react" in names

    async def test_parse_bun_lock_binary(self, tmp_path):
        """Test parsing bun.lockb file (binary format)."""
        # Create a minimal bun.lockb-like binary file with npm package names
        bun_lockb_content = (
            b"\x00\x00npm:react@18.3.1\x00\x00npm:lodash@4.17.21\x00\x00"
        )
        bun_lockb = tmp_path / "bun.lockb"
        bun_lockb.write_bytes(bun_lockb_content)

        resolver = JavaScriptResolver()
        packages = await resolver.parse_lockfile(str(bun_lockb))

        names = {p.name for p in packages}
        assert "react" in names
        assert "lodash" in names

    async def test_detect_lockfiles_includes_bun_lock_and_lockb(self, tmp_path):
        """Test that detect_lockfiles includes both bun.lock and bun.lockb."""
        # Create both bun.lock and bun.lockb files
        bun_lock = tmp_path / "bun.lock"
        bun_lockb = tmp_path / "bun.lockb"
        bun_lock.write_text("{}")
        bun_lockb.write_bytes(b"")

        resolver = JavaScriptResolver()
        lockfiles = await resolver.detect_lockfiles(str(tmp_path))

        lockfile_strs = [str(f) for f in lockfiles]
        assert str(bun_lock) in lockfile_strs
        assert str(bun_lockb) in lockfile_strs
