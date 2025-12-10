"""
Python/PyPI package resolver.
"""

import json
from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class PythonResolver(LanguageResolver):
    """Resolver for Python packages (PyPI)."""

    @property
    def ecosystem_name(self) -> str:
        return "python"

    def resolve_github_url(self, package_name: str) -> tuple[str, str] | None:
        """
        Fetches package information from the PyPI JSON API and extracts the GitHub URL.

        Args:
            package_name: The name of the package on PyPI.

        Returns:
            A tuple of (owner, repo_name) if a GitHub URL is found, otherwise None.
        """
        try:
            with httpx.Client(verify=get_verify_ssl()) as client:
                response = client.get(
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

            github_url = None
            if project_urls:  # Ensure project_urls is not None or empty
                for key in url_keys:
                    if (
                        key in project_urls
                        and project_urls[key]
                        and "github.com" in project_urls[key]
                    ):
                        github_url = project_urls[key]
                        break

                if not github_url:
                    # Fallback to searching all urls
                    for url in project_urls.values():
                        if isinstance(url, str) and "github.com" in url:
                            github_url = url
                            break

            if github_url:
                parts = github_url.strip("/").split("/")
                try:
                    gh_index = parts.index("github.com")
                    if len(parts) > gh_index + 2:
                        owner = parts[gh_index + 1]
                        repo = parts[gh_index + 2]
                        return owner, repo.split("#")[0]  # Clean fragment
                except (ValueError, IndexError):
                    return None

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(f"Error fetching PyPI data for {package_name}: {e}")
            return None

        return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
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
            return self._parse_lockfile_poetry(lockfile_path)
        elif filename == "uv.lock":
            return self._parse_lockfile_uv(lockfile_path)
        elif filename == "Pipfile.lock":
            return self._parse_lockfile_pipenv(lockfile_path)
        else:
            raise ValueError(f"Unknown Python lockfile type: {filename}")

    def detect_lockfiles(self, directory: str | Path = ".") -> list[Path]:
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

    def get_manifest_files(self) -> list[str]:
        """Return list of Python manifest file names."""
        return ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
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
            return self._parse_manifest_requirements(manifest_path)
        elif filename == "pyproject.toml":
            return self._parse_manifest_pyproject(manifest_path)
        elif filename == "Pipfile":
            return self._parse_manifest_pipfile(manifest_path)
        else:
            raise ValueError(f"Unknown Python manifest file type: {filename}")

    @staticmethod
    def _parse_manifest_requirements(manifest_path: Path) -> list[PackageInfo]:
        """Parse requirements.txt file."""
        packages = []
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                for line in f:
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
    def _parse_manifest_pyproject(manifest_path: Path) -> list[PackageInfo]:
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
            with open(manifest_path, "rb") as f:
                data = tomllib.load(f)

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
    def _parse_manifest_pipfile(manifest_path: Path) -> list[PackageInfo]:
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
            with open(manifest_path, "rb") as f:
                data = tomllib.load(f)

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
    def _parse_lockfile_poetry(lockfile_path: Path) -> list[PackageInfo]:
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
            with open(lockfile_path, "rb") as f:
                data = tomllib.load(f)
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
    def _parse_lockfile_uv(lockfile_path: Path) -> list[PackageInfo]:
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
            with open(lockfile_path, "rb") as f:
                data = tomllib.load(f)
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
    def _parse_lockfile_pipenv(lockfile_path: Path) -> list[PackageInfo]:
        """Parse Pipfile.lock (JSON) file."""
        try:
            with open(lockfile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
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


# Legacy functions for backward compatibility
def get_github_url_from_pypi(package_name: str) -> tuple[str, str] | None:
    """
    Legacy function for backward compatibility.
    Use PythonResolver.resolve_github_url() instead.
    """
    resolver = PythonResolver()
    return resolver.resolve_github_url(package_name)


def parse_lockfile_poetry(lockfile_path: str | Path) -> list[str]:
    """Legacy function for backward compatibility."""
    resolver = PythonResolver()
    packages = resolver._parse_lockfile_poetry(Path(lockfile_path))
    return [p.name for p in packages]


def parse_lockfile_uv(lockfile_path: str | Path) -> list[str]:
    """Legacy function for backward compatibility."""
    resolver = PythonResolver()
    packages = resolver._parse_lockfile_uv(Path(lockfile_path))
    return [p.name for p in packages]


def parse_lockfile_pipenv(lockfile_path: str | Path) -> list[str]:
    """Legacy function for backward compatibility."""
    resolver = PythonResolver()
    packages = resolver._parse_lockfile_pipenv(Path(lockfile_path))
    return [p.name for p in packages]


def get_packages_from_lockfile(lockfile_path: str | Path) -> list[str]:
    """Legacy function for backward compatibility."""
    resolver = PythonResolver()
    packages = resolver.parse_lockfile(lockfile_path)
    return [p.name for p in packages]


def detect_lockfiles(directory: str | Path = ".") -> list[Path]:
    """Legacy function for backward compatibility."""
    resolver = PythonResolver()
    return resolver.detect_lockfiles(directory)
