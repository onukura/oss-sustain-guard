"""
Tests for resolver registry and factory functions.
"""

from oss_sustain_guard.resolvers import (
    detect_ecosystems,
    get_all_resolvers,
    get_resolver,
    register_resolver,
)
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class MockEcosystemResolver(LanguageResolver):
    """Mock resolver for testing registration."""

    @property
    def ecosystem_name(self) -> str:
        return "mock-ecosystem"

    def resolve_github_url(self, package_name: str) -> tuple[str, str] | None:
        return None

    def parse_lockfile(self, lockfile_path: str) -> list[PackageInfo]:
        return []

    def parse_manifest(self, manifest_path: str) -> list[PackageInfo]:
        return []

    def detect_lockfiles(self, directory: str) -> list:
        return []

    def get_manifest_files(self) -> list[str]:
        return ["mock.lock"]


class TestResolverRegistry:
    """Test resolver registry and factory functions."""

    def test_get_python_resolver(self):
        """Test getting Python resolver."""
        resolver = get_resolver("python")
        assert resolver is not None
        assert resolver.ecosystem_name == "python"

    def test_get_resolver_case_insensitive(self):
        """Test that get_resolver is case-insensitive."""
        resolver_lower = get_resolver("python")
        resolver_upper = get_resolver("PYTHON")
        resolver_mixed = get_resolver("PyThOn")

        assert resolver_lower is not None
        assert resolver_upper is not None
        assert resolver_mixed is not None
        assert resolver_lower is resolver_upper
        assert resolver_upper is resolver_mixed

    def test_get_unknown_resolver(self):
        """Test getting unknown resolver returns None."""
        resolver = get_resolver("unknown-ecosystem")
        assert resolver is None

    def test_register_custom_resolver(self):
        """Test registering a custom resolver."""
        mock_resolver = MockEcosystemResolver()
        register_resolver("test-ecosystem", mock_resolver)

        resolver = get_resolver("test-ecosystem")
        assert resolver is mock_resolver
        if resolver is not None:
            assert resolver.ecosystem_name == "mock-ecosystem"

    def test_get_all_resolvers(self):
        """Test getting all resolvers."""
        resolvers = get_all_resolvers()
        assert len(resolvers) >= 1
        assert any(r.ecosystem_name == "python" for r in resolvers)

    def test_get_all_resolvers_deduplication(self):
        """Test that get_all_resolvers deduplicates."""
        # Register the same resolver with multiple aliases
        mock_resolver = MockEcosystemResolver()
        register_resolver("alias1", mock_resolver)
        register_resolver("alias2", mock_resolver)

        resolvers = get_all_resolvers()
        # Should not include duplicate references to the same resolver
        resolver_ids = [id(r) for r in resolvers]
        assert len(resolver_ids) == len(set(resolver_ids))

    def test_detect_ecosystems_python(self, tmp_path):
        """Test detecting Python ecosystem."""
        (tmp_path / "poetry.lock").touch()

        ecosystems = detect_ecosystems(str(tmp_path))
        assert "python" in ecosystems

    def test_detect_ecosystems_none(self, tmp_path):
        """Test detecting no ecosystems."""
        ecosystems = detect_ecosystems(str(tmp_path))
        assert isinstance(ecosystems, list)

    def test_detect_ecosystems_multiple(self, tmp_path):
        """Test detecting multiple ecosystems."""
        (tmp_path / "poetry.lock").touch()

        ecosystems = detect_ecosystems(str(tmp_path))
        assert isinstance(ecosystems, list)
        # Should be sorted
        assert ecosystems == sorted(ecosystems)

    def test_detect_ecosystems_manifest_files(self, tmp_path):
        """Test detecting ecosystems by manifest files."""
        (tmp_path / "pyproject.toml").write_text("[project]")

        ecosystems = detect_ecosystems(str(tmp_path))
        assert "python" in ecosystems

    def test_get_php_resolver(self):
        """Test getting PHP resolver."""
        resolver = get_resolver("php")
        assert resolver is not None
        assert resolver.ecosystem_name == "php"

    def test_get_java_resolver(self):
        """Test getting Java resolver."""
        resolver = get_resolver("java")
        assert resolver is not None
        assert resolver.ecosystem_name == "java"

    def test_get_csharp_resolver(self):
        """Test getting C# resolver."""
        resolver = get_resolver("csharp")
        assert resolver is not None
        assert resolver.ecosystem_name == "csharp"

    def test_get_java_aliases(self):
        """Test getting Java resolver via aliases."""
        java = get_resolver("java")
        kotlin = get_resolver("kotlin")
        scala = get_resolver("scala")
        maven = get_resolver("maven")

        assert java is not None
        assert kotlin is not None
        assert scala is not None
        assert maven is not None
        # Java ecosystem
        assert java.ecosystem_name == "java"
        # Kotlin has its own ecosystem but uses Maven Central
        assert kotlin.ecosystem_name == "kotlin"
        # Scala uses Java ecosystem (Maven Central/sbt)
        assert scala.ecosystem_name == "java"
        # Maven alias points to Java
        assert maven.ecosystem_name == "java"

    def test_get_csharp_aliases(self):
        """Test getting C# resolver via aliases."""
        csharp = get_resolver("csharp")
        dotnet = get_resolver("dotnet")
        nuget = get_resolver("nuget")

        assert csharp is not None
        assert dotnet is not None
        assert nuget is not None
        # All should be csharp ecosystem
        assert csharp.ecosystem_name == "csharp"
        assert dotnet.ecosystem_name == "csharp"
        assert nuget.ecosystem_name == "csharp"

    def test_get_php_aliases(self):
        """Test getting PHP resolver via aliases."""
        php = get_resolver("php")
        composer = get_resolver("composer")

        assert php is not None
        assert composer is not None
        # All should be php ecosystem
        assert php.ecosystem_name == "php"
        assert composer.ecosystem_name == "php"
