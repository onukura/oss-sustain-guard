"""
Tests for resolver base classes and abstractions.
"""

from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class MockResolver(LanguageResolver):
    """Mock resolver for testing base class."""

    @property
    def ecosystem_name(self) -> str:
        return "mock"

    def resolve_github_url(self, package_name: str) -> tuple[str, str] | None:
        if package_name == "mock-pkg":
            return ("owner", "repo")
        return None

    def parse_lockfile(self, lockfile_path: str) -> list[PackageInfo]:
        return [
            PackageInfo(name="pkg1", ecosystem="mock", version="1.0.0"),
            PackageInfo(name="pkg2", ecosystem="mock", version="2.0.0"),
        ]

    def parse_manifest(self, manifest_path: str) -> list[PackageInfo]:
        return [
            PackageInfo(name="pkg1", ecosystem="mock", version="1.0.0"),
            PackageInfo(name="pkg2", ecosystem="mock", version="2.0.0"),
        ]

    def detect_lockfiles(self, directory: str) -> list:
        return []

    def get_manifest_files(self) -> list[str]:
        return ["mock.lock"]


class TestPackageInfo:
    """Test PackageInfo NamedTuple."""

    def test_package_info_creation(self):
        """Test creating PackageInfo with all fields."""
        pkg = PackageInfo(
            name="requests",
            ecosystem="python",
            version="2.28.0",
            registry_url="https://pypi.org",
        )
        assert pkg.name == "requests"
        assert pkg.ecosystem == "python"
        assert pkg.version == "2.28.0"
        assert pkg.registry_url == "https://pypi.org"

    def test_package_info_optional_fields(self):
        """Test creating PackageInfo with only required fields."""
        pkg = PackageInfo(name="requests", ecosystem="python")
        assert pkg.name == "requests"
        assert pkg.ecosystem == "python"
        assert pkg.version is None
        assert pkg.registry_url is None


class TestLanguageResolver:
    """Test LanguageResolver abstract base class."""

    def test_resolver_implementation(self):
        """Test that resolver can be instantiated with mock."""
        resolver = MockResolver()
        assert resolver.ecosystem_name == "mock"
        assert resolver.get_manifest_files() == ["mock.lock"]

    def test_resolve_github_url(self):
        """Test resolving GitHub URL."""
        resolver = MockResolver()
        result = resolver.resolve_github_url("mock-pkg")
        assert result == ("owner", "repo")

    def test_resolve_github_url_not_found(self):
        """Test resolving non-existent package."""
        resolver = MockResolver()
        result = resolver.resolve_github_url("unknown-pkg")
        assert result is None

    def test_parse_lockfile(self):
        """Test parsing lockfile."""
        resolver = MockResolver()
        packages = resolver.parse_lockfile("dummy.lock")
        assert len(packages) == 2
        assert packages[0].name == "pkg1"
        assert packages[1].name == "pkg2"

    def test_resolver_repr(self):
        """Test resolver string representation."""
        resolver = MockResolver()
        assert "MockResolver" in repr(resolver)
        assert "mock" in repr(resolver)
