"""C# ecosystem external tools for dependency resolution."""

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


class DotnetTool(ExternalTool):
    """Use dotnet to resolve C#/.NET package dependencies."""

    @property
    def name(self) -> str:
        return "dotnet"

    @property
    def ecosystem(self) -> str:
        return "csharp"

    def is_available(self) -> bool:
        """Check if dotnet is installed."""
        return shutil.which("dotnet") is not None

    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve dependency tree using dotnet restore.

        Creates a temporary .csproj file, uses dotnet restore to fetch the specified package,
        runs dotnet restore to generate packages.lock.json, then parses the lockfile.

        Note: dotnet restore only fetches metadata and creates a lockfile,
        making it efficient for dependency resolution.

        Args:
            package: Package name to resolve (e.g., "Newtonsoft.Json")
            version: Optional specific version (if None, uses latest)

        Returns:
            DependencyGraph with all resolved dependencies

        Raises:
            RuntimeError: If dotnet execution fails
            ValueError: If package is invalid or not found
        """
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="os4g-trace-csharp-"))

        try:
            # Create minimal .csproj file
            # Use wildcard "*" if no version specified to get latest
            version_attr = f' Version="{version}"' if version else ' Version="*"'
            csproj_content = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="{package}"{version_attr} />
  </ItemGroup>
</Project>
"""
            csproj_path = temp_dir / "temp-os4g-trace.csproj"
            csproj_path.write_text(csproj_content)

            # Run dotnet restore to generate packages.lock.json
            process = await asyncio.create_subprocess_exec(
                "dotnet",
                "restore",
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **dict(os.environ),
                    "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                },
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                stdout_msg = stdout.decode().strip()
                stderr_msg = stderr.decode().strip()
                error_msg = f"{stdout_msg}\n{stderr_msg}".strip()

                # Check for common errors
                if (
                    "Unable to find package" in error_msg
                    or "NU1101" in error_msg  # NuGet error code for package not found
                    or "does not exist" in error_msg.lower()
                ):
                    raise ValueError(
                        f"Package '{package}' not found in NuGet registry.\n"
                        f"Error: {error_msg}"
                    )
                raise RuntimeError(
                    f"Failed to resolve dependencies for '{package}': {error_msg}"
                )

            # Parse packages.lock.json
            lock_path = temp_dir / "packages.lock.json"
            if not lock_path.exists():
                raise RuntimeError(
                    f"dotnet restore succeeded but packages.lock.json was not created for '{package}'"
                )

            # Use existing CSharpResolver to parse lockfile
            from oss_sustain_guard.resolvers.csharp import CSharpResolver

            resolver = CSharpResolver()
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

            # Determine if this is the root package or a direct dependency
            is_direct = pkg.name == root_package

            dep = DependencyInfo(
                name=pkg.name,
                ecosystem="csharp",
                version=pkg.version or "unknown",
                is_direct=is_direct,
                depth=0 if is_direct else 1,
            )

            if is_direct:
                direct_deps.append(dep)
            else:
                # All packages from packages.lock.json are considered direct
                # for simplicity, as .NET doesn't clearly distinguish in lockfile
                direct_deps.append(dep)

            # Add edge from root to this dependency
            edges.append(DependencyEdge(source=root_package, target=pkg.name))

        return DependencyGraph(
            root_package=root_package,
            ecosystem="csharp",
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
            edges=edges,
        )


def get_csharp_tool(preferred_tool: str | None = None) -> ExternalTool:
    """Get the best available C# dependency resolution tool.

    Args:
        preferred_tool: Optional tool name to prefer (e.g., "dotnet").
                       If specified and available, returns that tool.
                       If specified but not available, raises RuntimeError.
                       If None, uses auto-detection.

    Returns:
        ExternalTool instance

    Raises:
        RuntimeError: If preferred_tool is specified but not available
        ValueError: If preferred_tool is not a valid C# tool

    Priority order (when preferred_tool is None):
        1. dotnet (standard .NET CLI tool)
    """
    # Map of tool names to tool classes
    CSHARP_TOOLS = {
        "dotnet": DotnetTool,
    }

    # If user specified a preferred tool
    if preferred_tool:
        if preferred_tool not in CSHARP_TOOLS:
            raise ValueError(
                f"Tool '{preferred_tool}' is not available for csharp ecosystem. "
                f"Available tools: {', '.join(CSHARP_TOOLS.keys())}"
            )

        tool = CSHARP_TOOLS[preferred_tool]()
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{preferred_tool}' is not installed. "
                f"Please install it to trace csharp packages."
            )
        return tool

    # Auto-detection: Try dotnet (standard tool)
    dotnet_tool = DotnetTool()
    if dotnet_tool.is_available():
        return dotnet_tool

    # If dotnet not available, return it anyway (will error with helpful message)
    return dotnet_tool
