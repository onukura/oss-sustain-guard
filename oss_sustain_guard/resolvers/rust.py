"""
Rust package resolver (crates.io).
"""

from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class RustResolver(LanguageResolver):
    """Resolver for Rust packages (crates.io)."""

    @property
    def ecosystem_name(self) -> str:
        return "rust"

    def resolve_github_url(self, package_name: str) -> tuple[str, str] | None:
        """
        Fetches package information from crates.io and extracts the GitHub URL.

        Args:
            package_name: The name of the crate on crates.io.

        Returns:
            A tuple of (owner, repo_name) if a GitHub URL is found, otherwise None.
        """
        try:
            with httpx.Client(verify=get_verify_ssl()) as client:
                # Query crates.io API
                response = client.get(
                    f"https://crates.io/api/v1/crates/{package_name}",
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()

            crate_info = data.get("crate", {})
            repo_url = crate_info.get("repository")

            if repo_url and "github.com" in repo_url:
                # Clean up URL
                repo_url = repo_url.rstrip("/").replace(".git", "")

                # Parse GitHub URL
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
            print(f"Error fetching Rust data for {package_name}: {e}")
            return None

        return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse Cargo.lock file and extract package information.

        Cargo.lock is in TOML format with [[package]] entries.

        Args:
            lockfile_path: Path to Cargo.lock file.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        if lockfile_path.name != "Cargo.lock":
            raise ValueError(f"Unknown Rust lockfile type: {lockfile_path.name}")

        return self._parse_cargo_lock(lockfile_path)

    def detect_lockfiles(self, directory: str | Path = ".") -> list[Path]:
        """
        Detect Rust lockfiles in a directory.

        Args:
            directory: Directory to search for lockfiles. Defaults to current directory.

        Returns:
            List of detected lockfile paths that exist.
        """
        directory = Path(directory)
        detected = []
        cargo_lock = directory / "Cargo.lock"
        if cargo_lock.exists():
            detected.append(cargo_lock)
        return detected

    def get_manifest_files(self) -> list[str]:
        """Return list of Rust manifest file names."""
        return ["Cargo.toml"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse a Rust manifest file (Cargo.toml).

        Args:
            manifest_path: Path to Cargo.toml.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name != "Cargo.toml":
            raise ValueError(f"Unknown Rust manifest file type: {manifest_path.name}")

        return self._parse_cargo_toml(manifest_path)

    @staticmethod
    def _parse_cargo_toml(manifest_path: Path) -> list[PackageInfo]:
        """Parse Cargo.toml file."""
        try:
            import tomllib
        except ImportError:
            # Python < 3.11
            try:
                import tomli as tomllib  # type: ignore
            except ImportError as e:
                raise ValueError(
                    "tomllib or tomli is required to parse Cargo.toml"
                ) from e

        try:
            with open(manifest_path, "rb") as f:
                data = tomllib.load(f)

            packages = []

            # Collect dependencies from all sections
            for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                deps = data.get(section, {})
                if isinstance(deps, dict):
                    for package_name, dep_spec in deps.items():
                        version = None
                        if isinstance(dep_spec, dict):
                            version = dep_spec.get("version")
                        elif isinstance(dep_spec, str):
                            version = dep_spec

                        packages.append(
                            PackageInfo(
                                name=package_name,
                                ecosystem="rust",
                                version=version,
                            )
                        )

            return packages
        except Exception as e:
            raise ValueError(f"Failed to parse Cargo.toml: {e}") from e

    @staticmethod
    def _parse_cargo_lock(lockfile_path: Path) -> list[PackageInfo]:
        """Parse Cargo.lock file."""
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
                            ecosystem="rust",
                            version=package.get("version"),
                        )
                    )

            return packages
        except Exception:
            return []
