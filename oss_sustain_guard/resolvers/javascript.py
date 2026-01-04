"""
JavaScript/TypeScript package resolver (npm ecosystem).
"""

import json
import sys
from pathlib import Path

import aiofiles
import httpx

from oss_sustain_guard.http_client import _get_async_http_client
from oss_sustain_guard.repository import RepositoryReference, parse_repository_url
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class JavaScriptResolver(LanguageResolver):
    """Resolver for JavaScript/TypeScript packages (npm, yarn, pnpm)."""

    @property
    def ecosystem_name(self) -> str:
        return "javascript"

    async def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """
        Fetches package information from the npm registry and extracts repository URL.

        Args:
            package_name: The name of the package on npm.

        Returns:
            RepositoryReference if a supported repository URL is found, otherwise None.
        """
        try:
            client = await _get_async_http_client()
            response = await client.get(
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
                if isinstance(homepage, str):
                    repo_url = homepage

            if repo_url:
                normalized = repo_url.strip()
                if normalized.startswith("github:"):
                    normalized = f"https://github.com/{normalized.split(':', 1)[1]}"
                elif normalized.startswith("gitlab:"):
                    normalized = f"https://gitlab.com/{normalized.split(':', 1)[1]}"

                # Clean up git URL (remove git+ prefix and .git suffix)
                normalized = (
                    normalized.replace("git+", "")
                    .replace("git://", "https://")
                    .rstrip("/")
                )

                repo = parse_repository_url(normalized)
                if repo:
                    return repo

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(
                f"Note: Unable to fetch JavaScript data for {package_name}: {e}",
                file=sys.stderr,
            )
            return None

        return None

    async def parse_lockfile(self, lockfile_path: str | Path) -> list[PackageInfo]:
        """
        Auto-detects JavaScript lockfile type and extracts package information.

        Supports: package-lock.json, yarn.lock, pnpm-lock.yaml, bun.lock, bun.lockb, deno.lock

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
            return await self._parse_package_lock(lockfile_path)
        elif filename == "yarn.lock":
            return await self._parse_yarn_lock(lockfile_path)
        elif filename == "pnpm-lock.yaml":
            return await self._parse_pnpm_lock(lockfile_path)
        elif filename == "bun.lock" or filename == "bun.lockb":
            return await self._parse_bun_lock(lockfile_path)
        elif filename == "deno.lock":
            return await self._parse_deno_lock(lockfile_path)
        else:
            raise ValueError(f"Unknown JavaScript lockfile type: {filename}")

    async def detect_lockfiles(self, directory: str | Path = ".") -> list[Path]:
        """
        Detects JavaScript lockfiles in a directory.

        Args:
            directory: Directory to search for lockfiles. Defaults to current directory.

        Returns:
            List of detected lockfile paths that exist.
        """
        directory = Path(directory)
        lockfile_names = [
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "bun.lock",
            "bun.lockb",
            "deno.lock",
        ]
        detected = []
        for name in lockfile_names:
            lockfile = directory / name
            if lockfile.exists():
                detected.append(lockfile)
        return detected

    async def get_manifest_files(self) -> list[str]:
        """Return list of JavaScript manifest file names."""
        return ["package.json", "deno.json"]

    async def parse_manifest(self, manifest_path: str | Path) -> list[PackageInfo]:
        """
        Parse a JavaScript manifest file (package.json or deno.json).

        Args:
            manifest_path: Path to package.json or deno.json.

        Returns:
            List of PackageInfo objects.

        Raises:
            FileNotFoundError: If the manifest file doesn't exist.
            ValueError: If the manifest file format is invalid.
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        if manifest_path.name == "package.json":
            return await self._parse_package_json(manifest_path)
        elif manifest_path.name == "deno.json":
            return await self._parse_deno_json(manifest_path)
        else:
            raise ValueError(
                f"Unknown JavaScript manifest file type: {manifest_path.name}"
            )

    @staticmethod
    async def _parse_package_json(manifest_path: Path) -> list[PackageInfo]:
        """Parse package.json file."""
        try:
            async with aiofiles.open(manifest_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

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
    async def _parse_package_lock(lockfile_path: Path) -> list[PackageInfo]:
        """Parse package-lock.json file."""
        try:
            async with aiofiles.open(lockfile_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

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
                    package_name = _extract_npm_package_name(package_path)
                    if package_name and not any(
                        p.name == package_name for p in packages
                    ):
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
    async def _parse_yarn_lock(lockfile_path: Path) -> list[PackageInfo]:
        """
        Parse yarn.lock file.

        yarn.lock uses a custom format:
        package_name@version:
          dependencies:
            ...
        """
        try:
            async with aiofiles.open(lockfile_path, "r", encoding="utf-8") as f:
                content = await f.read()

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
    async def _parse_pnpm_lock(lockfile_path: Path) -> list[PackageInfo]:
        """Parse pnpm-lock.yaml file."""
        try:
            import yaml

            async with aiofiles.open(lockfile_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = yaml.safe_load(content)

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
                        # pnpm uses format: "package@version" or "/package@version" or "/@scope/package@version"
                        package_path_cleaned = package_path.lstrip("/")

                        # Handle scoped packages (@scope/package@version)
                        if package_path_cleaned.startswith("@"):
                            # Split on the last @ to separate name from version
                            last_at_idx = package_path_cleaned.rfind("@")
                            if last_at_idx > 0:
                                package_name = package_path_cleaned[:last_at_idx]
                                if package_name:
                                    packages.add(package_name)
                        else:
                            # Regular package (package@version)
                            # Split on @ to remove version
                            parts = package_path_cleaned.split("@")
                            if len(parts) > 0 and parts[0]:
                                package_name = parts[0]
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

    @staticmethod
    async def _parse_deno_lock(lockfile_path: Path) -> list[PackageInfo]:
        """Parse deno.lock file (Deno lock format)."""
        try:
            async with aiofiles.open(lockfile_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            packages = set()

            # Deno v5 format: check 'specifiers' section for npm packages
            specifiers = data.get("specifiers", {})
            if specifiers:
                for spec_key in specifiers.keys():
                    # spec_key format: "npm:package@version" or "npm:@scope/package@version"
                    if spec_key.startswith("npm:"):
                        # Remove "npm:" prefix
                        npm_spec = spec_key[4:]
                        # Extract package name (before @version)
                        # Handle scoped packages (@scope/package@version)
                        if npm_spec.startswith("@"):
                            # Scoped package: @scope/package@version
                            # Find the last @ to separate name from version
                            last_at_idx = npm_spec.rfind("@")
                            if last_at_idx > 0:
                                pkg_name = npm_spec[:last_at_idx]
                                packages.add(pkg_name)
                        else:
                            # Regular package: package@version
                            at_idx = npm_spec.find("@")
                            if at_idx > 0:
                                package_name = npm_spec[:at_idx]
                            else:
                                package_name = npm_spec
                            if package_name:
                                packages.add(package_name)

            # Legacy format: check 'remote' section (older Deno versions)
            remote = data.get("remote", {})
            if remote:
                for url in remote.keys():
                    # Try to extract package name from URL
                    if "registry.npmjs.org" in url:
                        parts = url.split("/")
                        for part in parts:
                            if part and not part.startswith("http") and "@" not in part:
                                packages.add(part)
                                break

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

    @staticmethod
    async def _parse_deno_json(manifest_path: Path) -> list[PackageInfo]:
        """Parse deno.json file (Deno manifest)."""
        try:
            async with aiofiles.open(manifest_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            packages = []

            # deno.json can have imports section with npm dependencies
            imports = data.get("imports", {})
            if isinstance(imports, dict):
                for _import_key, import_value in imports.items():
                    # Extract package name from npm: specifiers
                    if isinstance(import_value, str) and import_value.startswith(
                        "npm:"
                    ):
                        # Format: npm:package@version or npm:@scope/package@version
                        npm_spec = import_value[4:]  # Remove "npm:" prefix
                        # Extract package name (before @version)
                        if npm_spec.startswith("@"):
                            # Scoped package: @scope/package@version
                            # Find the last @ to separate name from version
                            last_at_idx = npm_spec.rfind("@")
                            if last_at_idx > 0:
                                pkg_name = npm_spec[:last_at_idx]
                                version = npm_spec[last_at_idx + 1 :]
                                packages.append(
                                    PackageInfo(
                                        name=pkg_name,
                                        ecosystem="javascript",
                                        version=version if version else None,
                                    )
                                )
                        else:
                            # Regular package: package@version
                            parts = npm_spec.split("@", 1)  # Split only on first @
                            if parts[0]:
                                version = parts[1] if len(parts) > 1 else None
                                packages.append(
                                    PackageInfo(
                                        name=parts[0],
                                        ecosystem="javascript",
                                        version=version if version else None,
                                    )
                                )

            return packages
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Failed to parse deno.json: {e}") from e

    @staticmethod
    async def _parse_bun_lock(lockfile_path: Path) -> list[PackageInfo]:
        """Parse bun.lock (JSON format) or bun.lockb (binary format) file.

        bun.lock is a JSON file with workspaces, dependencies, and packages sections.
        bun.lockb is a binary format with similar structure.
        """
        try:
            packages = set()

            # Try to parse as JSON first (bun.lock)
            try:
                async with aiofiles.open(lockfile_path, "r", encoding="utf-8") as f:
                    content = await f.read()

                    # Remove trailing commas before closing braces/brackets (JSONC compatibility)
                    import re

                    content = re.sub(r",(\s*[}\]])", r"\1", content)

                    data = json.loads(content)

                # Extract from packages section (all installed packages)
                packages_section = data.get("packages", {})
                if isinstance(packages_section, dict):
                    for pkg_name, pkg_info in packages_section.items():
                        if pkg_name:
                            # Handle array format: "pkg": ["pkg@version", "", {...}, "sha512-..."]
                            if isinstance(pkg_info, list) and len(pkg_info) > 0:
                                # Extract package name from first element
                                full_identifier = pkg_info[0]
                                if "@" in full_identifier:
                                    # Handle scoped packages like "@babel/core@7.28.5"
                                    parts = full_identifier.rsplit("@", 1)
                                    name = parts[0] if len(parts) > 0 else pkg_name
                                else:
                                    name = full_identifier
                                packages.add(name)
                            # Handle dict format (fallback)
                            elif isinstance(pkg_info, dict):
                                name = pkg_info.get("name", pkg_name)
                                packages.add(name)
                            else:
                                packages.add(pkg_name)

                # Also extract from workspaces section (direct dependencies)
                # This handles cases where packages section is empty
                workspaces = data.get("workspaces", {})
                if isinstance(workspaces, dict):
                    for _workspace_name, workspace_data in workspaces.items():
                        if isinstance(workspace_data, dict):
                            # Get dependencies and devDependencies from workspaces
                            for section in ("dependencies", "devDependencies"):
                                deps = workspace_data.get(section, {})
                                if isinstance(deps, dict):
                                    for package_name in deps.keys():
                                        if package_name:
                                            packages.add(package_name)

            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, try binary format (bun.lockb)
                with open(lockfile_path, "rb") as f:
                    content = f.read()

                # Decode as UTF-8 where possible, ignoring errors
                text_content = content.decode("utf-8", errors="ignore")

                # Look for npm: patterns and extract package names
                import re

                # Match npm:package@version patterns
                npm_patterns = re.finditer(
                    r"npm:([a-z0-9@/_-]+?)@", text_content, re.IGNORECASE
                )
                for match in npm_patterns:
                    package_name = match.group(1)
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


def _extract_npm_package_name(package_path: str) -> str | None:
    """Extract an npm package name from a package-lock path."""
    parts = package_path.split("/")
    node_modules_indices = [
        idx for idx, part in enumerate(parts) if part == "node_modules"
    ]
    if not node_modules_indices:
        return None

    last_index = node_modules_indices[-1]
    name_parts = parts[last_index + 1 :]
    if not name_parts:
        return None

    if name_parts[0].startswith("@") and len(name_parts) >= 2:
        return "/".join(name_parts[:2])
    return name_parts[0]


RESOLVER = JavaScriptResolver()
