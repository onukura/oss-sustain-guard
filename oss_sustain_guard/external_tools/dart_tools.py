"""Dart ecosystem external tools for dependency resolution."""

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


class PubTreeTool(ExternalTool):
    """Use pub/dart to resolve Dart package dependencies."""

    @property
    def name(self) -> str:
        return "dart"

    @property
    def ecosystem(self) -> str:
        return "dart"

    def is_available(self) -> bool:
        """Check if dart is installed."""
        return shutil.which("dart") is not None

    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve dependency tree using dart pub get.

        Creates a temporary pubspec.yaml file, uses dart pub get to fetch the specified package,
        generates pubspec.lock, then parses the lockfile.

        Note: dart pub get only fetches metadata and creates a lockfile,
        making it efficient for dependency resolution.

        Args:
            package: Package name to resolve (e.g., "http", "flutter")
            version: Optional specific version (if None, uses latest with ^)

        Returns:
            DependencyGraph with all resolved dependencies

        Raises:
            RuntimeError: If dart pub execution fails
            ValueError: If package is invalid or not found
        """
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="os4g-trace-dart-"))

        try:
            # Create minimal pubspec.yaml
            # Use ^version for latest compatible, or version constraint if specified
            version_constraint = f"^{version}" if version else "any"
            pubspec_content = f"""name: temp_os4g_trace
description: Temporary project for dependency tracing
version: 0.1.0
publish_to: none

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  {package}: {version_constraint}
"""
            pubspec_path = temp_dir / "pubspec.yaml"
            pubspec_path.write_text(pubspec_content)

            # Run dart pub get to generate pubspec.lock
            process = await asyncio.create_subprocess_exec(
                "dart",
                "pub",
                "get",
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **dict(os.environ),
                    "PUB_CACHE": str(temp_dir / ".pub-cache"),  # Use temp cache
                },
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                # Check for common errors
                if (
                    "Could not find" in error_msg
                    or "version solving failed" in error_msg.lower()
                    or "doesn't exist" in error_msg.lower()
                ):
                    raise ValueError(
                        f"Package '{package}' not found on pub.dev or version incompatible.\n"
                        f"Error: {error_msg}"
                    )
                raise RuntimeError(
                    f"Failed to resolve dependencies for '{package}': {error_msg}"
                )

            # Parse pubspec.lock
            lock_path = temp_dir / "pubspec.lock"
            if not lock_path.exists():
                raise RuntimeError(
                    f"dart pub get succeeded but pubspec.lock was not created for '{package}'"
                )

            # Use existing DartResolver to parse lockfile
            from oss_sustain_guard.resolvers.dart import DartResolver

            resolver = DartResolver()
            packages = await resolver.parse_lockfile(lock_path)

            # Convert PackageInfo list to DependencyGraph
            return self._build_dependency_graph(package, packages)

        finally:
            # Ensure temporary directory is always cleaned up
            # Use ignore_errors=True to handle permission issues gracefully
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _build_dependency_graph(
        self, root_package: str, packages: list
    ) -> DependencyGraph:
        """Build DependencyGraph from PackageInfo list.

        Args:
            root_package: The root package name we're tracing
            packages: List of PackageInfo objects from resolver

        Returns:
            DependencyGraph with parsed dependencies
        """
        direct_deps: list[DependencyInfo] = []
        transitive_deps: list[DependencyInfo] = []
        edges: list[DependencyEdge] = []
        seen = set()

        for pkg in packages:
            # Skip if already seen
            if pkg.name in seen:
                continue
            seen.add(pkg.name)

            # Determine if this is the root package or a dependency
            is_direct = pkg.name == root_package

            dep = DependencyInfo(
                name=pkg.name,
                ecosystem="dart",
                version=pkg.version or "unknown",
                is_direct=is_direct,
                depth=0 if is_direct else 1,
            )

            if is_direct:
                direct_deps.append(dep)
            else:
                # All packages from pubspec.lock except root are dependencies
                # We'll treat them as direct for simplicity since pubspec.lock
                # doesn't distinguish direct vs transitive clearly
                direct_deps.append(dep)

            # Add edge from root to this dependency
            edges.append(DependencyEdge(source=root_package, target=pkg.name))

        return DependencyGraph(
            root_package=root_package,
            ecosystem="dart",
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
            edges=edges,
        )


def get_dart_tool(preferred_tool: str | None = None) -> ExternalTool:
    """Get the best available Dart dependency resolution tool.

    Args:
        preferred_tool: Optional tool name to prefer (e.g., "dart", "flutter").
                       If specified and available, returns that tool.
                       If specified but not available, raises RuntimeError.
                       If None, uses auto-detection.

    Returns:
        ExternalTool instance

    Raises:
        RuntimeError: If preferred_tool is specified but not available
        ValueError: If preferred_tool is not a valid Dart tool

    Priority order (when preferred_tool is None):
        1. dart (standard Dart SDK tool)
        2. (future: flutter pub for Flutter packages)
    """
    # Map of tool names to tool classes
    DART_TOOLS = {
        "dart": PubTreeTool,
        "pub": PubTreeTool,  # Alias for dart
    }

    # If user specified a preferred tool
    if preferred_tool:
        if preferred_tool not in DART_TOOLS:
            raise ValueError(
                f"Tool '{preferred_tool}' is not available for dart ecosystem. "
                f"Available tools: {', '.join(DART_TOOLS.keys())}"
            )

        tool = DART_TOOLS[preferred_tool]()
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{preferred_tool}' is not installed. "
                f"Please install it to trace dart packages."
            )
        return tool

    # Auto-detection: Try dart (standard tool)
    dart_tool = PubTreeTool()
    if dart_tool.is_available():
        return dart_tool

    # If dart not available, return it anyway (will error with helpful message)
    return dart_tool
