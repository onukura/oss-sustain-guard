"""
PHP package resolver for Composer/Packagist.
"""

import json
import sys
from pathlib import Path

import aiofiles
import httpx

from oss_sustain_guard.http_client import _get_async_http_client
from oss_sustain_guard.repository import RepositoryReference, parse_repository_url
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class PhpResolver(LanguageResolver):
    """Resolver for PHP packages (Composer/Packagist)."""

    PACKAGIST_API_URL = "https://repo.packagist.org/p2"

    @property
    def ecosystem_name(self) -> str:
        return "php"

    async def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """
        Fetches package information from Packagist V2 API and extracts repository URL.

        Args:
            package_name: The name of the package in vendor/package format.

        Returns:
            RepositoryReference if a supported repository URL is found, otherwise None.
        """
        try:
            client = await _get_async_http_client()
            response = await client.get(
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
                    repo = parse_repository_url(repository_url)
                    if repo:
                        return repo

            # Fallback to support section
            support = package_data.get("support", {})
            if isinstance(support, dict):
                source_url = support.get("source", "")
                if source_url:
                    repo = parse_repository_url(source_url)
                    if repo:
                        return repo

            return None
        except httpx.HTTPStatusError as e:
            # Return None for 404 errors (package not found)
            print(
                f"Note: Unable to fetch PHP data for {package_name}: {e}",
                file=sys.stderr,
            )
            if e.response.status_code == 404:
                return None
            raise
        except (httpx.RequestError, ValueError, KeyError) as e:
            print(
                f"Note: Unable to fetch PHP data for {package_name}: {e}",
                file=sys.stderr,
            )
            return None

    async def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
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
            async with aiofiles.open(lockfile_path, "r", encoding="utf-8") as f:
                data = json.loads(await f.read())

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

    async def detect_lockfiles(self, directory: str | Path) -> list[Path]:
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

    async def get_manifest_files(self) -> list[str]:
        """
        Return list of PHP manifest files.

        Returns:
            List of manifest file names.
        """
        return ["composer.json", "composer.lock"]

    async def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
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

        return await self._parse_composer_json(manifest_path)

    @staticmethod
    async def _parse_composer_json(manifest_path: Path) -> list[PackageInfo]:
        """Parse composer.json file."""
        import json

        try:
            async with aiofiles.open(manifest_path, "r", encoding="utf-8") as f:
                data = json.loads(await f.read())

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


RESOLVER = PhpResolver()
