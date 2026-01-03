"""
Dart package resolver (pub.dev).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import aiofiles
import httpx

from oss_sustain_guard.http_client import _get_async_http_client
from oss_sustain_guard.repository import RepositoryReference, parse_repository_url
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class DartResolver(LanguageResolver):
    """Resolver for Dart packages via pub.dev."""

    @property
    def ecosystem_name(self) -> str:
        return "dart"

    async def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """
        Resolve a Dart package to a repository URL.

        Args:
            package_name: The package name on pub.dev.

        Returns:
            RepositoryReference if a supported repository URL is found, otherwise None.
        """
        try:
            client = await _get_async_http_client()
            response = await client.get(
                f"https://pub.dev/api/packages/{package_name}", timeout=10
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            print(
                f"Note: Unable to fetch pub.dev data for {package_name}: {e}",
                file=sys.stderr,
            )
            return None

        latest = data.get("latest", {}) if isinstance(data, dict) else {}
        pubspec = latest.get("pubspec", {}) if isinstance(latest, dict) else {}

        candidates = []
        for key in ("repository", "homepage"):
            value = pubspec.get(key)
            if isinstance(value, str) and value:
                candidates.append(value)

        for candidate in candidates:
            repo = parse_repository_url(candidate)
            if repo:
                return repo

        return None

    async def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse pubspec.lock and extract package information.

        Args:
            lockfile_path: Path to pubspec.lock.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
            ValueError: If the lockfile format is invalid.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        if lockfile_path.name != "pubspec.lock":
            raise ValueError(f"Unknown Dart lockfile type: {lockfile_path.name}")

        try:
            async with aiofiles.open(lockfile_path, "r", encoding="utf-8") as f:
                content = await f.read()
        except OSError as e:
            raise ValueError(f"Failed to read pubspec.lock: {e}") from e

        packages = []
        seen = set()
        in_packages = False
        for line in content.splitlines():
            if line.strip() == "packages:":
                in_packages = True
                continue
            if not in_packages:
                continue
            if line and not line.startswith(" "):
                break
            # Only match lines with exactly 2 spaces (package names)
            # Skip lines with 4+ spaces (package properties like "dependency:")
            if line.startswith("  ") and not line.startswith("    ") and ":" in line:
                name = line.strip().split(":", 1)[0]
                if name and name not in seen:
                    seen.add(name)
                    packages.append(PackageInfo(name=name, ecosystem="dart"))

        return packages

    async def detect_lockfiles(self, directory: str) -> list[Path]:
        """
        Detect Dart lockfiles in the directory.

        Args:
            directory: Directory to search for lockfiles.

        Returns:
            List of lockfile paths.
        """
        dir_path = Path(directory)
        lockfile = dir_path / "pubspec.lock"
        return [lockfile] if lockfile.exists() else []

    async def get_manifest_files(self) -> list[str]:
        """Get Dart manifest file names."""
        return ["pubspec.yaml"]

    async def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse pubspec.yaml and extract package information.

        Args:
            manifest_path: Path to pubspec.yaml.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name != "pubspec.yaml":
            raise ValueError(f"Unknown Dart manifest file type: {manifest_path.name}")

        try:
            async with aiofiles.open(manifest_path, "r", encoding="utf-8") as f:
                content = await f.read()
        except OSError as e:
            raise ValueError(f"Failed to read pubspec.yaml: {e}") from e

        packages = []
        seen = set()
        in_dependencies = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped in {
                "dependencies:",
                "dev_dependencies:",
                "dependency_overrides:",
            }:
                in_dependencies = True
                continue
            if line and not line.startswith(" "):
                in_dependencies = False
            if not in_dependencies:
                continue
            if line.startswith("  ") and ":" in line:
                name = line.strip().split(":", 1)[0]
                if name and name not in seen:
                    seen.add(name)
                    packages.append(PackageInfo(name=name, ecosystem="dart"))

        return packages


RESOLVER = DartResolver()
