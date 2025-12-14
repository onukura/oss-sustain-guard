"""
Tests for Kotlin resolver.
"""

from unittest.mock import MagicMock, patch

from oss_sustain_guard.resolvers.kotlin import KotlinResolver


class TestKotlinResolver:
    """Test KotlinResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = KotlinResolver()
        assert resolver.ecosystem_name == "kotlin"

    def test_get_manifest_files(self):
        """Test manifest files for Kotlin."""
        resolver = KotlinResolver()
        manifests = resolver.get_manifest_files()
        # Kotlin prioritizes .kts files
        assert manifests[0] == "build.gradle.kts"
        assert "build.gradle" in manifests
        assert "pom.xml" in manifests

    @patch("httpx.Client.get")
    def test_resolve_github_url_kotlin_package(self, mock_get):
        """Test resolving GitHub URL for a Kotlin package from Maven Central."""
        # First mock: metadata.xml response
        metadata_response = MagicMock()
        metadata_response.text = (
            '<?xml version="1.0"?><versioning><latest>1.9.0</latest></versioning>'
        )
        metadata_response.raise_for_status = MagicMock()

        # Second mock: pom.xml response
        pom_response = MagicMock()
        pom_response.text = (
            '<?xml version="1.0"?>'
            "<project>"
            "<scm><url>https://github.com/JetBrains/kotlin</url></scm>"
            "</project>"
        )
        pom_response.raise_for_status = MagicMock()

        mock_get.side_effect = [metadata_response, pom_response]

        resolver = KotlinResolver()
        result = resolver.resolve_github_url("org.jetbrains.kotlin:kotlin-stdlib")
        assert result == ("JetBrains", "kotlin")

    @patch("httpx.Client.get")
    def test_resolve_github_url_not_found(self, mock_get):
        """Test resolving package not in Maven Central."""
        # Mock metadata.xml response with no latest version
        metadata_response = MagicMock()
        metadata_response.text = '<?xml version="1.0"?><versioning></versioning>'
        metadata_response.raise_for_status = MagicMock()

        mock_get.return_value = metadata_response

        resolver = KotlinResolver()
        result = resolver.resolve_github_url("com.nonexistent:package")
        assert result is None

    @patch("httpx.Client.get")
    def test_resolve_github_url_invalid_format(self, mock_get):
        """Test resolving with invalid package format."""
        resolver = KotlinResolver()
        result = resolver.resolve_github_url("invalid-package-name")
        assert result is None

    @patch("httpx.Client.get")
    def test_resolve_github_url_network_error(self, mock_get):
        """Test resolving with network error."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = KotlinResolver()
        result = resolver.resolve_github_url("org.jetbrains.kotlin:kotlin-stdlib")
        assert result is None

    def test_detect_lockfiles(self, tmp_path):
        """Test detecting Kotlin lockfiles (same as Java/Gradle)."""
        (tmp_path / "gradle.lockfile").touch()
        (tmp_path / "other.txt").touch()

        resolver = KotlinResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) >= 1
        assert any(lf.name == "gradle.lockfile" for lf in lockfiles)

    def test_detect_kotlin_dsl_manifest(self, tmp_path):
        """Test that build.gradle.kts files are recognized."""
        (tmp_path / "build.gradle.kts").write_text(
            """
            plugins {
                kotlin("jvm") version "1.9.0"
            }

            dependencies {
                implementation("org.jetbrains.kotlin:kotlin-stdlib:1.9.0")
            }
            """
        )

        resolver = KotlinResolver()
        manifests = resolver.get_manifest_files()

        # Check that build.gradle.kts is the first priority
        assert manifests[0] == "build.gradle.kts"

    @patch("httpx.Client.get")
    def test_resolve_popular_kotlin_libraries(self, mock_get):
        """Test resolving popular Kotlin libraries."""
        # Mock for kotlinx-coroutines
        metadata_response = MagicMock()
        metadata_response.text = (
            '<?xml version="1.0"?><versioning><latest>1.7.3</latest></versioning>'
        )
        metadata_response.raise_for_status = MagicMock()

        pom_response = MagicMock()
        pom_response.text = (
            '<?xml version="1.0"?>'
            "<project>"
            "<scm><url>https://github.com/Kotlin/kotlinx.coroutines</url></scm>"
            "</project>"
        )
        pom_response.raise_for_status = MagicMock()

        mock_get.side_effect = [metadata_response, pom_response]

        resolver = KotlinResolver()
        result = resolver.resolve_github_url(
            "org.jetbrains.kotlinx:kotlinx-coroutines-core"
        )
        assert result == ("Kotlin", "kotlinx.coroutines")
