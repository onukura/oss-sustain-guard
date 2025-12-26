"""
R package resolver (CRAN).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.repository import RepositoryReference, parse_repository_url
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class RResolver(LanguageResolver):
    """Resolver for R packages (CRAN)."""

    @property
    def ecosystem_name(self) -> str:
        return "r"

    def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """
        Resolve an R package to a repository URL.

        Args:
            package_name: The package name on CRAN.

        Returns:
            RepositoryReference if a supported repository URL is found, otherwise None.
        """
        try:
            with httpx.Client(verify=get_verify_ssl()) as client:
                response = client.get(
                    f"https://crandb.r-pkg.org/{package_name}", timeout=10
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            print(f"Error fetching CRAN data for {package_name}: {e}")
            return None

        url_fields = [
            data.get("URL"),
            data.get("BugReports"),
            data.get("Repository"),
            data.get("Homepage"),
        ]

        for url_field in url_fields:
            for candidate in _split_urls(url_field):
                repo = parse_repository_url(candidate)
                if repo:
                    return repo

        return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse renv.lock and extract package information.

        Args:
            lockfile_path: Path to renv.lock.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
            ValueError: If the lockfile format is invalid.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        if lockfile_path.name != "renv.lock":
            raise ValueError(f"Unknown R lockfile type: {lockfile_path.name}")

        try:
            with open(lockfile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse renv.lock: {e}") from e

        packages = []
        for name, info in (data.get("Packages") or {}).items():
            if not isinstance(info, dict) or not name:
                continue
            version = (
                info.get("Version") if isinstance(info.get("Version"), str) else None
            )
            packages.append(
                PackageInfo(
                    name=name,
                    ecosystem="r",
                    version=version,
                    registry_url=f"https://cran.r-project.org/package={name}",
                )
            )

        return packages

    def detect_lockfiles(self, directory: str) -> list[Path]:
        """
        Detect R lockfiles in the directory.

        Args:
            directory: Directory to search for lockfiles.

        Returns:
            List of lockfile paths.
        """
        dir_path = Path(directory)
        lockfile = dir_path / "renv.lock"
        return [lockfile] if lockfile.exists() else []

    def get_manifest_files(self) -> list[str]:
        """Get R manifest file names."""
        return ["DESCRIPTION"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse an R DESCRIPTION file and extract dependencies.

        Args:
            manifest_path: Path to DESCRIPTION.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name != "DESCRIPTION":
            raise ValueError(f"Unknown R manifest file type: {manifest_path.name}")

        return _parse_description(manifest_path)


def _split_urls(value: object) -> list[str]:
    """Split a CRAN URL field into candidate URLs."""
    if not isinstance(value, str):
        return []
    candidates = []
    for piece in re.split(r"[\s,]+", value):
        cleaned = piece.strip()
        if cleaned:
            candidates.append(cleaned)
    return candidates


def _parse_description(manifest_path: Path) -> list[PackageInfo]:
    """Parse an R DESCRIPTION file for dependency names."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        raise ValueError(f"Failed to read DESCRIPTION: {e}") from e

    fields: dict[str, str] = {}
    current_key: str | None = None

    for line in lines:
        if not line.strip():
            current_key = None
            continue

        if line.startswith(" ") and current_key:
            fields[current_key] = f"{fields[current_key]} {line.strip()}".strip()
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            fields[current_key] = value.strip()

    dependency_fields = ["Imports", "Depends", "Suggests", "LinkingTo"]
    packages = []
    seen = set()

    for field in dependency_fields:
        raw_value = fields.get(field)
        if not raw_value:
            continue
        for entry in raw_value.split(","):
            name = entry.strip().split("(")[0].strip()
            if not name or name in seen:
                continue
            seen.add(name)
            packages.append(
                PackageInfo(
                    name=name,
                    ecosystem="r",
                )
            )

    return packages
