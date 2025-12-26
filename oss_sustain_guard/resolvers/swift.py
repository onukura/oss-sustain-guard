"""
Swift package resolver (Swift Package Manager).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from oss_sustain_guard.repository import RepositoryReference, parse_repository_url
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class SwiftResolver(LanguageResolver):
    """Resolver for Swift packages (Swift Package Manager)."""

    @property
    def ecosystem_name(self) -> str:
        return "swift"

    def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """
        Resolve a Swift package name to a repository reference.

        Args:
            package_name: The Swift package identifier or repository path.

        Returns:
            RepositoryReference if a supported repository URL is found, otherwise None.
        """
        candidate = package_name.strip()
        if not candidate:
            return None

        if candidate.startswith("git@") or "://" in candidate:
            return parse_repository_url(candidate)

        if candidate.startswith("github.com/") or candidate.startswith("gitlab.com/"):
            return parse_repository_url(candidate)

        if "/" in candidate:
            return parse_repository_url(f"https://github.com/{candidate}")

        return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse Package.resolved and extract package information.

        Args:
            lockfile_path: Path to Package.resolved.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
            ValueError: If the lockfile format is invalid.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        if lockfile_path.name != "Package.resolved":
            raise ValueError(f"Unknown Swift lockfile type: {lockfile_path.name}")

        try:
            with open(lockfile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Package.resolved: {e}") from e

        pins = data.get("pins")
        if pins is None:
            pins = data.get("object", {}).get("pins", [])

        packages = []
        for pin in pins or []:
            if not isinstance(pin, dict):
                continue
            location = pin.get("location") or pin.get("repositoryURL")
            if not isinstance(location, str):
                continue
            state = pin.get("state", {}) if isinstance(pin.get("state"), dict) else {}
            version = (
                state.get("version") if isinstance(state.get("version"), str) else None
            )
            repo = parse_repository_url(location)
            name = f"{repo.owner}/{repo.name}" if repo else location
            packages.append(
                PackageInfo(
                    name=name,
                    ecosystem="swift",
                    version=version,
                    registry_url=location,
                )
            )

        return packages

    def detect_lockfiles(self, directory: str) -> list[Path]:
        """
        Detect Swift lockfiles in the directory.

        Args:
            directory: Directory to search for lockfiles.

        Returns:
            List of lockfile paths.
        """
        dir_path = Path(directory)
        lockfile = dir_path / "Package.resolved"
        return [lockfile] if lockfile.exists() else []

    def get_manifest_files(self) -> list[str]:
        """Get Swift manifest file names."""
        return ["Package.swift"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse Package.swift and extract package information.

        Args:
            manifest_path: Path to Package.swift.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name != "Package.swift":
            raise ValueError(f"Unknown Swift manifest file type: {manifest_path.name}")

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            raise ValueError(f"Failed to read Package.swift: {e}") from e

        packages = []
        seen = set()
        for url in _extract_package_urls(content):
            repo = parse_repository_url(url)
            name = f"{repo.owner}/{repo.name}" if repo else url
            if name in seen:
                continue
            seen.add(name)
            packages.append(
                PackageInfo(
                    name=name,
                    ecosystem="swift",
                    registry_url=url,
                )
            )

        return packages


def _extract_package_urls(content: str) -> list[str]:
    """Extract package URLs from a Package.swift manifest."""
    pattern = re.compile(r"package\s*\(\s*url:\s*[\"']([^\"']+)[\"']")
    return pattern.findall(content)
