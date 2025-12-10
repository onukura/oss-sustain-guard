"""
Ruby package resolver (RubyGems).
"""

from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class RubyResolver(LanguageResolver):
    """Resolver for Ruby gems."""

    @property
    def ecosystem_name(self) -> str:
        return "ruby"

    def resolve_github_url(self, package_name: str) -> tuple[str, str] | None:
        """
        Resolve Ruby gem to GitHub repository.

        Queries the RubyGems API to get gem metadata and extracts GitHub URL.

        Args:
            package_name: The gem name (e.g., rails, devise).

        Returns:
            A tuple of (owner, repo_name) if a GitHub URL is found, otherwise None.
        """
        try:
            with httpx.Client(verify=get_verify_ssl()) as client:
                # Query RubyGems API
                response = client.get(
                    f"https://rubygems.org/api/v1/gems/{package_name}.json",
                    timeout=10,
                    follow_redirects=True,
                )
                response.raise_for_status()
                data = response.json()

                # Check multiple URL fields
                urls_to_check = [
                    data.get("source_code_uri"),
                    data.get("homepage_uri"),
                    data.get("project_uri"),
                ]

                for url in urls_to_check:
                    if url and "github.com" in url:
                        # Parse GitHub URL
                        # Format: https://github.com/owner/repo[/tree/...]
                        # Clean up query strings and fragments
                        url_clean = url.split("?")[0].split("#")[0].rstrip("/")
                        parts = url_clean.split("/")

                        # Find github.com in path
                        try:
                            github_idx = parts.index("github.com")
                            if len(parts) > github_idx + 2:
                                owner = parts[github_idx + 1]
                                repo = parts[github_idx + 2]
                                # Clean up .git suffix if present
                                if repo.endswith(".git"):
                                    repo = repo[:-4]
                                return owner, repo
                        except (ValueError, IndexError):
                            continue

                return None

        except Exception as e:
            print(f"Error fetching RubyGems data for {package_name}: {e}")
            return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse Gemfile.lock and extract gem information.

        Args:
            lockfile_path: Path to Gemfile.lock.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
            ValueError: If the lockfile format is invalid.
        """
        lockfile = Path(lockfile_path)
        if not lockfile.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        packages = []

        try:
            with open(lockfile, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse Gemfile.lock format
            # Format:
            # GEM
            #   remote: https://rubygems.org/
            #   specs:
            #     gem-name (version)
            #       dependency1 (>= version)
            #       dependency2

            in_specs = False
            for line in content.split("\n"):
                line_stripped = line.strip()

                if line_stripped == "specs:":
                    in_specs = True
                    continue

                # Check if we left the specs section
                if in_specs and line and not line.startswith(" "):
                    in_specs = False

                # Parse gem lines (indented with exactly 4 spaces)
                # Skip dependencies (indented with 6+ spaces)
                if (
                    in_specs
                    and line.startswith("    ")
                    and not line.startswith("      ")
                    and "(" in line
                ):
                    # Format: "    gem-name (version)"
                    parts = line.strip().split(" (")
                    if len(parts) == 2:
                        name = parts[0].strip()
                        version = parts[1].rstrip(")").strip()

                        packages.append(
                            PackageInfo(
                                name=name,
                                ecosystem="ruby",
                                version=version,
                                registry_url=f"https://rubygems.org/gems/{name}",
                            )
                        )

        except Exception as e:
            raise ValueError(f"Failed to parse Gemfile.lock: {e}") from e

        return packages

    def detect_lockfiles(self, directory: str) -> list[Path]:
        """
        Detect Ruby lockfiles in the directory.

        Args:
            directory: Directory to search for lockfiles.

        Returns:
            List of Path objects for found lockfiles.
        """
        dir_path = Path(directory)
        lockfiles = []

        gemfile_lock = dir_path / "Gemfile.lock"
        if gemfile_lock.exists():
            lockfiles.append(gemfile_lock)

        return lockfiles

    def get_manifest_files(self) -> list[str]:
        """
        Get Ruby manifest file names.

        Returns:
            List of manifest file names.
        """
        return ["Gemfile", "Gemfile.lock"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse a Ruby manifest file (Gemfile).

        Args:
            manifest_path: Path to Gemfile.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name != "Gemfile":
            raise ValueError(f"Unknown Ruby manifest file type: {manifest_path.name}")

        return self._parse_gemfile(manifest_path)

    @staticmethod
    def _parse_gemfile(manifest_path: Path) -> list[PackageInfo]:
        """Parse Gemfile file."""
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()

            packages = []

            # Gemfile format:
            # gem 'rails', '~> 7.0.0'
            # gem 'devise'
            # group :development do
            #   gem 'byebug'
            # end

            for line in content.split("\n"):
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Match gem declarations
                if line.startswith("gem "):
                    # Remove "gem " prefix
                    gem_spec = line[4:].strip()

                    # Parse gem name and version
                    # Format: 'name' or "name" or 'name', 'version'
                    import re

                    # Match patterns like 'name', "name", or 'name', '~> 1.0'
                    pattern = r"['\"]([^'\"]+)['\"]"
                    matches = re.findall(pattern, gem_spec)

                    if matches:
                        gem_name = matches[0]
                        version = matches[1] if len(matches) > 1 else None

                        packages.append(
                            PackageInfo(
                                name=gem_name,
                                ecosystem="ruby",
                                version=version,
                            )
                        )

            return packages
        except (IOError, ValueError) as e:
            raise ValueError(f"Failed to parse Gemfile: {e}") from e
