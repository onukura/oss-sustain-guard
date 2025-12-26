"""
Elixir package resolver (Hex.pm).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.repository import RepositoryReference, parse_repository_url
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class ElixirResolver(LanguageResolver):
    """Resolver for Elixir packages via Hex.pm."""

    @property
    def ecosystem_name(self) -> str:
        return "elixir"

    def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """
        Resolve an Elixir package to a repository URL.

        Args:
            package_name: The package name on Hex.pm.

        Returns:
            RepositoryReference if a supported repository URL is found, otherwise None.
        """
        try:
            with httpx.Client(verify=get_verify_ssl()) as client:
                response = client.get(
                    f"https://hex.pm/api/packages/{package_name}", timeout=10
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            print(f"Error fetching Hex.pm data for {package_name}: {e}")
            return None

        meta = data.get("meta", {})
        links = meta.get("links", {}) if isinstance(meta, dict) else {}

        candidates = []
        if isinstance(links, dict):
            for value in links.values():
                if isinstance(value, str) and value:
                    candidates.append(value)

        for candidate in candidates:
            repo = parse_repository_url(candidate)
            if repo:
                return repo

        return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse mix.lock and extract package information.

        Args:
            lockfile_path: Path to mix.lock.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
            ValueError: If the lockfile format is invalid.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        if lockfile_path.name != "mix.lock":
            raise ValueError(f"Unknown Elixir lockfile type: {lockfile_path.name}")

        try:
            content = lockfile_path.read_text(encoding="utf-8")
        except OSError as e:
            raise ValueError(f"Failed to read mix.lock: {e}") from e

        packages = []
        seen = set()
        pattern = re.compile(r'"([A-Za-z0-9_-]+)"\s*:\s*\{\s*:hex')
        for match in pattern.finditer(content):
            name = match.group(1)
            if name in seen:
                continue
            seen.add(name)
            packages.append(PackageInfo(name=name, ecosystem="elixir"))

        return packages

    def detect_lockfiles(self, directory: str) -> list[Path]:
        """
        Detect Elixir lockfiles in the directory.

        Args:
            directory: Directory to search for lockfiles.

        Returns:
            List of lockfile paths.
        """
        dir_path = Path(directory)
        lockfile = dir_path / "mix.lock"
        return [lockfile] if lockfile.exists() else []

    def get_manifest_files(self) -> list[str]:
        """Get Elixir manifest file names."""
        return ["mix.exs"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse mix.exs and extract package information.

        Args:
            manifest_path: Path to mix.exs.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name != "mix.exs":
            raise ValueError(f"Unknown Elixir manifest file type: {manifest_path.name}")

        try:
            content = manifest_path.read_text(encoding="utf-8")
        except OSError as e:
            raise ValueError(f"Failed to read mix.exs: {e}") from e

        deps_block = _extract_deps_block(content)
        if not deps_block:
            return []

        packages = []
        seen = set()
        pattern = re.compile(r"\{\s*:(\w+)")
        for match in pattern.finditer(deps_block):
            name = match.group(1)
            if name in seen:
                continue
            seen.add(name)
            packages.append(PackageInfo(name=name, ecosystem="elixir"))

        return packages


def _extract_deps_block(content: str) -> str | None:
    """Extract the deps list block from mix.exs."""
    match = re.search(r"defp\s+deps\s+do(.*?)end", content, re.DOTALL)
    if not match:
        return None
    return match.group(1)
