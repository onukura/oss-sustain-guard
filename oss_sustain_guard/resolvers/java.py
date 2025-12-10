"""
Java/JVM package resolver for Maven Central.

Supports Java, Kotlin, and Scala packages via Maven Central Repository.
"""

import re
from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class JavaResolver(LanguageResolver):
    """Resolver for Java/JVM packages (Maven Central)."""

    MAVEN_CENTRAL_API_URL = "https://search.maven.org/solrsearch/select"

    # Known package to GitHub repository mappings for packages where pom.xml resolution fails
    KNOWN_PACKAGES = {
        "org.apache.commons:commons-lang3": ("apache", "commons-lang"),
        "org.slf4j:slf4j-api": ("qos-ch", "slf4j"),
        "junit:junit": ("junit-team", "junit4"),
        "org.mockito:mockito-core": ("mockito", "mockito"),
        "org.hamcrest:hamcrest": ("hamcrest", "JavaHamcrest"),
        "com.google.code.gson:gson": ("google", "gson"),
        "org.projectlombok:lombok": ("projectlombok", "lombok"),
        "org.apache.log4j:log4j": ("apache", "logging-log4j1"),
        "ch.qos.logback:logback-classic": ("qos-ch", "logback"),
        "org.apache.commons:commons-pool2": ("apache", "commons-pool"),
        "org.apache.commons:commons-dbcp2": ("apache", "commons-dbcp"),
    }

    @property
    def ecosystem_name(self) -> str:
        return "java"

    def resolve_github_url(self, package_name: str) -> tuple[str, str] | None:
        """
        Fetches package information from Maven Central and extracts GitHub URL from pom.xml.

        Args:
            package_name: The name of the package in groupId:artifactId format.

        Returns:
            A tuple of (owner, repo_name) if a GitHub URL is found, otherwise None.
        """
        # Check known packages first
        if package_name in self.KNOWN_PACKAGES:
            return self.KNOWN_PACKAGES[package_name]

        try:
            # Parse groupId:artifactId format
            if ":" not in package_name:
                return None

            group_id, artifact_id = package_name.split(":", 1)
            group_path = group_id.replace(".", "/")

            with httpx.Client(verify=get_verify_ssl()) as client:
                # First, get the latest version from maven-metadata.xml
                metadata_url = f"https://repo1.maven.org/maven2/{group_path}/{artifact_id}/maven-metadata.xml"
                metadata_response = client.get(metadata_url, timeout=10)
                metadata_response.raise_for_status()

                # Extract latest version from metadata
                latest_match = re.search(
                    r"<latest>([^<]+)</latest>",
                    metadata_response.text,
                )
                if not latest_match:
                    return None

                latest_version = latest_match.group(1)

                # Fetch pom.xml from the latest version
                pom_url = f"https://repo1.maven.org/maven2/{group_path}/{artifact_id}/{latest_version}/{artifact_id}-{latest_version}.pom"
                pom_response = client.get(pom_url, timeout=10)
                pom_response.raise_for_status()

                # Extract SCM URL from pom.xml
                scm_match = re.search(
                    r"<scm>.*?<url>([^<]+)</url>.*?</scm>",
                    pom_response.text,
                    re.DOTALL,
                )
                if scm_match:
                    scm_url = scm_match.group(1)
                    return self._parse_github_url(scm_url)

                # Fallback: look for GitHub URL in project url or any GitHub link
                github_match = re.search(
                    r'https://github\.com/[^\s<>"\']+',
                    pom_response.text,
                )
                if github_match:
                    return self._parse_github_url(github_match.group(0))

                return None
        except (httpx.RequestError, ValueError, KeyError) as e:
            print(f"Error fetching Java data for {package_name}: {e}")
            return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse Maven/Gradle lockfile and extract package information.

        Args:
            lockfile_path: Path to gradle.lockfile or pom.xml.asc.

        Returns:
            List of PackageInfo objects extracted from the lockfile.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
            ValueError: If the lockfile format is invalid.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        if lockfile_path.name == "gradle.lockfile":
            return self._parse_gradle_lockfile(lockfile_path)
        elif lockfile_path.name.endswith(".asc"):
            return self._parse_maven_asc_lockfile(lockfile_path)
        elif lockfile_path.name == "build.sbt.lock":
            return self._parse_sbt_lockfile(lockfile_path)
        else:
            raise ValueError(f"Unsupported lockfile format: {lockfile_path.name}")

    def detect_lockfiles(self, directory: str | Path) -> list[Path]:
        """
        Detect Maven/Gradle lockfiles in the directory.

        Args:
            directory: Directory to scan.

        Returns:
            List of Path objects pointing to lockfiles.
        """
        directory = Path(directory)
        lockfiles = []

        # Look for gradle.lockfile
        if (directory / "gradle.lockfile").exists():
            lockfiles.append(directory / "gradle.lockfile")

        # Look for build.sbt.lock (Scala/sbt)
        if (directory / "build.sbt.lock").exists():
            lockfiles.append(directory / "build.sbt.lock")

        # Note: pom.xml itself is not a lockfile, but we could support
        # Maven dependency-tree output in the future

        # Recursively search subdirectories
        for subdir in directory.rglob("gradle.lockfile"):
            if subdir not in lockfiles:
                lockfiles.append(subdir)

        for subdir in directory.rglob("build.sbt.lock"):
            if subdir not in lockfiles:
                lockfiles.append(subdir)

        return lockfiles

    def get_manifest_files(self) -> list[str]:
        """
        Return list of Java manifest files.

        Returns:
            List of manifest file names.
        """
        return ["pom.xml", "build.gradle", "build.gradle.kts", "build.sbt"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse a Java manifest file (pom.xml, build.gradle, build.sbt).

        Args:
            manifest_path: Path to manifest file.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        filename = manifest_path.name

        if filename == "pom.xml":
            return self._parse_pom_xml(manifest_path)
        elif filename in ("build.gradle", "build.gradle.kts"):
            return self._parse_gradle_manifest(manifest_path)
        elif filename == "build.sbt":
            return self._parse_sbt_manifest(manifest_path)
        else:
            raise ValueError(f"Unknown Java manifest file type: {filename}")

    @staticmethod
    def _parse_pom_xml(manifest_path: Path) -> list[PackageInfo]:
        """Parse pom.xml file."""
        try:
            import xml.etree.ElementTree as ET
        except ImportError as e:
            raise ValueError(
                "xml.etree.ElementTree is required to parse pom.xml"
            ) from e

        packages = []

        try:
            tree = ET.parse(manifest_path)
            root = tree.getroot()

            # Define Maven namespace
            ns = {"mvn": "http://maven.apache.org/POM/4.0.0"}

            # Find all dependencies
            for dep in root.findall(".//mvn:dependency", ns):
                group_id = dep.find("mvn:groupId", ns)
                artifact_id = dep.find("mvn:artifactId", ns)
                version = dep.find("mvn:version", ns)

                if artifact_id is not None:
                    packages.append(
                        PackageInfo(
                            name=f"{group_id.text if group_id is not None else ''}:{artifact_id.text}",
                            ecosystem="java",
                            version=version.text if version is not None else None,
                        )
                    )

            return packages
        except Exception as e:
            raise ValueError(f"Failed to parse pom.xml: {e}") from e

    @staticmethod
    def _parse_gradle_manifest(manifest_path: Path) -> list[PackageInfo]:
        """Parse build.gradle or build.gradle.kts file."""
        packages = []

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()

            import re

            # Match dependency patterns
            # dependencies {
            #     implementation 'group:artifact:version'
            #     testImplementation("group:artifact:version")
            # }

            # Pattern: implementation/testImplementation/etc '...' or "..."
            pattern = r"(?:implementation|testImplementation|compileOnly|runtimeOnly)\s+['\"]([^'\"]+)['\"]"
            matches = re.findall(pattern, content)

            for match in matches:
                packages.append(
                    PackageInfo(
                        name=match,
                        ecosystem="java",
                        version=None,
                    )
                )

            return packages
        except (IOError, ValueError) as e:
            raise ValueError(f"Failed to parse gradle manifest: {e}") from e

    @staticmethod
    def _parse_sbt_manifest(manifest_path: Path) -> list[PackageInfo]:
        """Parse build.sbt file."""
        packages = []

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()

            import re

            # Match libraryDependencies pattern
            # libraryDependencies += "org.example" %% "artifact" % "1.0.0"
            # libraryDependencies += "org.example" % "artifact" % "1.0.0"

            pattern = r'libraryDependencies\s*\+=\s*"([^"]+)"\s*%%?\s*"([^"]+)"\s*%\s*"([^"]+)"'
            matches = re.findall(pattern, content)

            for group_id, artifact_id, version in matches:
                packages.append(
                    PackageInfo(
                        name=f"{group_id}:{artifact_id}",
                        ecosystem="java",
                        version=version,
                    )
                )

            return packages
        except (IOError, ValueError) as e:
            raise ValueError(f"Failed to parse sbt manifest: {e}") from e

    def _parse_gradle_lockfile(self, lockfile_path: Path) -> list[PackageInfo]:
        """
        Parse gradle.lockfile and extract dependencies.

        Args:
            lockfile_path: Path to gradle.lockfile.

        Returns:
            List of PackageInfo objects.

        Raises:
            ValueError: If the file format is invalid.
        """
        packages = []
        try:
            with open(lockfile_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # gradle.lockfile format:
            # # Comment lines
            # group:artifact:version=hash
            # ...

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Parse "group:artifact:version=hash" format
                if "=" in line:
                    dep_part = line.split("=")[0]
                    if ":" in dep_part:
                        parts = dep_part.rsplit(
                            ":", 2
                        )  # Split from right to get version
                        if len(parts) == 3:
                            group_id, artifact_id, version = parts
                            packages.append(
                                PackageInfo(
                                    name=f"{group_id}:{artifact_id}",
                                    ecosystem="java",
                                    version=version,
                                    registry_url=f"https://search.maven.org/artifact/{group_id}/{artifact_id}",
                                )
                            )

            return packages
        except Exception as e:
            raise ValueError(f"Failed to parse gradle.lockfile: {e}") from e

    def _parse_maven_asc_lockfile(self, lockfile_path: Path) -> list[PackageInfo]:
        """
        Parse Maven pom.xml.asc and extract version information.

        Note: pom.xml.asc is typically a PGP signature. This is a simplified parser.

        Args:
            lockfile_path: Path to pom.xml.asc.

        Returns:
            List of PackageInfo objects (empty in typical case).

        Raises:
            ValueError: If the file format is invalid.
        """
        # pom.xml.asc is typically an ASCII-armored PGP signature, not directly parseable
        # Return empty list for now
        return []

    def _parse_sbt_lockfile(self, lockfile_path: Path) -> list[PackageInfo]:
        """
        Parse build.sbt.lock and extract dependencies.

        Args:
            lockfile_path: Path to build.sbt.lock.

        Returns:
            List of PackageInfo objects.

        Raises:
            ValueError: If the file format is invalid.
        """
        packages = []
        try:
            with open(lockfile_path, "r", encoding="utf-8") as f:
                content = f.read()

            # build.sbt.lock uses TOML-like format
            # Try to parse as simple key-value pairs
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Look for dependency patterns
                # Format: org:artifact:version
                pattern = r"([a-zA-Z0-9._-]+):([a-zA-Z0-9._-]+):([a-zA-Z0-9._-]+)"
                matches = re.findall(pattern, line)
                for group_id, artifact_id, version in matches:
                    packages.append(
                        PackageInfo(
                            name=f"{group_id}:{artifact_id}",
                            ecosystem="java",
                            version=version,
                            registry_url=f"https://search.maven.org/artifact/{group_id}/{artifact_id}",
                        )
                    )

            return packages
        except Exception as e:
            raise ValueError(f"Failed to parse build.sbt.lock: {e}") from e

    @staticmethod
    def _parse_github_url(url: str) -> tuple[str, str] | None:
        """
        Parse GitHub URL and extract owner and repo.

        Args:
            url: GitHub URL in format https://github.com/owner/repo[.git]
                 or other git URLs like https://gitbox.apache.org/repos/asf/repo-name.git

        Returns:
            Tuple of (owner, repo) or None if URL cannot be parsed.
        """
        if not url or not isinstance(url, str):
            return None

        # Remove .git suffix if present
        if url.endswith(".git"):
            url = url[:-4]

        # Handle GitHub URLs
        if "github.com" in url:
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                owner = parts[-2]
                repo = parts[-1]
                if owner and repo:
                    return (owner, repo)

        # Handle other git hosting URLs (e.g., gitbox.apache.org)
        # Try to extract last two path components as owner/repo
        parts = url.rstrip("/").split("/")
        if len(parts) >= 2:
            # Skip common patterns and extract meaningful last two parts
            repo = parts[-1]
            owner = parts[-2]

            # Filter out common non-meaningful parts
            if (
                repo
                and owner
                and owner
                not in [
                    "repos",
                    "git",
                    "repo",
                    "repository",
                ]
            ):
                return (owner, repo)

        return None
