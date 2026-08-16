"""Ruby ecosystem external tools for dependency resolution."""

import asyncio
import re
import shutil
import tempfile
from pathlib import Path

from oss_sustain_guard.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyInfo,
)
from oss_sustain_guard.external_tools.base import ExternalTool


class BundlerTreeTool(ExternalTool):
    """Use bundler to resolve Ruby gem dependencies."""

    @property
    def name(self) -> str:
        return "bundler"

    @property
    def ecosystem(self) -> str:
        return "ruby"

    def is_available(self) -> bool:
        """Check if bundler is installed."""
        return shutil.which("bundle") is not None

    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve dependency tree using bundler.

        Creates a temporary Gemfile, runs bundle install to generate Gemfile.lock,
        then parses the lockfile for dependency information.

        Args:
            package: Package name to resolve (gem name)
            version: Optional specific version (if None, uses latest)

        Returns:
            DependencyGraph with all resolved dependencies

        Raises:
            RuntimeError: If bundler execution fails
            ValueError: If package is invalid or not found
        """
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="os4g-trace-ruby-"))

        try:
            # Create minimal Gemfile
            version_spec = f", '{version}'" if version else ""
            gemfile_content = f"""source 'https://rubygems.org'

gem '{package}'{version_spec}
"""
            gemfile_path = temp_dir / "Gemfile"
            gemfile_path.write_text(gemfile_content)

            # Run bundle install to generate Gemfile.lock
            # --quiet: Suppress output
            # --jobs 1: Use single thread to avoid potential issues
            process = await asyncio.create_subprocess_exec(
                "bundle",
                "install",
                "--quiet",
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                # Check for common errors
                if (
                    "Could not find" in error_msg
                    or "not find gem" in error_msg
                    or "no such gem" in error_msg.lower()
                ):
                    raise ValueError(
                        f"Package '{package}' not found in RubyGems.\n"
                        f"Error: {error_msg}"
                    )
                raise RuntimeError(
                    f"Failed to resolve dependencies for '{package}': {error_msg}"
                )

            # Parse Gemfile.lock
            lockfile_path = temp_dir / "Gemfile.lock"
            if not lockfile_path.exists():
                raise RuntimeError(f"Gemfile.lock was not generated for '{package}'")

            lockfile_content = lockfile_path.read_text()
            return self._parse_gemfile_lock(package, lockfile_content)

        finally:
            # Ensure temporary directory is always cleaned up
            # Use ignore_errors=True to handle permission issues gracefully
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _parse_gemfile_lock(
        self, root_package: str, lockfile_content: str
    ) -> DependencyGraph:
        """Parse Gemfile.lock content into DependencyGraph.

        Gemfile.lock format:
        ```
        GEM
          remote: https://rubygems.org/
          specs:
            gem-name (1.2.3)
              dependency1 (>= 1.0)
              dependency2 (~> 2.0)
        ```

        Args:
            root_package: The root package name we're tracing
            lockfile_content: Contents of Gemfile.lock

        Returns:
            DependencyGraph with parsed dependencies
        """
        direct_deps: list[DependencyInfo] = []
        transitive_deps: list[DependencyInfo] = []
        edges: list[DependencyEdge] = []
        seen = set()

        # Parse GEM section
        gem_section_match = re.search(
            r"GEM\s+remote:.*?specs:(.*?)(?=\n\w|\Z)", lockfile_content, re.DOTALL
        )

        if not gem_section_match:
            # No dependencies found
            return DependencyGraph(
                root_package=root_package,
                ecosystem="ruby",
                direct_dependencies=[],
                transitive_dependencies=[],
                edges=[],
            )

        specs_content = gem_section_match.group(1)

        # Build a dictionary of all gems and their dependencies
        gem_info: dict[str, dict] = {}
        current_gem = None

        for line in specs_content.split("\n"):
            # Match gem declaration: "    gem-name (1.2.3)"
            gem_match = re.match(r"^\s{4}(\S+)\s+\(([^)]+)\)", line)
            if gem_match:
                gem_name = gem_match.group(1)
                gem_version = gem_match.group(2)
                current_gem = gem_name
                gem_info[gem_name] = {
                    "version": gem_version,
                    "dependencies": [],
                }
                continue

            # Match dependency declaration: "      dependency-name (>= 1.0)"
            if current_gem:
                dep_match = re.match(r"^\s{6}(\S+)", line)
                if dep_match:
                    dep_name = dep_match.group(1)
                    gem_info[current_gem]["dependencies"].append(dep_name)

        # Identify direct dependencies (the root package and its deps)
        if root_package in gem_info:
            root_info = gem_info[root_package]

            # Add root package as a direct dependency
            root_dep = DependencyInfo(
                name=root_package,
                ecosystem="ruby",
                version=root_info["version"],
                is_direct=True,
                depth=0,
            )
            direct_deps.append(root_dep)
            seen.add(root_package)

            # Process root's dependencies
            for dep_name in root_info["dependencies"]:
                if dep_name not in gem_info:
                    continue

                if dep_name not in seen:
                    dep_info = gem_info[dep_name]
                    dep = DependencyInfo(
                        name=dep_name,
                        ecosystem="ruby",
                        version=dep_info["version"],
                        is_direct=True,
                        depth=0,
                    )
                    direct_deps.append(dep)
                    seen.add(dep_name)

                # Add edge from root to dependency
                edges.append(DependencyEdge(source=root_package, target=dep_name))

                # Recursively process transitive dependencies
                self._process_gem_dependencies_recursive(
                    dep_name,
                    gem_info,
                    1,
                    transitive_deps,
                    edges,
                    seen,
                )

        return DependencyGraph(
            root_package=root_package,
            ecosystem="ruby",
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
            edges=edges,
        )

    def _process_gem_dependencies_recursive(
        self,
        parent_name: str,
        gem_info: dict,
        depth: int,
        transitive_deps: list[DependencyInfo],
        edges: list[DependencyEdge],
        seen: set,
    ) -> None:
        """Recursively process gem dependencies.

        Args:
            parent_name: Name of the parent gem
            gem_info: Dictionary of all gems and their info
            depth: Current depth in dependency tree
            transitive_deps: List to accumulate transitive dependencies
            edges: List to accumulate dependency edges
            seen: Set of already processed gem names
        """
        if parent_name not in gem_info:
            return

        parent_info = gem_info[parent_name]

        for dep_name in parent_info["dependencies"]:
            if dep_name not in gem_info:
                continue

            if dep_name not in seen:
                dep_info = gem_info[dep_name]
                dep = DependencyInfo(
                    name=dep_name,
                    ecosystem="ruby",
                    version=dep_info["version"],
                    is_direct=False,
                    depth=depth,
                )
                transitive_deps.append(dep)
                seen.add(dep_name)

            # Add edge from parent to this dependency
            edges.append(DependencyEdge(source=parent_name, target=dep_name))

            # Recurse into nested dependencies
            self._process_gem_dependencies_recursive(
                dep_name,
                gem_info,
                depth + 1,
                transitive_deps,
                edges,
                seen,
            )


def get_ruby_tool(preferred_tool: str | None = None) -> ExternalTool:
    """Get the best available Ruby dependency resolution tool.

    Args:
        preferred_tool: Optional tool name to prefer (e.g., "bundler").
                       If specified and available, returns that tool.
                       If specified but not available, raises RuntimeError.
                       If None, uses auto-detection.

    Returns:
        ExternalTool instance

    Raises:
        RuntimeError: If preferred_tool is specified but not available
        ValueError: If preferred_tool is not a valid Ruby tool

    Priority order (when preferred_tool is None):
        1. bundler (standard Ruby dependency manager)
    """
    # Map of tool names to tool classes
    RUBY_TOOLS = {
        "bundler": BundlerTreeTool,
    }

    # If user specified a preferred tool
    if preferred_tool:
        if preferred_tool not in RUBY_TOOLS:
            raise ValueError(
                f"Tool '{preferred_tool}' is not available for ruby ecosystem. "
                f"Available tools: {', '.join(RUBY_TOOLS.keys())}"
            )

        tool = RUBY_TOOLS[preferred_tool]()
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{preferred_tool}' is not installed. "
                f"Please install it to trace ruby packages."
            )
        return tool

    # Auto-detection: Try bundler (standard tool)
    bundler_tool = BundlerTreeTool()
    if bundler_tool.is_available():
        return bundler_tool

    # If bundler not available, return it anyway (will error with helpful message)
    return bundler_tool
