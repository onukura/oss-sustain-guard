"""Go ecosystem external tools for dependency resolution."""

import asyncio
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


class GoModTool(ExternalTool):
    """Use go mod to resolve Go package dependencies."""

    @property
    def name(self) -> str:
        return "go"

    @property
    def ecosystem(self) -> str:
        return "go"

    def is_available(self) -> bool:
        """Check if go is installed."""
        return shutil.which("go") is not None

    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve dependency tree using go mod graph.

        Creates a temporary Go module, adds the specified package dependency,
        runs go mod graph to get dependency information without downloading packages.

        Note: go mod graph only fetches metadata without downloading packages,
        making it very efficient for dependency resolution.

        Args:
            package: Package name to resolve (module path, e.g., "github.com/user/repo")
            version: Optional specific version (if None, uses latest)

        Returns:
            DependencyGraph with all resolved dependencies

        Raises:
            RuntimeError: If go execution fails
            ValueError: If package is invalid or not found
        """
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="os4g-trace-go-"))

        try:
            # Create minimal go.mod file
            go_mod_content = f"""module temp-os4g-trace

go 1.21

require {package} {version if version else "latest"}
"""
            go_mod_path = temp_dir / "go.mod"
            go_mod_path.write_text(go_mod_content)

            # Create a dummy main.go file (required for go mod operations)
            (temp_dir / "main.go").write_text("package main\nfunc main() {}\n")

            # First, run go mod tidy to resolve dependencies
            process = await asyncio.create_subprocess_exec(
                "go",
                "mod",
                "tidy",
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **dict(os.environ),  # noqa: F821
                    "GOFLAGS": "-mod=mod",  # Allow go mod to modify go.mod
                },
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                # Check for common errors
                if "cannot find module" in error_msg.lower():
                    raise ValueError(
                        f"Package '{package}' not found in Go module registry.\n"
                        f"Error: {error_msg}"
                    )
                raise RuntimeError(
                    f"Failed to resolve dependencies for '{package}': {error_msg}"
                )

            # Now run go mod graph to get dependency tree in text format
            process = await asyncio.create_subprocess_exec(
                "go",
                "mod",
                "graph",
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise RuntimeError(
                    f"Failed to get dependency graph for '{package}': {error_msg}"
                )

            # Parse go mod graph output
            graph_output = stdout.decode().strip()
            return self._parse_go_mod_graph(package, graph_output)

        finally:
            # Ensure temporary directory is always cleaned up
            # Use ignore_errors=True to handle permission issues gracefully
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _parse_go_mod_graph(
        self, root_package: str, graph_output: str
    ) -> DependencyGraph:
        """Parse go mod graph output into DependencyGraph.

        The output format of 'go mod graph' is:
        parent@version child@version
        For example:
        temp-os4g-trace@v0.0.0 github.com/spf13/cobra@v1.7.0
        github.com/spf13/cobra@v1.7.0 github.com/inconshreveable/log15@v2.0.0

        Args:
            root_package: The root package name we're tracing
            graph_output: The text output from go mod graph

        Returns:
            DependencyGraph with parsed dependencies
        """
        direct_deps: list[DependencyInfo] = []
        transitive_deps: list[DependencyInfo] = []
        edges: list[DependencyEdge] = []
        seen = set()
        depth_map = {}  # Track depth of each package

        lines = graph_output.strip().split("\n")
        if not lines or (len(lines) == 1 and not lines[0]):
            # No dependencies
            return DependencyGraph(
                root_package=root_package,
                ecosystem="go",
                direct_dependencies=[],
                transitive_dependencies=[],
                edges=[],
            )

        # Find the actual root module from the first line
        # The first line's parent is the temporary module we created
        actual_root_module = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) != 2:
                continue

            parent_full = parts[0]  # e.g., "temp-os4g-trace@v0.0.0"
            child_full = parts[1]  # e.g., "github.com/spf13/cobra@v1.7.0"

            # The first non-empty line tells us the root module
            if actual_root_module is None:
                actual_root_module = parent_full

            # Parse parent and child into name and version
            parent_name, parent_version = self._parse_module_ref(parent_full)
            child_name, child_version = self._parse_module_ref(child_full)

            # Check if this is a direct dependency of the temp root module
            is_direct = parent_full == actual_root_module

            # Only add child if it's not the root package itself
            if child_name == root_package:
                # This is the actual package we're tracing, skip it
                # (it's in the output because go mod graph includes the actual dependency)
                continue

            # Add child as dependency if not seen
            if child_name not in seen:
                dep = DependencyInfo(
                    name=child_name,
                    ecosystem="go",
                    version=child_version,
                    is_direct=is_direct,
                    depth=0 if is_direct else 1,
                )

                if is_direct:
                    direct_deps.append(dep)
                else:
                    transitive_deps.append(dep)

                seen.add(child_name)

            # Add edge (source is parent, target is child)
            edges.append(DependencyEdge(source=parent_name, target=child_name))

        return DependencyGraph(
            root_package=root_package,
            ecosystem="go",
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
            edges=edges,
        )

    @staticmethod
    def _parse_module_ref(module_ref: str) -> tuple[str, str]:
        """Parse a Go module reference into name and version.

        Args:
            module_ref: Module reference string (e.g., "github.com/user/repo@v1.0.0")

        Returns:
            Tuple of (module_name, version)
        """
        if "@" in module_ref:
            name, version = module_ref.rsplit("@", 1)
            return name, version
        return module_ref, "unknown"


def get_go_tool(preferred_tool: str | None = None) -> ExternalTool:
    """Get the best available Go dependency resolution tool.

    Args:
        preferred_tool: Optional tool name to prefer (e.g., "go").
                       If specified and available, returns that tool.
                       If specified but not available, raises RuntimeError.
                       If None, uses auto-detection.

    Returns:
        ExternalTool instance

    Raises:
        RuntimeError: If preferred_tool is specified but not available
        ValueError: If preferred_tool is not a valid Go tool

    Priority order (when preferred_tool is None):
        1. go (standard Go package manager)
    """
    # Map of tool names to tool classes
    GO_TOOLS = {
        "go": GoModTool,
    }

    # If user specified a preferred tool
    if preferred_tool:
        if preferred_tool not in GO_TOOLS:
            raise ValueError(
                f"Tool '{preferred_tool}' is not available for go ecosystem. "
                f"Available tools: {', '.join(GO_TOOLS.keys())}"
            )

        tool = GO_TOOLS[preferred_tool]()
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{preferred_tool}' is not installed. "
                f"Please install it to trace go packages."
            )
        return tool

    # Auto-detection: Try go (standard tool)
    go_tool = GoModTool()
    if go_tool.is_available():
        return go_tool

    # If go not available, return it anyway (will error with helpful message)
    return go_tool
