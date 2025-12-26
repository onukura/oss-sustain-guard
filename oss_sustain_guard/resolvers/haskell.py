"""
Haskell package resolver (Hackage).
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.repository import RepositoryReference, parse_repository_url
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class HaskellResolver(LanguageResolver):
    """Resolver for Haskell packages via Hackage."""

    @property
    def ecosystem_name(self) -> str:
        return "haskell"

    def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """
        Resolve a Haskell package to a repository URL.

        Strategy:
        1. Get latest version from package JSON
        2. Fetch cabal file for that version
        3. Parse source-repository field

        Args:
            package_name: The package name on Hackage.

        Returns:
            RepositoryReference if a supported repository URL is found, otherwise None.
        """
        try:
            with httpx.Client(verify=get_verify_ssl()) as client:
                # First, get the package versions to find the latest
                versions_response = client.get(
                    f"https://hackage.haskell.org/package/{package_name}.json",
                    timeout=10,
                )
                if versions_response.status_code == 404:
                    return None
                versions_response.raise_for_status()
                versions_data = versions_response.json()

                # Get the latest version using semantic version sorting
                versions = list(versions_data.keys())
                if not versions:
                    return None

                # Sort versions by semantic versioning rules
                def version_key(v: str) -> tuple[int, ...]:
                    """Convert version string to tuple of integers for proper sorting."""
                    try:
                        return tuple(int(x) for x in v.split("."))
                    except ValueError:
                        # Fallback for non-numeric versions
                        return (0,)

                latest_version = max(versions, key=version_key)

                # Fetch the cabal file for the latest version
                cabal_response = client.get(
                    f"https://hackage.haskell.org/package/{package_name}-{latest_version}/{package_name}.cabal",
                    timeout=10,
                )
                if cabal_response.status_code == 404:
                    return None
                cabal_response.raise_for_status()
                cabal_content = cabal_response.text

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(f"Error fetching Hackage data for {package_name}: {e}")
            return None

        # Parse source-repository from cabal file
        for url in _extract_cabal_repo_urls(cabal_content):
            repo = parse_repository_url(url)
            if repo:
                return repo

        return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse Haskell lockfiles and extract package information.

        Supports: cabal.project.freeze, stack.yaml.lock

        Args:
            lockfile_path: Path to the lockfile.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
            ValueError: If the lockfile format is invalid.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        if lockfile_path.name == "cabal.project.freeze":
            return _parse_cabal_freeze(lockfile_path)
        if lockfile_path.name == "stack.yaml.lock":
            return _parse_stack_lock(lockfile_path)

        raise ValueError(f"Unknown Haskell lockfile type: {lockfile_path.name}")

    def detect_lockfiles(self, directory: str) -> list[Path]:
        """
        Detect Haskell lockfiles in the directory.

        Args:
            directory: Directory to search for lockfiles.

        Returns:
            List of lockfile paths.
        """
        dir_path = Path(directory)
        lockfiles = []
        cabal_freeze = dir_path / "cabal.project.freeze"
        stack_lock = dir_path / "stack.yaml.lock"
        if cabal_freeze.exists():
            lockfiles.append(cabal_freeze)
        if stack_lock.exists():
            lockfiles.append(stack_lock)
        return lockfiles

    def get_manifest_files(self) -> list[str]:
        """Get Haskell manifest file names."""
        return ["cabal.project", "stack.yaml", "package.yaml"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse Haskell manifest files and extract package information.

        Args:
            manifest_path: Path to the manifest file.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name == "cabal.project":
            return _parse_cabal_project(manifest_path)
        if manifest_path.name in {"stack.yaml", "package.yaml"}:
            return _parse_stack_manifest(manifest_path)

        raise ValueError(f"Unknown Haskell manifest file type: {manifest_path.name}")


def _extract_cabal_repo_urls(cabal_content: str) -> list[str]:
    """
    Extract repository URLs from cabal file content.

    Parses source-repository sections and bug-reports field.

    Args:
        cabal_content: Content of the .cabal file.

    Returns:
        List of repository URLs found.
    """
    urls: list[str] = []

    # Parse source-repository blocks (multi-line format)
    # Format:
    #   source-repository head
    #     type: git
    #     location: https://github.com/owner/repo
    #
    # Use DOTALL to match across newlines
    repo_pattern = re.compile(
        r"source-repository\s+\w+.*?location:\s*(.+?)(?:\n|$)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    for match in repo_pattern.finditer(cabal_content):
        url = match.group(1).strip()
        if url:
            urls.append(url)

    # Also check Bug-reports field (often contains GitHub issues URL)
    bug_pattern = re.compile(r"bug-reports:\s*(.+?)(?:\n|$)", re.IGNORECASE)
    for match in bug_pattern.finditer(cabal_content):
        url = match.group(1).strip()
        # Extract repo URL from issues URL (e.g., https://github.com/owner/repo/issues)
        if "/issues" in url:
            url = url.split("/issues")[0]
        if url:
            urls.append(url)

    return urls


def _parse_cabal_freeze(lockfile_path: Path) -> list[PackageInfo]:
    """Parse cabal.project.freeze file."""
    try:
        content = lockfile_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Failed to read cabal.project.freeze: {e}") from e

    packages = []
    seen = set()
    pattern = re.compile(r"any\.([A-Za-z0-9_.-]+)\s*==\s*([^,\s]+)")

    for match in pattern.finditer(content):
        name, version = match.groups()
        if name in seen:
            continue
        seen.add(name)
        packages.append(
            PackageInfo(
                name=name,
                ecosystem="haskell",
                version=version,
                registry_url=f"https://hackage.haskell.org/package/{name}",
            )
        )

    return packages


def _parse_stack_lock(lockfile_path: Path) -> list[PackageInfo]:
    """Parse stack.yaml.lock file."""
    try:
        content = lockfile_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Failed to read stack.yaml.lock: {e}") from e

    packages = []
    seen = set()
    pattern = re.compile(r"hackage:\s+([A-Za-z0-9_.-]+)-([0-9][^@\s]*)")

    for match in pattern.finditer(content):
        name, version = match.groups()
        if name in seen:
            continue
        seen.add(name)
        packages.append(
            PackageInfo(
                name=name,
                ecosystem="haskell",
                version=version,
                registry_url=f"https://hackage.haskell.org/package/{name}",
            )
        )

    return packages


def _parse_cabal_project(manifest_path: Path) -> list[PackageInfo]:
    """Parse cabal.project for dependency constraints."""
    try:
        content = manifest_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Failed to read cabal.project: {e}") from e

    packages = []
    seen = set()
    pattern = re.compile(r"any\.([A-Za-z0-9_.-]+)")

    for match in pattern.finditer(content):
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        packages.append(PackageInfo(name=name, ecosystem="haskell"))

    return packages


def _parse_stack_manifest(manifest_path: Path) -> list[PackageInfo]:
    """Parse stack.yaml or package.yaml for extra dependency entries."""
    try:
        content = manifest_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Failed to read {manifest_path.name}: {e}") from e

    packages = []
    seen = set()
    # Match package names with optional version suffix (e.g., "text-1.2.5.0")
    pattern = re.compile(r"^\s*-\s*([A-Za-z0-9_.-]+?)(?:-[0-9][^\s]*)?\s*$")

    for line in content.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        raw_name = match.group(1)
        # Strip version suffix if present (e.g., "text-1.2.5.0" -> "text")
        name = re.sub(r"-[0-9]+(?:\.[0-9]+)*$", "", raw_name)
        if name in seen:
            continue
        seen.add(name)
        packages.append(PackageInfo(name=name, ecosystem="haskell"))

    return packages
