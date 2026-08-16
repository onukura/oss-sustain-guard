"""Rust ecosystem external tools for dependency resolution."""

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


class CargoTreeTool(ExternalTool):
    """Use cargo to resolve Rust package dependencies."""

    @property
    def name(self) -> str:
        return "cargo"

    @property
    def ecosystem(self) -> str:
        return "rust"

    def is_available(self) -> bool:
        """Check if cargo is installed."""
        return shutil.which("cargo") is not None

    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve dependency tree using cargo metadata.

        Creates a temporary Cargo.toml, runs cargo metadata to get dependency
        information without building or installing packages.

        Note: cargo metadata only fetches metadata without building/installing,
        making it very efficient for dependency resolution.

        Args:
            package: Package name to resolve (crate name)
            version: Optional specific version (if None, uses latest)

        Returns:
            DependencyGraph with all resolved dependencies

        Raises:
            RuntimeError: If cargo execution fails
            ValueError: If package is invalid or not found
        """
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="os4g-trace-rust-"))

        try:
            # Create minimal Cargo.toml
            version_spec = f'= "{version}"' if version else '"*"'
            cargo_content = f"""[package]
name = "temp-os4g-trace"
version = "0.1.0"
edition = "2021"

[dependencies]
{package} = {version_spec}
"""
            cargo_path = temp_dir / "Cargo.toml"
            cargo_path.write_text(cargo_content)

            # Create dummy src/main.rs (required for cargo to work)
            src_dir = temp_dir / "src"
            src_dir.mkdir()
            (src_dir / "main.rs").write_text("fn main() {}\n")

            # Run cargo metadata to get dependency tree
            # --format-version 1: Use stable JSON format
            # --locked: Don't update Cargo.lock (we want to generate it fresh)
            # Note: We don't use --locked on first run since Cargo.lock doesn't exist yet
            process = await asyncio.create_subprocess_exec(
                "cargo",
                "metadata",
                "--format-version",
                "1",
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                # Check for common errors
                if (
                    "not found in registry" in error_msg.lower()
                    or "no matching package" in error_msg.lower()
                ):
                    raise ValueError(
                        f"Package '{package}' not found in crates.io registry.\n"
                        f"Error: {error_msg}"
                    )
                raise RuntimeError(
                    f"Failed to resolve dependencies for '{package}': {error_msg}"
                )

            # Parse cargo metadata output
            metadata = json.loads(stdout.decode())
            return self._parse_cargo_metadata(package, metadata)

        finally:
            # Ensure temporary directory is always cleaned up
            # Use ignore_errors=True to handle permission issues gracefully
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _parse_cargo_metadata(
        self, root_package: str, metadata: dict
    ) -> DependencyGraph:
        """Parse cargo metadata JSON output into DependencyGraph.

        Args:
            root_package: The root package name we're tracing
            metadata: The JSON output from cargo metadata

        Returns:
            DependencyGraph with parsed dependencies
        """
        packages = {pkg["id"]: pkg for pkg in metadata["packages"]}
        resolve_nodes = {node["id"]: node for node in metadata["resolve"]["nodes"]}

        # Find the root package node
        root_id = metadata["resolve"]["root"]
        root_node = resolve_nodes[root_id]

        direct_deps: list[DependencyInfo] = []
        transitive_deps: list[DependencyInfo] = []
        edges: list[DependencyEdge] = []
        seen = set()

        # Process direct dependencies
        for dep_id in root_node.get("dependencies", []):
            if dep_id not in packages:
                continue

            pkg = packages[dep_id]
            pkg_name = pkg["name"]

            if pkg_name in seen:
                continue

            dep = DependencyInfo(
                name=pkg_name,
                ecosystem="rust",
                version=pkg["version"],
                is_direct=True,
                depth=0,
            )
            direct_deps.append(dep)
            seen.add(pkg_name)

            # Add edge from root to dependency
            edges.append(DependencyEdge(source=root_package, target=pkg_name))

            # Recursively process transitive dependencies
            self._process_dependencies_recursive(
                pkg_name,
                dep_id,
                1,
                packages,
                resolve_nodes,
                transitive_deps,
                edges,
                seen,
            )

        return DependencyGraph(
            root_package=root_package,
            ecosystem="rust",
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
            edges=edges,
        )

    def _process_dependencies_recursive(
        self,
        parent_name: str,
        parent_id: str,
        depth: int,
        packages: dict,
        resolve_nodes: dict,
        transitive_deps: list[DependencyInfo],
        edges: list[DependencyEdge],
        seen: set,
    ) -> None:
        """Recursively process dependencies.

        Args:
            parent_name: Name of the parent package
            parent_id: ID of the parent package in cargo metadata
            depth: Current depth in dependency tree
            packages: Map of package IDs to package info
            resolve_nodes: Map of package IDs to resolve nodes
            transitive_deps: List to accumulate transitive dependencies
            edges: List to accumulate dependency edges
            seen: Set of already processed package names
        """
        if parent_id not in resolve_nodes:
            return

        parent_node = resolve_nodes[parent_id]

        for dep_id in parent_node.get("dependencies", []):
            if dep_id not in packages:
                continue

            pkg = packages[dep_id]
            pkg_name = pkg["name"]

            if pkg_name not in seen:
                dep = DependencyInfo(
                    name=pkg_name,
                    ecosystem="rust",
                    version=pkg["version"],
                    is_direct=False,
                    depth=depth,
                )
                transitive_deps.append(dep)
                seen.add(pkg_name)

            # Add edge from parent to this dependency
            edges.append(DependencyEdge(source=parent_name, target=pkg_name))

            # Recurse into nested dependencies
            self._process_dependencies_recursive(
                pkg_name,
                dep_id,
                depth + 1,
                packages,
                resolve_nodes,
                transitive_deps,
                edges,
                seen,
            )


def get_rust_tool(preferred_tool: str | None = None) -> ExternalTool:
    """Get the best available Rust dependency resolution tool.

    Args:
        preferred_tool: Optional tool name to prefer (e.g., "cargo").
                       If specified and available, returns that tool.
                       If specified but not available, raises RuntimeError.
                       If None, uses auto-detection.

    Returns:
        ExternalTool instance

    Raises:
        RuntimeError: If preferred_tool is specified but not available
        ValueError: If preferred_tool is not a valid Rust tool

    Priority order (when preferred_tool is None):
        1. cargo (standard Rust package manager)
    """
    # Map of tool names to tool classes
    RUST_TOOLS = {
        "cargo": CargoTreeTool,
    }

    # If user specified a preferred tool
    if preferred_tool:
        if preferred_tool not in RUST_TOOLS:
            raise ValueError(
                f"Tool '{preferred_tool}' is not available for rust ecosystem. "
                f"Available tools: {', '.join(RUST_TOOLS.keys())}"
            )

        tool = RUST_TOOLS[preferred_tool]()
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{preferred_tool}' is not installed. "
                f"Please install it to trace rust packages."
            )
        return tool

    # Auto-detection: Try cargo (standard tool)
    cargo_tool = CargoTreeTool()
    if cargo_tool.is_available():
        return cargo_tool

    # If cargo not available, return it anyway (will error with helpful message)
    return cargo_tool
