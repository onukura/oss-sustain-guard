"""
Base abstraction for language-specific package resolvers.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import NamedTuple


class PackageInfo(NamedTuple):
    """Unified package information across all languages."""

    name: str
    ecosystem: str
    version: str | None = None
    registry_url: str | None = None


class LanguageResolver(ABC):
    """Base class for language-specific package resolvers."""

    @property
    @abstractmethod
    def ecosystem_name(self) -> str:
        """Return the ecosystem name (e.g., 'python', 'javascript')."""
        pass

    @abstractmethod
    def resolve_github_url(self, package_name: str) -> tuple[str, str] | None:
        """
        Resolve package name to GitHub (owner, repo).

        Args:
            package_name: Package name in the ecosystem's format.

        Returns:
            Tuple of (owner, repo) or None if not found.

        Raises:
            Exception: If there's an error querying the registry.
        """
        pass

    @abstractmethod
    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse a lockfile and extract package information.

        Args:
            lockfile_path: Path to the lockfile.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
            ValueError: If the lockfile format is invalid.
        """
        pass

    @abstractmethod
    def detect_lockfiles(self, directory: str) -> list[Path]:
        """
        Detect lockfiles for this ecosystem in the given directory.

        Args:
            directory: Directory to search.

        Returns:
            List of lockfile paths that exist (may be empty).
        """
        pass

    @abstractmethod
    def get_manifest_files(self) -> list[str]:
        """
        Return list of manifest file names for this ecosystem.

        Returns:
            List of file names (e.g., ['package.json', 'requirements.txt']).
        """
        pass

    @abstractmethod
    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse a manifest file and extract package information.

        Args:
            manifest_path: Path to the manifest file (e.g., package.json, requirements.txt).

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(ecosystem='{self.ecosystem_name}')"
