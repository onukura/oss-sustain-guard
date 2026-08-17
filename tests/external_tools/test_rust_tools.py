"""
Tests for the Rust (cargo) external tool.
"""

from oss_sustain_guard.dependency_graph import tomllib
from oss_sustain_guard.external_tools.rust_tools import build_cargo_manifest


class TestBuildCargoManifest:
    """Test the temporary Cargo.toml generated for dependency resolution."""

    def test_pinned_version_uses_cargo_requirement_syntax(self):
        """Regression test: the `=` operator belongs inside the version string.

        Emitting it outside produced `serde = = "1.0.0"`, which cargo rejected
        with "extra `=`, expected nothing" — every pinned resolution failed.
        """
        manifest = build_cargo_manifest("serde", "1.0.0")
        assert "serde = = " not in manifest
        assert tomllib.loads(manifest)["dependencies"] == {"serde": "=1.0.0"}

    def test_unpinned_version_accepts_any_release(self):
        manifest = build_cargo_manifest("serde")
        assert tomllib.loads(manifest)["dependencies"] == {"serde": "*"}

    def test_manifest_is_a_buildable_package(self):
        """cargo metadata needs a complete [package] section to run at all."""
        parsed = tomllib.loads(build_cargo_manifest("serde", "1.0.0"))
        assert parsed["package"]["name"] == "temp-os4g-trace"
        assert parsed["package"]["version"] == "0.1.0"
        assert parsed["package"]["edition"] == "2021"
