"""JavaScript ecosystem external tools for dependency resolution."""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

from oss_sustain_guard.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyInfo,
)
from oss_sustain_guard.external_tools.base import ExternalTool


class PnpmTreeTool(ExternalTool):
    """Use pnpm to resolve JavaScript package dependencies."""

    @property
    def name(self) -> str:
        return "pnpm"

    @property
    def ecosystem(self) -> str:
        return "javascript"

    def is_available(self) -> bool:
        """Check if pnpm is installed."""
        return shutil.which("pnpm") is not None

    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve dependency tree using pnpm.

        Args:
            package: Package name to resolve
            version: Optional specific version (if None, uses latest)

        Returns:
            DependencyGraph with all resolved dependencies

        Raises:
            RuntimeError: If pnpm execution fails
            ValueError: If package is invalid or not found
        """
        temp_dir = Path(tempfile.mkdtemp(prefix="os4g-trace-js-"))

        try:
            # Create minimal package.json
            package_json = {
                "name": "temp-os4g-trace",
                "version": "1.0.0",
                "dependencies": {package: version or "*"},
            }
            package_json_path = temp_dir / "package.json"
            package_json_path.write_text(json.dumps(package_json, indent=2))

            # Use pnpm install with minimal disk usage options:
            # --ignore-scripts: Skip install scripts to save time and disk
            # --no-optional: Skip optional dependencies
            # --prefer-offline: Use cache when possible
            install_process = await asyncio.create_subprocess_exec(
                "pnpm",
                "install",
                "--no-frozen-lockfile",
                "--ignore-scripts",
                "--no-optional",
                "--prefer-offline",
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, install_stderr = await install_process.communicate()

            if install_process.returncode != 0:
                error_msg = install_stderr.decode().strip()
                if "not found" in error_msg.lower() or "404" in error_msg:
                    raise ValueError(
                        f"Package '{package}' not found or no compatible version available.\n"
                        f"Error: {error_msg}"
                    )
                raise RuntimeError(f"Failed to install '{package}': {error_msg}")

            # Run pnpm list to get dependency tree
            list_process = await asyncio.create_subprocess_exec(
                "pnpm",
                "list",
                "--depth",
                "100",
                "--json",
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await list_process.communicate()

            if list_process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise RuntimeError(f"Failed to list dependencies: {error_msg}")

            # Parse pnpm list output
            list_data = json.loads(stdout.decode())[0]  # pnpm returns array
            return self._parse_pnpm_tree(package, list_data)

        finally:
            # Ensure temporary directory is always cleaned up
            # Use ignore_errors=True to handle permission issues gracefully
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _parse_pnpm_tree(self, root_package: str, data: dict) -> DependencyGraph:
        """Parse pnpm list JSON output into DependencyGraph."""
        direct_deps: list[DependencyInfo] = []
        transitive_deps: list[DependencyInfo] = []
        edges: list[DependencyEdge] = []
        seen = set()

        dependencies = data.get("dependencies", {})

        # First pass: collect all dependencies
        for dep_name, dep_info in dependencies.items():
            if dep_name in seen:
                continue

            version = dep_info.get("version", "")
            is_direct = True  # Top-level dependencies are direct
            depth = 0

            dep = DependencyInfo(
                name=dep_name,
                ecosystem="javascript",
                version=version,
                is_direct=is_direct,
                depth=depth,
            )
            direct_deps.append(dep)
            seen.add(dep_name)

            # Add edge from root to dependency
            edges.append(DependencyEdge(source=root_package, target=dep_name))

            # Process nested dependencies recursively
            self._parse_dependencies_recursive(
                dep_name, dep_info, 1, transitive_deps, edges, seen
            )

        return DependencyGraph(
            root_package=root_package,
            ecosystem="javascript",
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
            edges=edges,
        )

    def _parse_dependencies_recursive(
        self,
        parent: str,
        parent_info: dict,
        depth: int,
        transitive_deps: list[DependencyInfo],
        edges: list[DependencyEdge],
        seen: set,
    ) -> None:
        """Recursively parse nested dependencies."""
        nested_deps = parent_info.get("dependencies", {})

        for dep_name, dep_info in nested_deps.items():
            if dep_name not in seen:
                version = dep_info.get("version", "")
                dep = DependencyInfo(
                    name=dep_name,
                    ecosystem="javascript",
                    version=version,
                    is_direct=False,
                    depth=depth,
                )
                transitive_deps.append(dep)
                seen.add(dep_name)

            # Add edge from parent to this dependency
            edges.append(DependencyEdge(source=parent, target=dep_name))

            # Recurse into nested dependencies
            self._parse_dependencies_recursive(
                dep_name, dep_info, depth + 1, transitive_deps, edges, seen
            )


class BunTreeTool(ExternalTool):
    """Use bun to resolve JavaScript package dependencies."""

    @property
    def name(self) -> str:
        return "bun"

    @property
    def ecosystem(self) -> str:
        return "javascript"

    def is_available(self) -> bool:
        """Check if bun is installed."""
        return shutil.which("bun") is not None

    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve dependency tree using bun.

        Note: Bun implementation is similar to pnpm.
        """
        # Similar implementation to pnpm but using bun commands
        temp_dir = Path(tempfile.mkdtemp(prefix="os4g-trace-js-bun-"))

        try:
            # Create minimal package.json
            package_json = {
                "name": "temp-os4g-trace",
                "version": "1.0.0",
                "dependencies": {package: version or "*"},
            }
            package_json_path = temp_dir / "package.json"
            package_json_path.write_text(json.dumps(package_json, indent=2))

            # Run bun install with minimal disk usage options
            # --no-save: Don't update package.json
            # --production: Skip devDependencies
            install_process = await asyncio.create_subprocess_exec(
                "bun",
                "install",
                "--no-save",
                "--production",
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, install_stderr = await install_process.communicate()

            if install_process.returncode != 0:
                error_msg = install_stderr.decode().strip()
                if "not found" in error_msg.lower() or "404" in error_msg:
                    raise ValueError(
                        f"Package '{package}' not found.\nError: {error_msg}"
                    )
                raise RuntimeError(f"Failed to install '{package}': {error_msg}")

            # Parse bun.lockb (binary) is complex, so use package-lock.json if available
            # Or fall back to reading node_modules structure
            lock_path = temp_dir / "package-lock.json"
            if lock_path.exists():
                from oss_sustain_guard.dependency_parsers.javascript.npm import (
                    parse_npm_lockfile,
                )

                return parse_npm_lockfile(lock_path) or DependencyGraph(
                    root_package=package,
                    ecosystem="javascript",
                    direct_dependencies=[],
                    transitive_dependencies=[],
                )

            # Fallback: simple implementation
            raise RuntimeError(
                "Bun lockfile parsing not yet fully implemented. Please use pnpm or npm."
            )

        finally:
            # Ensure temporary directory is always cleaned up
            # Use ignore_errors=True to handle permission issues gracefully
            shutil.rmtree(temp_dir, ignore_errors=True)


class NpmTreeTool(ExternalTool):
    """Use npm to resolve JavaScript package dependencies."""

    @property
    def name(self) -> str:
        return "npm"

    @property
    def ecosystem(self) -> str:
        return "javascript"

    def is_available(self) -> bool:
        """Check if npm is installed."""
        return shutil.which("npm") is not None

    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve dependency tree using npm."""
        temp_dir = Path(tempfile.mkdtemp(prefix="os4g-trace-js-npm-"))

        try:
            # Create minimal package.json
            package_json = {
                "name": "temp-os4g-trace",
                "version": "1.0.0",
                "dependencies": {package: version or "*"},
            }
            package_json_path = temp_dir / "package.json"
            package_json_path.write_text(json.dumps(package_json, indent=2))

            # Run npm install with minimal disk usage options:
            # --omit=dev: Skip devDependencies
            # --ignore-scripts: Skip install scripts to save time and disk
            # --prefer-offline: Use cache when possible
            install_process = await asyncio.create_subprocess_exec(
                "npm",
                "install",
                "--omit=dev",
                "--ignore-scripts",
                "--prefer-offline",
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, install_stderr = await install_process.communicate()

            if install_process.returncode != 0:
                error_msg = install_stderr.decode().strip()
                if "404" in error_msg or "not found" in error_msg.lower():
                    raise ValueError(
                        f"Package '{package}' not found.\nError: {error_msg}"
                    )
                raise RuntimeError(f"Failed to install '{package}': {error_msg}")

            # Parse package-lock.json
            lock_path = temp_dir / "package-lock.json"
            if not lock_path.exists():
                raise RuntimeError(
                    f"npm install succeeded but package-lock.json was not created for '{package}'"
                )

            from oss_sustain_guard.dependency_parsers.javascript.npm import (
                parse_npm_lockfile,
            )

            dep_graph = parse_npm_lockfile(lock_path)
            if dep_graph is None:
                raise RuntimeError(
                    f"Failed to parse generated package-lock.json for '{package}'"
                )

            # Update root package name
            return DependencyGraph(
                root_package=package,
                ecosystem=dep_graph.ecosystem,
                direct_dependencies=dep_graph.direct_dependencies,
                transitive_dependencies=dep_graph.transitive_dependencies,
                edges=dep_graph.edges,
            )

        finally:
            # Ensure temporary directory is always cleaned up
            # Use ignore_errors=True to handle permission issues gracefully
            shutil.rmtree(temp_dir, ignore_errors=True)


def get_javascript_tool(preferred_tool: str | None = None) -> ExternalTool:
    """Get the best available JavaScript dependency resolution tool.

    Args:
        preferred_tool: Optional tool name to prefer (e.g., "npm", "pnpm", "bun").
                       If specified and available, returns that tool.
                       If specified but not available, raises RuntimeError.
                       If None, uses auto-detection.

    Returns:
        ExternalTool instance

    Raises:
        RuntimeError: If preferred_tool is specified but not available
        ValueError: If preferred_tool is not a valid JavaScript tool

    Priority order (when preferred_tool is None):
        1. pnpm (mature and fast)
        2. bun (fastest but newer)
        3. npm (standard fallback)
    """
    # Map of tool names to tool classes
    JAVASCRIPT_TOOLS = {
        "npm": NpmTreeTool,
        "pnpm": PnpmTreeTool,
        "bun": BunTreeTool,
    }

    # If user specified a preferred tool
    if preferred_tool:
        if preferred_tool not in JAVASCRIPT_TOOLS:
            raise ValueError(
                f"Tool '{preferred_tool}' is not available for javascript ecosystem. "
                f"Available tools: {', '.join(JAVASCRIPT_TOOLS.keys())}"
            )

        tool = JAVASCRIPT_TOOLS[preferred_tool]()
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{preferred_tool}' is not installed. "
                f"Please install it to trace javascript packages."
            )
        return tool

    # Auto-detection: Try pnpm first (best balance of speed and maturity)
    pnpm_tool = PnpmTreeTool()
    if pnpm_tool.is_available():
        return pnpm_tool

    # Try bun second (fastest but newer)
    bun_tool = BunTreeTool()
    if bun_tool.is_available():
        return bun_tool

    # Fall back to npm (always available)
    npm_tool = NpmTreeTool()
    if npm_tool.is_available():
        return npm_tool

    # If nothing available, return npm (which will error with helpful message)
    return npm_tool
