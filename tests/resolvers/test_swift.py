"""
Tests for Swift resolver.
"""

import json

import pytest

from oss_sustain_guard.resolvers.swift import SwiftResolver


class TestSwiftResolver:
    """Test SwiftResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = SwiftResolver()
        assert resolver.ecosystem_name == "swift"

    async def test_resolve_repository_direct_url(self):
        """Test resolving repository for direct URL."""
        resolver = SwiftResolver()
        repo = await resolver.resolve_repository("https://github.com/apple/swift-nio")
        assert repo is not None
        assert repo.owner == "apple"
        assert repo.name == "swift-nio"

    async def test_resolve_repository_owner_repo(self):
        """Test resolving repository for owner/repo input."""
        resolver = SwiftResolver()
        repo = await resolver.resolve_repository("apple/swift-nio")
        assert repo is not None
        assert repo.owner == "apple"
        assert repo.name == "swift-nio"

    async def test_resolve_repository_empty(self):
        """Test resolving empty package name."""
        resolver = SwiftResolver()
        assert await resolver.resolve_repository("  ") is None

    async def test_resolve_repository_git_ssh(self):
        """Test resolving repository for git SSH URL."""
        resolver = SwiftResolver()
        repo = await resolver.resolve_repository("git@github.com:apple/swift-nio.git")
        assert repo is not None
        assert repo.owner == "apple"
        assert repo.name == "swift-nio"

    async def test_resolve_repository_host_path(self):
        """Test resolving repository for host/path input."""
        resolver = SwiftResolver()
        repo = await resolver.resolve_repository("github.com/apple/swift-nio")
        assert repo is not None
        assert repo.owner == "apple"
        assert repo.name == "swift-nio"

    async def test_resolve_repository_invalid(self):
        """Test resolving repository for invalid input."""
        resolver = SwiftResolver()
        assert await resolver.resolve_repository("swift-nio") is None

    async def test_parse_lockfile(self, tmp_path):
        """Test parsing Package.resolved."""
        payload = {
            "object": {
                "pins": [
                    {
                        "location": "https://github.com/apple/swift-nio.git",
                        "state": {"version": "2.56.0"},
                    }
                ]
            }
        }
        lockfile = tmp_path / "Package.resolved"
        lockfile.write_text(json.dumps(payload))

        resolver = SwiftResolver()
        packages = await resolver.parse_lockfile(lockfile)

        assert len(packages) == 1
        assert packages[0].name == "apple/swift-nio"
        assert packages[0].version == "2.56.0"

    async def test_parse_lockfile_invalid_json(self, tmp_path):
        """Test parsing invalid Package.resolved."""
        lockfile = tmp_path / "Package.resolved"
        lockfile.write_text("{ invalid json }")

        resolver = SwiftResolver()
        with pytest.raises(ValueError, match="Failed to parse Package.resolved"):
            await resolver.parse_lockfile(lockfile)

    async def test_parse_lockfile_skips_invalid_pins(self, tmp_path):
        """Test parsing Package.resolved with invalid pin entries."""
        payload = {
            "pins": [
                "not-a-dict",
                {"location": None},
                {
                    "repositoryURL": "https://github.com/apple/swift-collections.git",
                    "state": {"version": "1.0.5"},
                },
            ]
        }
        lockfile = tmp_path / "Package.resolved"
        lockfile.write_text(json.dumps(payload))

        resolver = SwiftResolver()
        packages = await resolver.parse_lockfile(lockfile)

        assert len(packages) == 1
        assert packages[0].name == "apple/swift-collections"

    async def test_parse_lockfile_not_found(self):
        """Test parsing missing lockfile."""
        resolver = SwiftResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_lockfile("/missing/Package.resolved")

    async def test_parse_lockfile_unknown(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown = tmp_path / "unknown.lock"
        unknown.touch()

        resolver = SwiftResolver()
        with pytest.raises(ValueError, match="Unknown Swift lockfile type"):
            await resolver.parse_lockfile(unknown)

    async def test_parse_manifest(self, tmp_path):
        """Test parsing Package.swift."""
        manifest = tmp_path / "Package.swift"
        manifest.write_text(
            """
            // swift-tools-version:5.7
            import PackageDescription

            let package = Package(
                name: "Example",
                dependencies: [
                    .package(url: "https://github.com/apple/swift-nio.git", from: "2.56.0"),
                ]
            )
            """
        )

        resolver = SwiftResolver()
        packages = await resolver.parse_manifest(manifest)
        assert len(packages) == 1
        assert packages[0].name == "apple/swift-nio"

    async def test_parse_manifest_duplicates(self, tmp_path):
        """Test parsing Package.swift with duplicate URLs."""
        manifest = tmp_path / "Package.swift"
        manifest.write_text(
            "let package = Package(dependencies: [\n"
            '  .package(url: "https://github.com/apple/swift-nio.git", from: "2.56.0"),\n'
            '  .package(url: "https://github.com/apple/swift-nio.git", from: "2.56.0")\n'
            "])\n"
        )

        resolver = SwiftResolver()
        packages = await resolver.parse_manifest(manifest)

        assert len(packages) == 1
        assert packages[0].name == "apple/swift-nio"

    async def test_parse_manifest_not_found(self):
        """Test missing manifest."""
        resolver = SwiftResolver()
        with pytest.raises(FileNotFoundError):
            await resolver.parse_manifest("/missing/Package.swift")

    async def test_parse_manifest_unknown(self, tmp_path):
        """Test unknown manifest type."""
        unknown = tmp_path / "unknown.swift"
        unknown.touch()

        resolver = SwiftResolver()
        with pytest.raises(ValueError, match="Unknown Swift manifest file type"):
            await resolver.parse_manifest(unknown)

    async def test_parse_manifest_read_error(self, tmp_path, monkeypatch):
        """Test error reading Package.swift."""
        manifest = tmp_path / "Package.swift"
        manifest.write_text("let package = Package(dependencies: [])\n")

        def _raise(*_args, **_kwargs):
            raise OSError("read error")

        monkeypatch.setattr("aiofiles.open", _raise)

        resolver = SwiftResolver()
        with pytest.raises(ValueError, match="Failed to read Package.swift"):
            await resolver.parse_manifest(manifest)
