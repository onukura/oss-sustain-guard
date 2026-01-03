"""
Python/PyPI package resolver.
"""

import json
import sys
from pathlib import Path

import aiofiles
import httpx

from oss_sustain_guard.http_client import _get_async_http_client
from oss_sustain_guard.repository import RepositoryReference, parse_repository_url
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class PythonResolver(LanguageResolver):
    """Resolver for Python packages (PyPI)."""

    @property
    def ecosystem_name(self) -> str:
        return "python"

    async def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """
        Fetches package information from the PyPI JSON API and extracts repository URL.

        Args:
            package_name: The name of the package on PyPI.

        Returns:
            RepositoryReference if a supported repository URL is found, otherwise None.
        """
        try:
            client = await _get_async_http_client()
            response = await client.get(
                f"https://pypi.org/pypi/{package_name}/json", timeout=10
            )
            response.raise_for_status()
            data = response.json()

            project_urls = data.get("info", {}).get("project_urls", {})

            # A list of common keys for the source repository
            url_keys = [
                "Source",
                "Source Code",
                "Repository",
                "Homepage",
            ]

            url_candidates: list[str] = []
            if project_urls:  # Ensure project_urls is not None or empty
                for key in url_keys:
                    value = project_urls.get(key)
                    if isinstance(value, str) and value:
                        url_candidates.append(value)

                for url in project_urls.values():
                    if isinstance(url, str) and url:
                        url_candidates.append(url)

            home_page = data.get("info", {}).get("home_page")
            if isinstance(home_page, str) and home_page:
                url_candidates.append(home_page)

            for candidate in url_candidates:
                repo = parse_repository_url(candidate)
                if repo:
                    return repo

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(
                f"Note: Unable to fetch PyPI data for {package_name}: {e}",
                file=sys.stderr,
            )
            return None

        return None

    async def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Auto-detects Python lockfile type and extracts package information.

        Supports: poetry.lock, uv.lock, Pipfile.lock

        Args:
            lockfile_path: Path to a Python lockfile.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        filename = lockfile_path.name

        if filename == "poetry.lock":
            return await self._parse_lockfile_poetry(lockfile_path)
        elif filename == "uv.lock":
            return await self._parse_lockfile_uv(lockfile_path)
        elif filename == "Pipfile.lock":
            return await self._parse_lockfile_pipenv(lockfile_path)
        else:
            raise ValueError(f"Unknown Python lockfile type: {filename}")

    async def detect_lockfiles(self, directory: str | Path = ".") -> list[Path]:
        """
        Detects Python lockfiles in a directory.

        Args:
            directory: Directory to search for lockfiles. Defaults to current directory.

        Returns:
            List of detected lockfile paths that exist.
        """
        directory = Path(directory)
        lockfile_names = ["poetry.lock", "uv.lock", "Pipfile.lock"]
        detected = []
        for name in lockfile_names:
            lockfile = directory / name
            if lockfile.exists():
                detected.append(lockfile)
        return detected

    async def get_manifest_files(self) -> list[str]:
        """Return list of Python manifest file names."""
        return ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py"]

    async def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse a Python manifest file and extract package information.

        Supports: requirements.txt, pyproject.toml, Pipfile

        Args:
            manifest_path: Path to a Python manifest file.

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

        if filename == "requirements.txt":
            return await self._parse_manifest_requirements(manifest_path)
        elif filename == "pyproject.toml":
            return await self._parse_manifest_pyproject(manifest_path)
        elif filename == "Pipfile":
            return await self._parse_manifest_pipfile(manifest_path)
        else:
            raise ValueError(f"Unknown Python manifest file type: {filename}")

    @staticmethod
    async def _parse_manifest_requirements(manifest_path: Path) -> list[PackageInfo]:
        """Parse requirements.txt file."""
        packages = []
        try:
            async with aiofiles.open(manifest_path, "r", encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue
                    # Extract package name (before ==, >=, <=, etc.)
                    pkg_name = (
                        line.split("==")[0]
                        .split(">=")[0]
                        .split("<=")[0]
                        .split("!=")[0]
                        .split("~=")[0]
                        .split(">")[0]
                        .split("<")[0]
                        .strip()
                    )
                    if pkg_name:
                        packages.append(
                            PackageInfo(
                                name=pkg_name,
                                ecosystem="python",
                            )
                        )
        except Exception:
            pass
        return packages

    @staticmethod
    async def _parse_manifest_pyproject(manifest_path: Path) -> list[PackageInfo]:
        """Parse pyproject.toml file."""
        try:
            import tomllib
        except ImportError:
            # Python < 3.11
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                return []

        packages = []
        try:
            async with aiofiles.open(manifest_path, "rb") as f:
                content = await f.read()
                data = tomllib.loads(content.decode())

            # First, try to extract dependencies from [project] section (PEP 621)
            if "project" in data and "dependencies" in data["project"]:
                for dep in data["project"]["dependencies"]:
                    # Extract package name (before >=, ==, etc.)
                    pkg_name = (
                        dep.split(">=")[0]
                        .split("==")[0]
                        .split("<=")[0]
                        .split("!=")[0]
                        .split("~=")[0]
                        .split(">")[0]
                        .split("<")[0]
                        .split("[")[0]
                        .strip()
                    )
                    if pkg_name:
                        packages.append(
                            PackageInfo(
                                name=pkg_name,
                                ecosystem="python",
                            )
                        )

            # Also check [tool.poetry.dependencies] section (Poetry format)
            if (
                "tool" in data
                and "poetry" in data["tool"]
                and "dependencies" in data["tool"]["poetry"]
            ):
                for pkg_name, version_spec in data["tool"]["poetry"][
                    "dependencies"
                ].items():
                    # Skip the python version constraint
                    if pkg_name.lower() == "python":
                        continue

                    # Handle both string and dict formats
                    # Example: "requests" = "^2.13.0" or "requests" = { version = "^2.13.0" }
                    if isinstance(version_spec, str):
                        # String format is the version constraint
                        if pkg_name:
                            packages.append(
                                PackageInfo(
                                    name=pkg_name,
                                    ecosystem="python",
                                )
                            )

            # Extract optional dependencies from [project.optional-dependencies]
            if "project" in data and "optional-dependencies" in data["project"]:
                for extras_deps in data["project"]["optional-dependencies"].values():
                    if isinstance(extras_deps, list):
                        for dep in extras_deps:
                            # Extract package name (before >=, ==, etc.)
                            pkg_name = (
                                dep.split(">=")[0]
                                .split("==")[0]
                                .split("<=")[0]
                                .split("!=")[0]
                                .split("~=")[0]
                                .split(">")[0]
                                .split("<")[0]
                                .split("[")[0]
                                .strip()
                            )
                            if pkg_name:
                                packages.append(
                                    PackageInfo(
                                        name=pkg_name,
                                        ecosystem="python",
                                    )
                                )

            # Extract dev dependencies from [dependency-groups] section (PDM/PEP 735 format)
            if "dependency-groups" in data:
                for group_deps in data["dependency-groups"].values():
                    if isinstance(group_deps, list):
                        for dep in group_deps:
                            # Extract package name (before >=, ==, etc.)
                            pkg_name = (
                                dep.split(">=")[0]
                                .split("==")[0]
                                .split("<=")[0]
                                .split("!=")[0]
                                .split("~=")[0]
                                .split(">")[0]
                                .split("<")[0]
                                .split("[")[0]
                                .strip()
                            )
                            if pkg_name:
                                packages.append(
                                    PackageInfo(
                                        name=pkg_name,
                                        ecosystem="python",
                                    )
                                )
        except Exception:
            pass
        return packages

    @staticmethod
    async def _parse_manifest_pipfile(manifest_path: Path) -> list[PackageInfo]:
        """Parse Pipfile file."""
        try:
            import tomllib
        except ImportError:
            # Python < 3.11
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                return []

        packages = []
        try:
            async with aiofiles.open(manifest_path, "rb") as f:
                content = await f.read()
                data = tomllib.loads(content.decode())

            # Extract packages from [packages] section
            if "packages" in data:
                for pkg_name in data["packages"].keys():
                    if pkg_name:
                        packages.append(
                            PackageInfo(
                                name=pkg_name,
                                ecosystem="python",
                            )
                        )

            # Also extract dev packages from [dev-packages] section
            if "dev-packages" in data:
                for pkg_name in data["dev-packages"].keys():
                    if pkg_name:
                        packages.append(
                            PackageInfo(
                                name=pkg_name,
                                ecosystem="python",
                            )
                        )
        except Exception:
            pass
        return packages

    @staticmethod
    async def _parse_lockfile_poetry(lockfile_path: Path) -> list[PackageInfo]:
        """Parse poetry.lock file."""
        try:
            import tomllib
        except ImportError:
            # Python < 3.11
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                return []

        try:
            async with aiofiles.open(lockfile_path, "rb") as f:
                content = await f.read()
                data = tomllib.loads(content.decode())
            packages = []
            for package in data.get("package", []):
                if "name" in package:
                    packages.append(
                        PackageInfo(
                            name=package["name"],
                            ecosystem="python",
                            version=package.get("version"),
                        )
                    )
            return packages
        except Exception:
            return []

    @staticmethod
    async def _parse_lockfile_uv(lockfile_path: Path) -> list[PackageInfo]:
        """Parse uv.lock file."""
        try:
            import tomllib
        except ImportError:
            # Python < 3.11
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                return []

        try:
            async with aiofiles.open(lockfile_path, "rb") as f:
                content = await f.read()
                data = tomllib.loads(content.decode())
            packages = []
            for package in data.get("package", []):
                if "name" in package:
                    packages.append(
                        PackageInfo(
                            name=package["name"],
                            ecosystem="python",
                            version=package.get("version"),
                        )
                    )
            return packages
        except Exception:
            return []

    @staticmethod
    async def _parse_lockfile_pipenv(lockfile_path: Path) -> list[PackageInfo]:
        """Parse Pipfile.lock (JSON) file."""
        try:
            async with aiofiles.open(lockfile_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)
            packages = []
            # Pipfile.lock has "default" and "develop" sections
            for section in ("default", "develop"):
                if section in data:
                    for package_name, package_info in data[section].items():
                        version = None
                        if isinstance(package_info, dict):
                            version = package_info.get("version")
                        packages.append(
                            PackageInfo(
                                name=package_name,
                                ecosystem="python",
                                version=version,
                            )
                        )
            return packages
        except Exception:
            return []


RESOLVER = PythonResolver()
