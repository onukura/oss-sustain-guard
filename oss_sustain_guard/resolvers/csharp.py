"""
C# package resolver for NuGet.
"""

import json
import re
from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class CSharpResolver(LanguageResolver):
    """Resolver for C#/.NET packages (NuGet)."""

    NUGET_FLAT_CONTAINER_URL = "https://api.nuget.org/v3-flatcontainer"

    @property
    def ecosystem_name(self) -> str:
        return "csharp"

    def resolve_github_url(self, package_name: str) -> tuple[str, str] | None:
        """
        Fetches package information from NuGet Flat Container API and extracts GitHub URL from nuspec.

        Args:
            package_name: The name of the package on NuGet.

        Returns:
            A tuple of (owner, repo_name) if a GitHub URL is found, otherwise None.
        """
        try:
            package_lower = package_name.lower()

            with httpx.Client(verify=get_verify_ssl()) as client:
                # Get available versions using flat container API
                versions_url = (
                    f"{self.NUGET_FLAT_CONTAINER_URL}/{package_lower}/index.json"
                )
                versions_response = client.get(versions_url, timeout=10)
                versions_response.raise_for_status()
                versions_data = versions_response.json()

            versions = versions_data.get("versions", [])
            if not versions:
                return None

            # Find the latest stable version (prefer non-dev versions)
            stable_versions = [
                v
                for v in versions
                if not any(suffix in v.lower() for suffix in ["dev", "alpha", "beta"])
            ]
            target_version = stable_versions[-1] if stable_versions else versions[-1]

            # Fetch nuspec for the target version
            nuspec_url = f"{self.NUGET_FLAT_CONTAINER_URL}/{package_lower}/{target_version}/{package_lower}.nuspec"

            with httpx.Client(verify=get_verify_ssl()) as client:
                nuspec_response = client.get(nuspec_url, timeout=10)
                nuspec_response.raise_for_status()
                nuspec_content = nuspec_response.text

            # Extract repository URL from nuspec XML
            repo_match = re.search(
                r'<repository[^>]*url="([^"]+)"',
                nuspec_content,
            )
            if repo_match:
                repository_url = repo_match.group(1)
                return self._parse_github_url(repository_url)

            return None
        except (httpx.RequestError, ValueError, KeyError) as e:
            print(f"Error fetching NuGet data for {package_name}: {e}")
            return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse packages.lock.json and extract package information.

        Args:
            lockfile_path: Path to packages.lock.json file.

        Returns:
            List of PackageInfo objects extracted from the lockfile.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
            ValueError: If the lockfile is invalid.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        try:
            with open(lockfile_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            packages = []

            # packages.lock.json has a structure like:
            # {
            #   "version": 2,
            #   "dependencies": {
            #     ".NETFramework,Version=v4.7.2": {
            #       "PackageName": { "type": "Direct", "requested": "1.0.0", "resolved": "1.0.0" },
            #       ...
            #     }
            #   }
            # }

            dependencies = data.get("dependencies", {})
            for _framework, packages_dict in dependencies.items():
                if isinstance(packages_dict, dict):
                    for package_name, package_info in packages_dict.items():
                        version = package_info.get(
                            "resolved", package_info.get("requested", "")
                        )
                        packages.append(
                            PackageInfo(
                                name=package_name,
                                ecosystem="csharp",
                                version=version,
                                registry_url=f"https://www.nuget.org/packages/{package_name}",
                            )
                        )

            return packages
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid lockfile format: {lockfile_path}") from e

    def detect_lockfiles(self, directory: str | Path) -> list[Path]:
        """
        Detect packages.lock.json files in the directory.

        Args:
            directory: Directory to scan.

        Returns:
            List of Path objects pointing to packages.lock.json files.
        """
        directory = Path(directory)
        lockfiles = []

        # Look for packages.lock.json in current directory
        if (directory / "packages.lock.json").exists():
            lockfiles.append(directory / "packages.lock.json")

        # Recursively search subdirectories
        for subdir in directory.rglob("packages.lock.json"):
            if subdir not in lockfiles:
                lockfiles.append(subdir)

        return lockfiles

    def get_manifest_files(self) -> list[str]:
        """
        Return list of C# manifest files.

        Returns:
            List of manifest file names.
        """
        return ["*.csproj", "*.vbproj", "packages.config", "packages.lock.json"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse a C# manifest file (.csproj, .vbproj, packages.config).

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

        if filename.endswith(".csproj") or filename.endswith(".vbproj"):
            return self._parse_project_file(manifest_path)
        elif filename == "packages.config":
            return self._parse_packages_config(manifest_path)
        else:
            raise ValueError(f"Unknown C# manifest file type: {filename}")

    @staticmethod
    def _parse_project_file(manifest_path: Path) -> list[PackageInfo]:
        """Parse .csproj or .vbproj file."""
        try:
            import xml.etree.ElementTree as ET
        except ImportError as e:
            raise ValueError(
                "xml.etree.ElementTree is required to parse project files"
            ) from e

        packages = []

        try:
            tree = ET.parse(manifest_path)
            root = tree.getroot()

            # Find all PackageReference elements
            for pkg_ref in root.findall(".//PackageReference"):
                include = pkg_ref.get("Include")
                version = pkg_ref.get("Version")

                if include:
                    packages.append(
                        PackageInfo(
                            name=include,
                            ecosystem="csharp",
                            version=version,
                        )
                    )

            return packages
        except Exception as e:
            raise ValueError(f"Failed to parse project file: {e}") from e

    @staticmethod
    def _parse_packages_config(manifest_path: Path) -> list[PackageInfo]:
        """Parse packages.config file."""
        try:
            import xml.etree.ElementTree as ET
        except ImportError as e:
            raise ValueError(
                "xml.etree.ElementTree is required to parse packages.config"
            ) from e

        packages = []

        try:
            tree = ET.parse(manifest_path)
            root = tree.getroot()

            # Find all package elements
            for pkg in root.findall(".//package"):
                pkg_id = pkg.get("id")
                version = pkg.get("version")

                if pkg_id:
                    packages.append(
                        PackageInfo(
                            name=pkg_id,
                            ecosystem="csharp",
                            version=version,
                        )
                    )

            return packages
        except Exception as e:
            raise ValueError(f"Failed to parse packages.config: {e}") from e

    @staticmethod
    def _parse_github_url(url: str) -> tuple[str, str] | None:
        """
        Parse GitHub URL and extract owner and repo.

        Args:
            url: GitHub URL in format https://github.com/owner/repo[.git]
                 or other git URLs

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

        # Handle other git hosting URLs
        # Try to extract last two path components as owner/repo
        parts = url.rstrip("/").split("/")
        if len(parts) >= 2:
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
