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

    def test_resolve_repository_direct_url(self):
        """Test resolving repository for direct URL."""
        resolver = SwiftResolver()
        repo = resolver.resolve_repository("https://github.com/apple/swift-nio")
        assert repo is not None
        assert repo.owner == "apple"
        assert repo.name == "swift-nio"

    def test_resolve_repository_owner_repo(self):
        """Test resolving repository for owner/repo input."""
        resolver = SwiftResolver()
        repo = resolver.resolve_repository("apple/swift-nio")
        assert repo is not None
        assert repo.owner == "apple"
        assert repo.name == "swift-nio"

    def test_parse_lockfile(self, tmp_path):
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
        packages = resolver.parse_lockfile(lockfile)

        assert len(packages) == 1
        assert packages[0].name == "apple/swift-nio"
        assert packages[0].version == "2.56.0"

    def test_parse_lockfile_not_found(self):
        """Test parsing missing lockfile."""
        resolver = SwiftResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/missing/Package.resolved")

    def test_parse_lockfile_unknown(self, tmp_path):
        """Test parsing unknown lockfile type."""
        unknown = tmp_path / "unknown.lock"
        unknown.touch()

        resolver = SwiftResolver()
        with pytest.raises(ValueError, match="Unknown Swift lockfile type"):
            resolver.parse_lockfile(unknown)

    def test_parse_manifest(self, tmp_path):
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
        packages = resolver.parse_manifest(manifest)
        assert len(packages) == 1
        assert packages[0].name == "apple/swift-nio"

    def test_parse_manifest_not_found(self):
        """Test missing manifest."""
        resolver = SwiftResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_manifest("/missing/Package.swift")

    def test_parse_manifest_unknown(self, tmp_path):
        """Test unknown manifest type."""
        unknown = tmp_path / "unknown.swift"
        unknown.touch()

        resolver = SwiftResolver()
        with pytest.raises(ValueError, match="Unknown Swift manifest file type"):
            resolver.parse_manifest(unknown)
