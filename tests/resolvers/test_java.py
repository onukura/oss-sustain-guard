"""
Tests for Java resolver.
"""

import platform
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

    def test_parse_repository_url_github(self):
        """Test parsing valid GitHub URL."""
        from oss_sustain_guard.repository import parse_repository_url

        result = parse_repository_url("https://github.com/google/guava")
        assert result is not None
        assert result.provider == "github"
        assert result.owner == "google"
        assert result.name == "guava"

    def test_parse_repository_url_github_with_git_suffix(self):
        """Test parsing GitHub URL with .git suffix."""
        from oss_sustain_guard.repository import parse_repository_url

        result = parse_repository_url("https://github.com/google/guava.git")
        assert result is not None
        assert result.provider == "github"
        assert result.owner == "google"
        assert result.name == "guava"

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

    def test_known_packages(self):
        """Test resolving known packages with direct mapping."""
        resolver = JavaResolver()
        # Test known package without hitting the API
        result = resolver.resolve_repository("org.apache.commons:commons-lang3")
        assert result is not None
        assert result.owner == "apache"
        assert result.name == "commons-lang"

    def test_known_packages_slf4j(self):
        """Test resolving slf4j known package."""
        resolver = JavaResolver()
        result = resolver.resolve_repository("org.slf4j:slf4j-api")
        assert result is not None
        assert result.owner == "qos-ch"
        assert result.name == "slf4j"

    @patch("httpx.Client.get")
    def test_resolve_repository_fallback_url(self, mock_get):
        """Test fallback when SCM URL is not in pom.xml but other GitHub URL exists."""
        # First mock: metadata.xml response
        metadata_response = MagicMock()
        metadata_response.text = (
            '<?xml version="1.0"?><versioning><latest>1.0.0</latest></versioning>'
        )
        metadata_response.raise_for_status = MagicMock()

        # Second mock: pom.xml without SCM but with GitHub URL in text
        pom_response = MagicMock()
        pom_response.text = """<?xml version="1.0"?>
<project>
    <name>Test Project</name>
    <url>https://github.com/test-org/test-repo</url>
</project>"""
        pom_response.raise_for_status = MagicMock()

        mock_get.side_effect = [metadata_response, pom_response]

        resolver = JavaResolver()
        result = resolver.resolve_repository("com.test:test-artifact")
        assert result is not None
        assert result.owner == "test-org"
        assert result.name == "test-repo"

    @patch("httpx.Client.get")
    def test_resolve_repository_no_url(self, mock_get):
        """Test when pom.xml has no repository URL."""
        # First mock: metadata.xml response
        metadata_response = MagicMock()
        metadata_response.text = (
            '<?xml version="1.0"?><versioning><latest>1.0.0</latest></versioning>'
        )
        metadata_response.raise_for_status = MagicMock()

        # Second mock: pom.xml without any repository URL
        pom_response = MagicMock()
        pom_response.text = """<?xml version="1.0"?>
<project>
    <name>Test Project</name>
</project>"""
        pom_response.raise_for_status = MagicMock()

        mock_get.side_effect = [metadata_response, pom_response]

        resolver = JavaResolver()
        result = resolver.resolve_repository("com.test:no-repo")
        assert result is None

    @patch("httpx.Client.get")
    def test_resolve_repository_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        import httpx

        # Create proper mock request and response
        mock_request = MagicMock()
        mock_request.url = "https://example.com"
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_get.side_effect = httpx.HTTPStatusError(
            "Not found", request=mock_request, response=mock_response
        )

        resolver = JavaResolver()
        result = resolver.resolve_repository("com.error:package")
        assert result is None

    @patch("httpx.Client.get")
    def test_resolve_repository_value_error(self, mock_get):
        """Test handling of ValueError during parsing."""
        # First mock: metadata.xml response
        metadata_response = MagicMock()
        metadata_response.text = (
            '<?xml version="1.0"?><versioning><latest>1.0.0</latest></versioning>'
        )
        metadata_response.raise_for_status = MagicMock()

        # Second mock: malformed pom.xml that causes ValueError
        pom_response = MagicMock()
        pom_response.text = "invalid xml content"
        pom_response.raise_for_status = MagicMock(side_effect=ValueError("Parse error"))

        mock_get.side_effect = [metadata_response, pom_response]

        resolver = JavaResolver()
        result = resolver.resolve_repository("com.error:package")
        assert result is None

    def test_parse_pom_xml(self, tmp_path):
        """Test parsing pom.xml manifest."""
        pom_file = tmp_path / "pom.xml"
        pom_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <dependencies>
        <dependency>
            <groupId>com.google.guava</groupId>
            <artifactId>guava</artifactId>
            <version>31.1-jre</version>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
        </dependency>
    </dependencies>
</project>""")

        resolver = JavaResolver()
        packages = resolver.parse_manifest(str(pom_file))

        assert len(packages) == 2
        assert packages[0].name == "com.google.guava:guava"
        assert packages[0].version == "31.1-jre"
        assert packages[0].ecosystem == "java"
        assert packages[1].name == "junit:junit"
        assert packages[1].version == "4.13.2"

    def test_parse_gradle_manifest(self, tmp_path):
        """Test parsing build.gradle manifest."""
        gradle_file = tmp_path / "build.gradle"
        gradle_file.write_text("""
dependencies {
    implementation 'com.google.guava:guava:31.1-jre'
    testImplementation 'junit:junit:4.13.2'
    compileOnly 'org.projectlombok:lombok:1.18.24'
    runtimeOnly "ch.qos.logback:logback-classic:1.4.0"
}
""")

        resolver = JavaResolver()
        packages = resolver.parse_manifest(str(gradle_file))

        assert len(packages) == 4
        package_names = [p.name for p in packages]
        assert "com.google.guava:guava:31.1-jre" in package_names
        assert "junit:junit:4.13.2" in package_names
        assert "org.projectlombok:lombok:1.18.24" in package_names
        assert "ch.qos.logback:logback-classic:1.4.0" in package_names

    def test_parse_gradle_kts_manifest(self, tmp_path):
        """Test parsing build.gradle.kts manifest."""
        gradle_kts_file = tmp_path / "build.gradle.kts"
        gradle_kts_file.write_text("""
dependencies {
    implementation("com.google.guava:guava:31.1-jre")
    testImplementation("junit:junit:4.13.2")
}
""")

        resolver = JavaResolver()
        packages = resolver.parse_manifest(str(gradle_kts_file))

        assert len(packages) == 2
        assert packages[0].name == "com.google.guava:guava:31.1-jre"
        assert packages[1].name == "junit:junit:4.13.2"

    def test_parse_sbt_manifest(self, tmp_path):
        """Test parsing build.sbt manifest."""
        sbt_file = tmp_path / "build.sbt"
        sbt_file.write_text("""
name := "test-project"

libraryDependencies += "org.scala-lang" %% "scala-library" % "2.13.0"
libraryDependencies += "com.typesafe" % "config" % "1.4.0"
""")

        resolver = JavaResolver()
        packages = resolver.parse_manifest(str(sbt_file))

        assert len(packages) == 2
        assert packages[0].name == "org.scala-lang:scala-library"
        assert packages[0].version == "2.13.0"
        assert packages[1].name == "com.typesafe:config"
        assert packages[1].version == "1.4.0"

    def test_parse_manifest_not_found(self):
        """Test parsing non-existent manifest."""
        resolver = JavaResolver()
        with pytest.raises(FileNotFoundError):
            resolver.parse_manifest("/nonexistent/pom.xml")

    def test_parse_manifest_unknown_type(self, tmp_path):
        """Test parsing unknown manifest type."""
        unknown_file = tmp_path / "unknown.xml"
        unknown_file.write_text("content")

        resolver = JavaResolver()
        with pytest.raises(ValueError):
            resolver.parse_manifest(str(unknown_file))

    def test_parse_pom_xml_malformed(self, tmp_path):
        """Test parsing malformed pom.xml."""
        pom_file = tmp_path / "pom.xml"
        pom_file.write_text("not valid xml")

        resolver = JavaResolver()
        with pytest.raises(ValueError):
            resolver.parse_manifest(str(pom_file))

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="chmod does not restrict file access on Windows",
    )
    def test_parse_gradle_manifest_io_error(self, tmp_path):
        """Test handling IOError in gradle parsing."""
        gradle_file = tmp_path / "build.gradle"
        gradle_file.write_text("content")
        # Make file unreadable
        gradle_file.chmod(0o000)

        resolver = JavaResolver()
        try:
            with pytest.raises(ValueError):
                resolver.parse_manifest(str(gradle_file))
        finally:
            # Restore permissions for cleanup
            gradle_file.chmod(0o644)

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="chmod does not restrict file access on Windows",
    )
    def test_parse_sbt_manifest_io_error(self, tmp_path):
        """Test handling IOError in sbt parsing."""
        sbt_file = tmp_path / "build.sbt"
        sbt_file.write_text("content")
        # Make file unreadable
        sbt_file.chmod(0o000)

        resolver = JavaResolver()
        try:
            with pytest.raises(ValueError):
                resolver.parse_manifest(str(sbt_file))
        finally:
            # Restore permissions for cleanup
            sbt_file.chmod(0o644)

    def test_parse_maven_asc_lockfile(self, tmp_path):
        """Test parsing Maven .asc file (signature file)."""
        asc_file = tmp_path / "pom.xml.asc"
        asc_file.write_text("""-----BEGIN PGP SIGNATURE-----
iQEzBAABCAAdFiEE...
-----END PGP SIGNATURE-----""")

        resolver = JavaResolver()
        packages = resolver.parse_lockfile(str(asc_file))
        # ASC files don't contain parseable dependencies
        assert packages == []

    def test_parse_sbt_lockfile_with_complex_format(self, tmp_path):
        """Test parsing build.sbt.lock with various formats."""
        lockfile = tmp_path / "build.sbt.lock"
        lockfile.write_text("""# sbt lockfile
# Comment line
org.scala-lang:scala-library:2.13.8
com.typesafe.akka:akka-actor_2.13:2.6.19
org.scalatest:scalatest_2.13:3.2.12
""")

        resolver = JavaResolver()
        packages = resolver.parse_lockfile(str(lockfile))

        assert len(packages) >= 3
        package_names = [p.name for p in packages]
        assert any("scala-library" in name for name in package_names)

    def test_resolve_github_url_deprecated_method(self):
        """Test deprecated resolve_github_url calls resolve_repository."""
        resolver = JavaResolver()
        # Test that known package works through deprecated method
        result = resolver.resolve_github_url("junit:junit")
        assert result == ("junit-team", "junit4")

    def test_detect_lockfiles_recursive(self, tmp_path):
        """Test detecting lockfiles recursively in subdirectories."""
        # Create subdirectories with lockfiles
        subdir1 = tmp_path / "module1"
        subdir1.mkdir()
        (subdir1 / "gradle.lockfile").touch()

        subdir2 = tmp_path / "module2"
        subdir2.mkdir()
        (subdir2 / "build.sbt.lock").touch()

        resolver = JavaResolver()
        lockfiles = resolver.detect_lockfiles(str(tmp_path))

        # Should find both lockfiles in subdirectories
        assert len(lockfiles) >= 2
        lockfile_names = [lf.name for lf in lockfiles]
        assert "gradle.lockfile" in lockfile_names
        assert "build.sbt.lock" in lockfile_names

    def test_parse_gradle_lockfile_exception(self, tmp_path):
        """Test handling exception during gradle lockfile parsing."""
        lockfile = tmp_path / "gradle.lockfile"
        lockfile.write_text("malformed content without proper format")

        resolver = JavaResolver()
        # Should return empty list for malformed content
        packages = resolver.parse_lockfile(str(lockfile))
        # Empty list is acceptable for malformed content
        assert isinstance(packages, list)

    def test_parse_sbt_lockfile_exception(self, tmp_path):
        """Test handling exception during sbt lockfile parsing."""
        lockfile = tmp_path / "build.sbt.lock"
        # Create file but make it unreadable after writing
        lockfile.write_text("content")

        resolver = JavaResolver()
        # Test that it handles the file properly
        packages = resolver.parse_lockfile(str(lockfile))
        assert isinstance(packages, list)

    def test_parse_gradle_lockfile_with_exception(self, tmp_path):
        """Test gradle lockfile parsing that triggers exception block."""
        from unittest.mock import patch

        lockfile = tmp_path / "gradle.lockfile"
        lockfile.write_text("valid:content:1.0.0=hash")

        resolver = JavaResolver()

        # Mock open to raise exception during read
        with patch("builtins.open", side_effect=Exception("IO error")):
            with pytest.raises(ValueError, match="Failed to parse gradle.lockfile"):
                resolver.parse_lockfile(str(lockfile))

    def test_parse_sbt_lockfile_with_exception(self, tmp_path):
        """Test sbt lockfile parsing that triggers exception block."""
        from unittest.mock import patch

        lockfile = tmp_path / "build.sbt.lock"
        lockfile.write_text("org.scala:lib:1.0")

        resolver = JavaResolver()

        # Mock open to raise exception during read
        with patch("builtins.open", side_effect=Exception("IO error")):
            with pytest.raises(ValueError, match="Failed to parse build.sbt.lock"):
                resolver.parse_lockfile(str(lockfile))

    def test_parse_pom_xml_import_error(self, tmp_path):
        """Test pom.xml parsing when xml.etree.ElementTree is not available."""
        import sys
        from unittest.mock import patch

        pom_file = tmp_path / "pom.xml"
        pom_file.write_text("<?xml version='1.0'?><project></project>")

        resolver = JavaResolver()

        # Mock import to raise ImportError
        with patch.dict(sys.modules, {"xml.etree.ElementTree": None}):
            # Force reimport to trigger ImportError
            import builtins

            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "xml.etree.ElementTree":
                    raise ImportError("Module not found")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(
                    ValueError, match="xml.etree.ElementTree is required"
                ):
                    resolver._parse_pom_xml(pom_file)
