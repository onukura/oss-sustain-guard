"""
Perl package resolver (CPAN).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.repository import RepositoryReference, parse_repository_url
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class PerlResolver(LanguageResolver):
    """Resolver for Perl packages via MetaCPAN."""

    @property
    def ecosystem_name(self) -> str:
        return "perl"

    def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """
        Resolve a Perl package to a repository URL.

        Args:
            package_name: The distribution name on CPAN.

        Returns:
            RepositoryReference if a supported repository URL is found, otherwise None.
        """
        try:
            with httpx.Client(verify=get_verify_ssl()) as client:
                response = client.get(
                    f"https://fastapi.metacpan.org/v1/release/{package_name}",
                    timeout=10,
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            print(f"Error fetching MetaCPAN data for {package_name}: {e}")
            return None

        resources = data.get("resources", {}) if isinstance(data, dict) else {}
        repository = (
            resources.get("repository", {}) if isinstance(resources, dict) else {}
        )

        candidates = []
        if isinstance(repository, dict):
            url = repository.get("url")
            if isinstance(url, str) and url:
                candidates.append(url)
            web = repository.get("web")
            if isinstance(web, str) and web:
                candidates.append(web)

        for candidate in candidates:
            repo = parse_repository_url(candidate)
            if repo:
                return repo

        return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse cpanfile.snapshot and extract package information.

        Args:
            lockfile_path: Path to cpanfile.snapshot.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
            ValueError: If the lockfile format is invalid.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        if lockfile_path.name != "cpanfile.snapshot":
            raise ValueError(f"Unknown Perl lockfile type: {lockfile_path.name}")

        try:
            content = lockfile_path.read_text(encoding="utf-8")
        except OSError as e:
            raise ValueError(f"Failed to read cpanfile.snapshot: {e}") from e

        packages = []
        seen = set()
        pattern = re.compile(r"distribution:\s*([A-Za-z0-9_.:-]+)")

        for match in pattern.finditer(content):
            raw_name = match.group(1)
            name = _strip_distribution_version(raw_name)
            if name in seen:
                continue
            seen.add(name)
            packages.append(
                PackageInfo(
                    name=name,
                    ecosystem="perl",
                    registry_url=f"https://metacpan.org/release/{name}",
                )
            )

        return packages

    def detect_lockfiles(self, directory: str) -> list[Path]:
        """
        Detect Perl lockfiles in the directory.

        Args:
            directory: Directory to search for lockfiles.

        Returns:
            List of lockfile paths.
        """
        dir_path = Path(directory)
        lockfile = dir_path / "cpanfile.snapshot"
        return [lockfile] if lockfile.exists() else []

    def get_manifest_files(self) -> list[str]:
        """Get Perl manifest file names."""
        return ["cpanfile"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse cpanfile and extract package information.

        Args:
            manifest_path: Path to cpanfile.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name != "cpanfile":
            raise ValueError(f"Unknown Perl manifest file type: {manifest_path.name}")

        try:
            content = manifest_path.read_text(encoding="utf-8")
        except OSError as e:
            raise ValueError(f"Failed to read cpanfile: {e}") from e

        packages = []
        seen = set()
        pattern = re.compile(r"requires\s+['\"]([^'\"]+)['\"]")

        for match in pattern.finditer(content):
            name = match.group(1)
            if name in seen:
                continue
            seen.add(name)
            packages.append(PackageInfo(name=name, ecosystem="perl"))

        return packages


def _strip_distribution_version(name: str) -> str:
    """Strip version suffix from CPAN distribution names."""
    match = re.match(r"^(?P<base>.+)-\d", name)
    if match:
        return match.group("base")
    return name
