"""
JavaScript/TypeScript package resolver (npm ecosystem).
"""

import json
from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class JavaScriptResolver(LanguageResolver):
    """Resolver for JavaScript/TypeScript packages (npm, yarn, pnpm)."""

    @property
    def ecosystem_name(self) -> str:
        return "javascript"

    def resolve_github_url(self, package_name: str) -> tuple[str, str] | None:
        """
        Fetches package information from the npm registry and extracts the GitHub URL.

        Args:
            package_name: The name of the package on npm.

        Returns:
            A tuple of (owner, repo_name) if a GitHub URL is found, otherwise None.
        """
        try:
            with httpx.Client(verify=get_verify_ssl()) as client:
                response = client.get(
                    f"https://registry.npmjs.org/{package_name}",
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()

            # npm registry stores repository info in different formats
            repo_info = data.get("repository", {})

            # Extract URL from repository object
            repo_url = None
            if isinstance(repo_info, dict):
                repo_url = repo_info.get("url", "")
            elif isinstance(repo_info, str):
                repo_url = repo_info

            if not repo_url:
                # Fallback: check other common fields
                homepage = data.get("homepage", "")
                if "github.com" in homepage:
                    repo_url = homepage

            if repo_url:
                # Clean up git URL (remove git+ prefix and .git suffix)
                repo_url = (
                    repo_url.replace("git+", "")
                    .replace("git://", "https://")
                    .replace(".git", "")
                    .strip()
                )

                # Parse GitHub URL
                if "github.com" in repo_url:
                    parts = repo_url.strip("/").split("/")
                    try:
                        gh_index = parts.index("github.com")
                        if len(parts) > gh_index + 2:
                            owner = parts[gh_index + 1]
                            repo = parts[gh_index + 2]
                            return owner, repo.split("#")[0]  # Clean fragment
                    except (ValueError, IndexError):
                        return None

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(f"Error fetching JavaScript data for {package_name}: {e}")
            return None

        return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Auto-detects JavaScript lockfile type and extracts package information.

        Supports: package-lock.json, yarn.lock, pnpm-lock.yaml

        Args:
            lockfile_path: Path to a JavaScript lockfile.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        filename = lockfile_path.name

        if filename == "package-lock.json":
            return self._parse_package_lock(lockfile_path)
        elif filename == "yarn.lock":
            return self._parse_yarn_lock(lockfile_path)
        elif filename == "pnpm-lock.yaml":
            return self._parse_pnpm_lock(lockfile_path)
        else:
            raise ValueError(f"Unknown JavaScript lockfile type: {filename}")

    def detect_lockfiles(self, directory: str | Path = ".") -> list[Path]:
        """
        Detects JavaScript lockfiles in a directory.

        Args:
            directory: Directory to search for lockfiles. Defaults to current directory.

        Returns:
            List of detected lockfile paths that exist.
        """
        directory = Path(directory)
        lockfile_names = ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"]
        detected = []
        for name in lockfile_names:
            lockfile = directory / name
            if lockfile.exists():
                detected.append(lockfile)
        return detected

    def get_manifest_files(self) -> list[str]:
        """Return list of JavaScript manifest file names."""
        return ["package.json"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse a JavaScript manifest file (package.json).

        Args:
            manifest_path: Path to package.json.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name != "package.json":
            raise ValueError(
                f"Unknown JavaScript manifest file type: {manifest_path.name}"
            )

        return self._parse_package_json(manifest_path)

    @staticmethod
    def _parse_package_json(manifest_path: Path) -> list[PackageInfo]:
        """Parse package.json file."""
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            packages = []

            # Collect dependencies from all sections
            for section in (
                "dependencies",
                "devDependencies",
                "optionalDependencies",
                "peerDependencies",
            ):
                deps = data.get(section, {})
                if isinstance(deps, dict):
                    for package_name, version in deps.items():
                        packages.append(
                            PackageInfo(
                                name=package_name,
                                ecosystem="javascript",
                                version=version if isinstance(version, str) else None,
                            )
                        )

            return packages
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Failed to parse package.json: {e}") from e

    @staticmethod
    def _parse_package_lock(lockfile_path: Path) -> list[PackageInfo]:
        """Parse package-lock.json file."""
        try:
            with open(lockfile_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            packages = []
            dependencies = data.get("dependencies", {})

            # package-lock.json v1 and v3 format
            for package_name in dependencies.keys():
                packages.append(
                    PackageInfo(
                        name=package_name,
                        ecosystem="javascript",
                        version=dependencies[package_name].get("version"),
                    )
                )

            # Also check "packages" field (used in v3)
            packages_obj = data.get("packages", {})
            for package_path in packages_obj.keys():
                if package_path and package_path != ".":
                    # Extract package name from path (e.g., "node_modules/lodash" -> "lodash")
                    parts = package_path.split("/")
                    if len(parts) >= 2:
                        package_name = parts[-1]
                        # Avoid duplicates
                        if not any(p.name == package_name for p in packages):
                            packages.append(
                                PackageInfo(
                                    name=package_name,
                                    ecosystem="javascript",
                                    version=packages_obj[package_path].get("version"),
                                )
                            )

            return packages
        except Exception:
            return []

    @staticmethod
    def _parse_yarn_lock(lockfile_path: Path) -> list[PackageInfo]:
        """
        Parse yarn.lock file.

        yarn.lock uses a custom format:
        package_name@version:
          dependencies:
            ...
        """
        try:
            with open(lockfile_path, "r", encoding="utf-8") as f:
                content = f.read()

            packages = set()

            # Simple parser: extract package names before @ symbol
            for line in content.split("\n"):
                line = line.strip()
                # Match pattern like "package-name@^1.0.0:" or "package-name@1.0.0:"
                if line and "@" in line and ":" in line:
                    # Remove quotes if present
                    line = line.strip('"')

                    # Handle scoped packages (@scope/package@version)
                    if line.startswith("@"):
                        # Scoped package
                        parts = line.split("@")
                        if len(parts) >= 3:
                            # Format: @scope@version:
                            package_name = f"@{parts[1]}"
                            packages.add(package_name)
                    else:
                        # Regular package
                        package_name = line.split("@")[0]
                        if package_name and not package_name.startswith("#"):
                            packages.add(package_name)

            return [
                PackageInfo(
                    name=pkg_name,
                    ecosystem="javascript",
                    version=None,  # yarn.lock doesn't easily expose single version
                )
                for pkg_name in sorted(packages)
            ]
        except Exception:
            return []

    @staticmethod
    def _parse_pnpm_lock(lockfile_path: Path) -> list[PackageInfo]:
        """Parse pnpm-lock.yaml file."""
        try:
            import yaml

            with open(lockfile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            packages = set()

            # pnpm-lock.yaml structure: dependencies and optionalDependencies
            for section in ("dependencies", "devDependencies", "optionalDependencies"):
                deps = data.get(section, {})
                if isinstance(deps, dict):
                    for package_name in deps.keys():
                        packages.add(package_name)

            # Also check the "packages" section
            packages_obj = data.get("packages", {})
            if isinstance(packages_obj, dict):
                for package_path in packages_obj.keys():
                    if package_path and package_path != ".":
                        # Extract package name from path
                        parts = package_path.split("/")
                        if len(parts) >= 1:
                            # Remove version info if present
                            package_name = parts[-1].split("_")[0]
                            if package_name:
                                packages.add(package_name)

            return [
                PackageInfo(
                    name=pkg_name,
                    ecosystem="javascript",
                    version=None,
                )
                for pkg_name in sorted(packages)
            ]
        except Exception:
            return []
