"""
Tests for Java resolver.
"""

from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.java import JavaResolver


class TestJavaResolver:
    """Test JavaResolver class."""

    def test_ecosystem_name(self):
        """Test ecosystem name."""
        resolver = JavaResolver()
        assert resolver.ecosystem_name == "java"

    def test_get_manifest_files(self):
        """Test manifest files for Java."""
        resolver = JavaResolver()
        manifests = resolver.get_manifest_files()
        assert "pom.xml" in manifests
        assert "build.gradle" in manifests
        assert "build.gradle.kts" in manifests
        assert "build.sbt" in manifests

    @patch("httpx.Client.get")
    def test_resolve_github_url_success(self, mock_get):
        """Test resolving GitHub URL from Maven Central."""
        # First mock: metadata.xml response
        metadata_response = MagicMock()
        metadata_response.text = (
            '<?xml version="1.0"?><versioning><latest>31.1-jre</latest></versioning>'
        )
        metadata_response.raise_for_status = MagicMock()

        # Second mock: pom.xml response
        pom_response = MagicMock()
        pom_response.text = (
            '<?xml version="1.0"?>'
            "<project>"
            "<scm><url>https://github.com/google/guava</url></scm>"
            "</project>"
        )
        pom_response.raise_for_status = MagicMock()

        mock_get.side_effect = [metadata_response, pom_response]

        resolver = JavaResolver()
        result = resolver.resolve_github_url("com.google.guava:guava")
        assert result == ("google", "guava")

    @patch("httpx.Client.get")
    def test_resolve_github_url_not_found(self, mock_get):
        """Test resolving package not in Maven Central."""
        # Mock metadata.xml response with no latest version
        metadata_response = MagicMock()
        metadata_response.text = '<?xml version="1.0"?><versioning></versioning>'
        metadata_response.raise_for_status = MagicMock()

        mock_get.return_value = metadata_response

        resolver = JavaResolver()
        result = resolver.resolve_github_url("com.nonexistent:package")
        assert result is None

    @patch("httpx.Client.get")
    def test_resolve_github_url_invalid_format(self, mock_get):
        """Test resolving with invalid package format."""
        resolver = JavaResolver()
        result = resolver.resolve_github_url("invalid-package-name")
        assert result is None

    @patch("httpx.Client.get")
    def test_resolve_github_url_network_error(self, mock_get):
        """Test resolving with network error."""
        import httpx

        mock_get.side_effect = httpx.RequestError("Network error")

        resolver = JavaResolver()
        result = resolver.resolve_github_url("com.google.guava:guava")
        assert result is None

    def test_detect_lockfiles(self, tmp_path):
        """Test detecting Java lockfiles."""
        (tmp_path / "gradle.lockfile").touch()
        (tmp_path / "other.txt").touch()

        resolver = JavaResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) >= 1
        assert any(lf.name == "gradle.lockfile" for lf in lockfiles)

    def test_detect_lockfiles_sbt(self, tmp_path):
        """Test detecting sbt lockfiles."""
        (tmp_path / "build.sbt.lock").touch()

        resolver = JavaResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        assert len(lockfiles) >= 1
        assert any(lf.name == "build.sbt.lock" for lf in lockfiles)

    def test_parse_gradle_lockfile_success(self, tmp_path):
        """Test parsing valid gradle.lockfile."""
        lockfile = tmp_path / "gradle.lockfile"
        lockfile.write_text(
            """# Gradle lockfile format
com.google.guava:guava:31.1-jre=abc123
org.springframework:spring-core:5.3.0=def456
junit:junit:4.13.2=ghi789
"""
        )

        resolver = JavaResolver()
        packages = resolver.parse_lockfile(str(lockfile))

        assert len(packages) == 3
        assert packages[0].name == "com.google.guava:guava"
        assert packages[0].version == "31.1-jre"
        assert packages[0].ecosystem == "java"
        assert packages[1].name == "org.springframework:spring-core"
        assert packages[1].version == "5.3.0"

    def test_parse_gradle_lockfile_not_found(self):
        """Test parsing non-existent gradle.lockfile."""
        resolver = JavaResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_lockfile("/nonexistent/gradle.lockfile")

    def test_parse_sbt_lockfile_success(self, tmp_path):
        """Test parsing valid build.sbt.lock."""
        lockfile = tmp_path / "build.sbt.lock"
        lockfile.write_text(
            """# sbt lockfile
org.scala-lang:scala-library:2.13.0
com.typesafe:config:1.4.0
"""
        )

        resolver = JavaResolver()
        packages = resolver.parse_lockfile(str(lockfile))

        # Should extract org:lib:version patterns
        assert len(packages) >= 2

    def test_parse_lockfile_unknown_type(self, tmp_path):
        """Test parsing unknown lockfile type."""
        lockfile = tmp_path / "unknown.lock"
        lockfile.write_text("some content")

        resolver = JavaResolver()
        with pytest.raises(ValueError):
            resolver.parse_lockfile(str(lockfile))

    def test_parse_github_url_valid(self):
        """Test parsing valid GitHub URL."""
        resolver = JavaResolver()
        result = resolver._parse_github_url("https://github.com/google/guava")
        assert result == ("google", "guava")

    def test_parse_github_url_with_git_suffix(self):
        """Test parsing GitHub URL with .git suffix."""
        resolver = JavaResolver()
        result = resolver._parse_github_url("https://github.com/google/guava.git")
        assert result == ("google", "guava")

    def test_parse_github_url_non_github(self):
        """Test parsing non-GitHub URL."""
        resolver = JavaResolver()
        result = resolver._parse_github_url("https://gitlab.com/user/repo")
        # Non-GitHub URLs still extract owner/repo, just not from GitHub
        assert result == ("user", "repo")

    def test_parse_github_url_invalid(self):
        """Test parsing invalid URL."""
        resolver = JavaResolver()
        assert resolver._parse_github_url("") is None
