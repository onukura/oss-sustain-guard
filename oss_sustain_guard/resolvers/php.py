"""
PHP package resolver for Composer/Packagist.
"""

import json
from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class PhpResolver(LanguageResolver):
    """Resolver for PHP packages (Composer/Packagist)."""

    PACKAGIST_API_URL = "https://repo.packagist.org/p2"

    @property
    def ecosystem_name(self) -> str:
        return "php"

    def resolve_github_url(self, package_name: str) -> tuple[str, str] | None:
        """
        Fetches package information from Packagist V2 API and extracts GitHub URL.

        Args:
            package_name: The name of the package in vendor/package format.

        Returns:
            A tuple of (owner, repo_name) if a GitHub URL is found, otherwise None.
        """
        try:
            with httpx.Client(verify=get_verify_ssl()) as client:
                response = client.get(
                    f"{self.PACKAGIST_API_URL}/{package_name}.json",
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()

            # Extract repository URL from package metadata
            packages = data.get("packages", {})
            if not packages:
                return None

            # Get the first available package version
            package_versions = list(packages.values())
            if not package_versions:
                return None

            package_data = package_versions[0]
            if isinstance(package_data, list):
                if not package_data:
                    return None
                package_data = package_data[0]

            # Look for repository URL in source or support
            source = package_data.get("source", {})
            if isinstance(source, dict):
                repository_url = source.get("url", "")
                if repository_url:
                    return self._parse_github_url(repository_url)

            # Fallback to support section
            support = package_data.get("support", {})
            if isinstance(support, dict):
                source_url = support.get("source", "")
                if source_url:
                    return self._parse_github_url(source_url)

            return None
        except httpx.HTTPStatusError as e:
            # Return None for 404 errors (package not found)
            print(f"Error fetching PHP data for {package_name}: {e}")
            if e.response.status_code == 404:
                return None
            raise
        except (httpx.RequestError, ValueError, KeyError) as e:
            print(f"Error fetching PHP data for {package_name}: {e}")
            return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse composer.lock and extract package information.

        Args:
            lockfile_path: Path to composer.lock file.

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
            for pkg_entry in data.get("packages", []):
                if isinstance(pkg_entry, dict):
                    packages.append(
                        PackageInfo(
                            name=pkg_entry.get("name", ""),
                            ecosystem="php",
                            version=pkg_entry.get("version", ""),
                            registry_url="https://packagist.org/packages/"
                            + pkg_entry.get("name", ""),
                        )
                    )

            return packages
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid lockfile format: {lockfile_path}") from e

    def detect_lockfiles(self, directory: str | Path) -> list[Path]:
        """
        Detect composer.lock files in the directory.

        Args:
            directory: Directory to scan.

        Returns:
            List of Path objects pointing to composer.lock files.
        """
        directory = Path(directory)
        lockfiles = []

        if (directory / "composer.lock").exists():
            lockfiles.append(directory / "composer.lock")

        # Recursively search subdirectories
        for subdir in directory.rglob("composer.lock"):
            if subdir not in lockfiles:
                lockfiles.append(subdir)

        return lockfiles

    def get_manifest_files(self) -> list[str]:
        """
        Return list of PHP manifest files.

        Returns:
            List of manifest file names.
        """
        return ["composer.json", "composer.lock"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse a PHP manifest file (composer.json).

        Args:
            manifest_path: Path to composer.json.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name != "composer.json":
            raise ValueError(f"Unknown PHP manifest file type: {manifest_path.name}")

        return self._parse_composer_json(manifest_path)

    @staticmethod
    def _parse_composer_json(manifest_path: Path) -> list[PackageInfo]:
        """Parse composer.json file."""
        import json

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            packages = []

            # Collect dependencies from all sections
            for section in ("require", "require-dev"):
                deps = data.get(section, {})
                if isinstance(deps, dict):
                    for package_name, version in deps.items():
                        packages.append(
                            PackageInfo(
                                name=package_name,
                                ecosystem="php",
                                version=version if isinstance(version, str) else None,
                            )
                        )

            return packages
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Failed to parse composer.json: {e}") from e

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
