"""
Go package resolver (Go modules).
"""

from pathlib import Path

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.repository import RepositoryReference, parse_repository_url
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class GoResolver(LanguageResolver):
    """Resolver for Go modules."""

    @property
    def ecosystem_name(self) -> str:
        return "go"

    def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """
        Resolve Go module to repository URL.

        Go modules often use GitHub paths directly (e.g., github.com/user/repo).
        For other paths, query pkg.go.dev API. If package_name is a short name
        (e.g., "gorm"), attempt to search pkg.go.dev for the canonical module path.

        Args:
            package_name: The Go module path (e.g., github.com/golang/go or golang.org/x/net)
                         or a short package name (e.g., "gorm").

        Returns:
            RepositoryReference if a supported repository URL is found, otherwise None.
        """
        # Check if it's already a repository path
        if package_name.startswith(("github.com/", "gitlab.com/")):
            repo = parse_repository_url(package_name)
            if repo:
                return repo

        # For non-GitHub paths or short names, try to query pkg.go.dev
        try:
            with httpx.Client(verify=get_verify_ssl()) as client:
                # First, try to search for the package if it's a short name
                if "/" not in package_name:
                    search_response = client.get(
                        f"https://pkg.go.dev/search?q={package_name}&m=package",
                        timeout=10,
                        follow_redirects=True,
                    )
                    if search_response.status_code == 200:
                        import re

                        # Look for the first search result with data-test-id="snippet-title"
                        # Pattern: <a href="/module/path" ... data-test-id="snippet-title">
                        pattern = (
                            r'<a href="/([^"?]+)"[^>]*data-test-id="snippet-title"'
                        )
                        matches = re.findall(pattern, search_response.text)
                        if matches:
                            # Use the first match as the canonical path
                            package_name = matches[0]

                # Query pkg.go.dev for package details
                response = client.get(
                    f"https://pkg.go.dev/{package_name}?tab=overview",
                    timeout=10,
                    follow_redirects=True,
                )
                response.raise_for_status()

                # Look for repository link in the UnitMeta-repo section
                if "github.com" in response.text or "gitlab.com" in response.text:
                    import re

                    # First try to find the repository link in UnitMeta-repo section
                    # This is more reliable than searching the entire page
                    pattern = r'class="UnitMeta-repo"[^>]*>.*?href="(https://[^"]+)"'
                    matches = re.findall(pattern, response.text, re.DOTALL)
                    for match in matches:
                        repo = parse_repository_url(match)
                        if repo:
                            return repo

                    # Fallback: search for any repository URL
                    pattern = r'https://(?:github|gitlab)\.com/[^/\s"<>]+/[^/\s"<>]+'
                    matches = re.findall(pattern, response.text)
                    for match in matches:
                        # Filter out common false positives (golang/go is the Go logo link)
                        if "github.com/golang/go" in match:
                            continue
                        repo = parse_repository_url(match)
                        if repo:
                            return repo

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(f"Error fetching Go data for {package_name}: {e}")
            pass

        return None

    def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Parse go.sum file and extract module information.

        go.sum format: Each line is "{module} {version} {hash}"

        Args:
            lockfile_path: Path to go.sum file.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the lockfile doesn't exist.
        """
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

        if lockfile_path.name != "go.sum":
            raise ValueError(f"Unknown Go lockfile type: {lockfile_path.name}")

        return self._parse_go_sum(lockfile_path)

    def detect_lockfiles(self, directory: str | Path = ".") -> list[Path]:
        """
        Detect Go lockfiles in a directory.

        Args:
            directory: Directory to search for lockfiles. Defaults to current directory.

        Returns:
            List of detected lockfile paths that exist.
        """
        directory = Path(directory)
        detected = []
        go_sum = directory / "go.sum"
        if go_sum.exists():
            detected.append(go_sum)
        return detected

    def get_manifest_files(self) -> list[str]:
        """Return list of Go manifest file names."""
        return ["go.mod"]

    def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse a Go manifest file (go.mod).

        Args:
            manifest_path: Path to go.mod.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name != "go.mod":
            raise ValueError(f"Unknown Go manifest file type: {manifest_path.name}")

        return self._parse_go_mod(manifest_path)

    @staticmethod
    def _parse_go_mod(manifest_path: Path) -> list[PackageInfo]:
        """Parse go.mod file."""
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()

            packages = []
            in_require = False

            # go.mod format:
            # module github.com/example/myapp
            # go 1.21
            # require (
            #     github.com/user/repo v1.0.0
            #     github.com/user/repo2 v2.0.0
            # )

            for line in content.split("\n"):
                line = line.strip()

                if line == "require (":
                    in_require = True
                    continue

                if line == ")":
                    in_require = False
                    continue

                # Parse require line (e.g., "github.com/user/repo v1.0.0")
                if in_require and line and not line.startswith("//"):
                    parts = line.split()
                    if len(parts) >= 2:
                        module_path = parts[0]
                        version = parts[1]
                        packages.append(
                            PackageInfo(
                                name=module_path,
                                ecosystem="go",
                                version=version,
                            )
                        )
                # Also handle single-line requires
                elif line.startswith("require ") and "(" not in line:
                    parts = line.replace("require ", "").split()
                    if len(parts) >= 2:
                        module_path = parts[0]
                        version = parts[1]
                        packages.append(
                            PackageInfo(
                                name=module_path,
                                ecosystem="go",
                                version=version,
                            )
                        )

            return packages
        except (IOError, ValueError) as e:
            raise ValueError(f"Failed to parse go.mod: {e}") from e

    @staticmethod
    def _parse_go_sum(lockfile_path: Path) -> list[PackageInfo]:
        """Parse go.sum file."""
        try:
            with open(lockfile_path, "r", encoding="utf-8") as f:
                content = f.read()

            packages = set()

            # go.sum format: module version hash
            # Example: github.com/golang/go v1.21.0 h1:...
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    # Split by whitespace
                    parts = line.split()
                    if len(parts) >= 2:
                        # The first part is the module path
                        module_path = parts[0]
                        # We only care about unique module paths
                        packages.add(module_path)

            return [
                PackageInfo(
                    name=module_path,
                    ecosystem="go",
                    version=None,
                )
                for module_path in sorted(packages)
            ]
        except Exception:
            return []
