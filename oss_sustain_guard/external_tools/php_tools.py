"""PHP ecosystem external tools for dependency resolution."""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

from oss_sustain_guard.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyInfo,
)
from oss_sustain_guard.external_tools.base import ExternalTool


class ComposerTool(ExternalTool):
    """Use composer to resolve PHP package dependencies."""

    @property
    def name(self) -> str:
        return "composer"

    @property
    def ecosystem(self) -> str:
        return "php"

    def is_available(self) -> bool:
        """Check if composer is installed."""
        return shutil.which("composer") is not None

    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve dependency tree using composer.

        Creates a temporary PHP project, uses composer require to fetch the specified package,
        parses composer.lock to extract dependency information.

        Note: composer require is efficient as it only fetches metadata and creates
        a lock file without installing packages into vendor directory.

        Args:
            package: Package name to resolve (e.g., "laravel/framework" or "symfony/console")
            version: Optional specific version (if None, uses latest)

        Returns:
            DependencyGraph with all resolved dependencies

        Raises:
            RuntimeError: If composer execution fails
            ValueError: If package is invalid or not found
        """
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="os4g-trace-php-"))

        try:
            # Create minimal composer.json file
            composer_json_content = """{
    "name": "temp-os4g-trace/project",
    "description": "Temporary project for dependency tracing",
    "require": {}
}
"""
            composer_json_path = temp_dir / "composer.json"
            composer_json_path.write_text(composer_json_content)

            # Use composer require to fetch the package and resolve dependencies
            # composer require only updates composer.lock without installing
            package_spec = f"{package}:{version}" if version else package
            process = await asyncio.create_subprocess_exec(
                "composer",
                "require",
                package_spec,
                "--no-install",  # Don't install packages to vendor directory
                "--no-update",  # Let composer figure out dependencies
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **dict(os.environ),
                    "COMPOSER_DISCARD_CHANGES": "true",
                },
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                # Check for common errors
                if (
                    "could not find package" in error_msg.lower()
                    or "package not found" in error_msg.lower()
                ):
                    raise ValueError(
                        f"Package '{package}' not found in Packagist registry.\n"
                        f"Error: {error_msg}"
                    )
                raise RuntimeError(
                    f"Failed to resolve dependencies for '{package}': {error_msg}"
                )

            # Parse composer.json to get dependencies
            with open(composer_json_path) as f:
                composer_json = json.load(f)

            # Parse composer.lock if it exists for version information
            composer_lock_path = temp_dir / "composer.lock"
            if not composer_lock_path.exists():
                # If no lock file, use what we have from composer.json
                return self._parse_composer_json(package, composer_json)

            with open(composer_lock_path) as f:
                composer_lock = json.load(f)

            return self._parse_composer_lock(package, composer_json, composer_lock)

        finally:
            # Ensure temporary directory is always cleaned up
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _parse_composer_json(
        self, root_package: str, composer_json: dict
    ) -> DependencyGraph:
        """Parse composer.json to extract dependency information.

        Args:
            root_package: The root package name we're tracing
            composer_json: The parsed composer.json content

        Returns:
            DependencyGraph with parsed dependencies
        """
        direct_deps: list[DependencyInfo] = []
        edges: list[DependencyEdge] = []

        # Get direct dependencies from require section
        requires = composer_json.get("require", {})

        for package_name, version_spec in requires.items():
            # Skip PHP version requirements
            if package_name == "php":
                dep = DependencyInfo(
                    name=package_name,
                    ecosystem="php",
                    version=version_spec,
                    is_direct=False,
                    depth=0,
                )
                direct_deps.append(dep)
                edges.append(DependencyEdge(source=root_package, target=package_name))
                continue

            # Extract actual version if available
            version = version_spec if version_spec and version_spec != "*" else "latest"
            dep = DependencyInfo(
                name=package_name,
                ecosystem="php",
                version=version,
                is_direct=True,
                depth=0,
            )
            direct_deps.append(dep)
            edges.append(DependencyEdge(source=root_package, target=package_name))

        return DependencyGraph(
            root_package=root_package,
            ecosystem="php",
            direct_dependencies=direct_deps,
            transitive_dependencies=[],
            edges=edges,
        )

    def _parse_composer_lock(
        self, root_package: str, composer_json: dict, composer_lock: dict
    ) -> DependencyGraph:
        """Parse composer.lock to extract dependency information with versions.

        Args:
            root_package: The root package name we're tracing
            composer_json: The parsed composer.json content
            composer_lock: The parsed composer.lock content

        Returns:
            DependencyGraph with parsed dependencies
        """
        direct_deps: list[DependencyInfo] = []
        transitive_deps: list[DependencyInfo] = []
        edges: list[DependencyEdge] = []
        seen = set()

        # Get direct requirements from composer.json
        direct_requires = set(composer_json.get("require", {}).keys())

        # Parse all packages from composer.lock
        packages = composer_lock.get("packages", [])
        packages_by_name = {pkg["name"]: pkg for pkg in packages}

        for package_data in packages:
            package_name = package_data["name"]
            version = package_data.get("version", "unknown")

            # Skip if already processed
            if package_name in seen:
                continue
            seen.add(package_name)

            # Determine if this is a direct dependency
            is_direct = package_name in direct_requires

            dep = DependencyInfo(
                name=package_name,
                ecosystem="php",
                version=version,
                is_direct=is_direct,
                depth=0 if is_direct else 1,
            )

            if is_direct:
                direct_deps.append(dep)
            else:
                transitive_deps.append(dep)

            # Add edge from root to this package
            edges.append(DependencyEdge(source=root_package, target=package_name))

            # Add edges from direct dependencies to their dependencies
            if is_direct:
                requires = package_data.get("require", {})
                for dep_name in requires.keys():
                    if dep_name != "php" and dep_name in packages_by_name:
                        edges.append(
                            DependencyEdge(source=package_name, target=dep_name)
                        )

        # Add PHP version as a special dependency if present
        if "php" in direct_requires:
            php_version = composer_json["require"].get("php", "*")
            php_dep = DependencyInfo(
                name="php",
                ecosystem="php",
                version=php_version,
                is_direct=False,
                depth=0,
            )
            direct_deps.append(php_dep)
            edges.append(DependencyEdge(source=root_package, target="php"))

        return DependencyGraph(
            root_package=root_package,
            ecosystem="php",
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
            edges=edges,
        )


def get_php_tool(preferred_tool: str | None = None) -> ExternalTool:
    """Get the best available PHP dependency resolution tool.

    Args:
        preferred_tool: Optional tool name to prefer (e.g., "composer").
                       If specified and available, returns that tool.
                       If specified but not available, raises RuntimeError.
                       If None, uses auto-detection.

    Returns:
        ExternalTool instance

    Raises:
        RuntimeError: If preferred_tool is specified but not available
        ValueError: If preferred_tool is not a valid PHP tool

    Priority order (when preferred_tool is None):
        1. composer (standard PHP package manager)
    """
    # Map of tool names to tool classes
    PHP_TOOLS = {
        "composer": ComposerTool,
    }

    # If user specified a preferred tool
    if preferred_tool:
        if preferred_tool not in PHP_TOOLS:
            raise ValueError(
                f"Tool '{preferred_tool}' is not available for php ecosystem. "
                f"Available tools: {', '.join(PHP_TOOLS.keys())}"
            )

        tool = PHP_TOOLS[preferred_tool]()
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{preferred_tool}' is not installed. "
                f"Please install it to trace php packages."
            )
        return tool

    # Auto-detection: Try composer (standard tool)
    composer_tool = ComposerTool()
    if composer_tool.is_available():
        return composer_tool

    # If composer not available, return it anyway (will error with helpful message)
    return composer_tool
