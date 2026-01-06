"""Python ecosystem external tools for dependency resolution."""

import asyncio
import shutil
import tempfile
from pathlib import Path

from oss_sustain_guard.dependency_graph import DependencyGraph
from oss_sustain_guard.external_tools.base import ExternalTool


class UvTreeTool(ExternalTool):
    """Use uv to resolve Python package dependencies."""

    @property
    def name(self) -> str:
        return "uv"

    @property
    def ecosystem(self) -> str:
        return "python"

    def is_available(self) -> bool:
        """Check if uv is installed."""
        return shutil.which("uv") is not None

    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve dependency tree using uv lock.

        Creates a temporary pyproject.toml, runs uv lock to generate uv.lock,
        then parses the lockfile to extract dependency information.

        Args:
            package: Package name to resolve
            version: Optional specific version (if None, uses latest)

        Returns:
            DependencyGraph with all resolved dependencies

        Raises:
            RuntimeError: If uv execution fails
            ValueError: If package is invalid or not found
        """
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="os4g-trace-"))

        try:
            # Create minimal pyproject.toml
            pyproject_content = f"""[project]
name = "temp-os4g-trace"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = [
    "{package}{f"=={version}" if version else ""}"
]
"""
            pyproject_path = temp_dir / "pyproject.toml"
            pyproject_path.write_text(pyproject_content)

            # Run uv lock to generate uv.lock
            process = await asyncio.create_subprocess_exec(
                "uv",
                "lock",
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                # Check for common errors
                if "No solution found" in error_msg or "not found" in error_msg.lower():
                    raise ValueError(
                        f"Package '{package}' not found or no compatible version available.\n"
                        f"Error: {error_msg}"
                    )
                raise RuntimeError(
                    f"Failed to resolve dependencies for '{package}': {error_msg}"
                )

            # Parse the generated uv.lock file
            lock_path = temp_dir / "uv.lock"
            if not lock_path.exists():
                raise RuntimeError(
                    f"uv lock succeeded but uv.lock was not created for package '{package}'"
                )

            # Use existing uv lockfile parser
            from oss_sustain_guard.dependency_parsers.python.uv import (
                parse_uv_lockfile,
            )

            dep_graph = parse_uv_lockfile(lock_path)
            if dep_graph is None:
                raise RuntimeError(
                    f"Failed to parse generated uv.lock for package '{package}'"
                )

            # Update root package name to be the traced package
            from oss_sustain_guard.dependency_graph import DependencyGraph

            return DependencyGraph(
                root_package=package,
                ecosystem=dep_graph.ecosystem,
                direct_dependencies=dep_graph.direct_dependencies,
                transitive_dependencies=dep_graph.transitive_dependencies,
                edges=dep_graph.edges,
            )

        finally:
            # Clean up temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)


def get_python_tool() -> ExternalTool:
    """Get the best available Python dependency resolution tool.

    Returns:
        ExternalTool instance (currently only UvTreeTool)

    Priority order:
        1. uv (fast and modern)
        2. (future: pip, pipdeptree, etc.)
    """
    # Try uv first
    uv_tool = UvTreeTool()
    if uv_tool.is_available():
        return uv_tool

    # Future: Add fallback tools here
    # pip_tool = PipShowTool()
    # if pip_tool.is_available():
    #     return pip_tool

    # If no tools available, return uv (which will error with helpful message)
    return uv_tool
