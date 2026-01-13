"""Java ecosystem external tools for dependency resolution."""

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


class MavenTreeTool(ExternalTool):
    """Use Maven to resolve Java package dependencies."""

    @property
    def name(self) -> str:
        return "mvn"

    @property
    def ecosystem(self) -> str:
        return "java"

    def is_available(self) -> bool:
        """Check if Maven is installed."""
        return shutil.which("mvn") is not None

    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve dependency tree using Maven dependency:tree.

        Creates a temporary pom.xml file, uses mvn dependency:tree to generate
        a JSON dependency tree, then parses the JSON output.

        Maven coordinates can be specified as:
        - groupId:artifactId (e.g., "junit:junit")
        - groupId:artifactId:version (version in third part, overrides version param)

        Args:
            package: Maven coordinates (groupId:artifactId or groupId:artifactId:version)
            version: Optional specific version (if None and not in package, uses LATEST)

        Returns:
            DependencyGraph with all resolved dependencies

        Raises:
            RuntimeError: If Maven execution fails
            ValueError: If package format is invalid or not found
        """
        # Parse Maven coordinates
        parts = package.split(":")
        if len(parts) < 2:
            raise ValueError(
                f"Invalid Maven coordinates '{package}'. "
                f"Expected format: 'groupId:artifactId' or 'groupId:artifactId:version'"
            )

        group_id = parts[0]
        artifact_id = parts[1]
        # Version can come from the coordinates or the version parameter
        coord_version = parts[2] if len(parts) >= 3 else None
        final_version = coord_version or version or "LATEST"

        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="os4g-trace-java-"))

        try:
            # Create minimal pom.xml
            pom_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.os4g.trace</groupId>
    <artifactId>temp-trace</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <dependencies>
        <dependency>
            <groupId>{group_id}</groupId>
            <artifactId>{artifact_id}</artifactId>
            <version>{final_version}</version>
        </dependency>
    </dependencies>
</project>
"""
            pom_path = temp_dir / "pom.xml"
            pom_path.write_text(pom_content)

            # Output file for JSON tree
            output_file = temp_dir / "dependency-tree.json"

            # Run mvn dependency:tree with JSON output
            # -DoutputType=json: Generate JSON format
            # -DoutputFile=...: Write to file
            # -B: Batch mode (non-interactive)
            # -q: Quiet mode (suppress most output)
            process = await asyncio.create_subprocess_exec(
                "mvn",
                "dependency:tree",
                f"-DoutputType=json",
                f"-DoutputFile={output_file}",
                "-B",  # Batch mode
                "-q",  # Quiet
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **dict(os.environ),
                    "MAVEN_OPTS": "-Dorg.slf4j.simpleLogger.log.org.apache.maven.cli.transfer.Slf4jMavenTransferListener=warn",
                },
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                stdout_msg = stdout.decode().strip()
                stderr_msg = stderr.decode().strip()
                error_msg = f"{stdout_msg}\n{stderr_msg}".strip()

                # Check for common errors
                if (
                    "Could not find artifact" in error_msg
                    or "Failed to collect dependencies" in error_msg
                    or "does not exist" in error_msg.lower()
                ):
                    raise ValueError(
                        f"Package '{group_id}:{artifact_id}' not found in Maven Central.\n"
                        f"Error: {error_msg}"
                    )
                raise RuntimeError(
                    f"Failed to resolve dependencies for '{package}': {error_msg}"
                )

            # Parse JSON output
            if not output_file.exists():
                raise RuntimeError(
                    f"Maven dependency:tree succeeded but output file was not created for '{package}'"
                )

            tree_json = json.loads(output_file.read_text())

            # Convert to DependencyGraph
            return self._parse_maven_tree(
                f"{group_id}:{artifact_id}", tree_json
            )

        finally:
            # Ensure temporary directory is always cleaned up
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _parse_maven_tree(
        self, root_package: str, tree_json: dict
    ) -> DependencyGraph:
        """Parse Maven dependency tree JSON into DependencyGraph.

        JSON structure:
        {
          "groupId": "...",
          "artifactId": "...",
          "version": "...",
          "type": "jar",
          "scope": "compile",
          "children": [...]
        }

        Args:
            root_package: The root package name (groupId:artifactId)
            tree_json: Parsed JSON from mvn dependency:tree

        Returns:
            DependencyGraph with parsed dependencies
        """
        direct_deps: list[DependencyInfo] = []
        transitive_deps: list[DependencyInfo] = []
        edges: list[DependencyEdge] = []
        seen = set()

        # Extract root package info from JSON
        # Note: The JSON root is the temporary project (com.os4g.trace:temp-trace)
        # We need to find the actual requested package in its children
        temp_project_name = f"{tree_json.get('groupId', '')}:{tree_json.get('artifactId', '')}"

        # Process children (should contain the actual requested package)
        children = tree_json.get("children", [])

        # Find the requested package in children
        actual_root = None
        for child in children:
            child_group = child.get("groupId", "")
            child_artifact = child.get("artifactId", "")
            child_name = f"{child_group}:{child_artifact}"

            # This should be our actual requested package
            if child_name == root_package or len(children) == 1:
                actual_root = child
                break

        if not actual_root:
            # Fallback: use first child if we can't identify the requested package
            actual_root = children[0] if children else tree_json

        # Extract actual root info
        root_group = actual_root.get("groupId", "")
        root_artifact = actual_root.get("artifactId", "")
        root_version = actual_root.get("version", "unknown")
        actual_root_name = f"{root_group}:{root_artifact}"

        # Add actual root as direct dependency
        root_dep = DependencyInfo(
            name=actual_root_name,
            ecosystem="java",
            version=root_version,
            is_direct=True,
            depth=0,
        )
        direct_deps.append(root_dep)
        seen.add(actual_root_name)

        # Process children of the actual root (direct dependencies)
        actual_children = actual_root.get("children", [])
        for child in actual_children:
            self._process_dependency(
                child,
                actual_root_name,
                1,
                direct_deps,
                transitive_deps,
                edges,
                seen,
            )

        return DependencyGraph(
            root_package=root_package,
            ecosystem="java",
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
            edges=edges,
        )

    def _process_dependency(
        self,
        dep_json: dict,
        parent_name: str,
        depth: int,
        direct_deps: list[DependencyInfo],
        transitive_deps: list[DependencyInfo],
        edges: list[DependencyEdge],
        seen: set,
    ) -> None:
        """Recursively process a dependency node.

        Args:
            dep_json: Dependency JSON object
            parent_name: Name of parent dependency
            depth: Current depth in tree
            direct_deps: List to accumulate direct dependencies
            transitive_deps: List to accumulate transitive dependencies
            edges: List to accumulate edges
            seen: Set of already processed dependencies
        """
        group_id = dep_json.get("groupId", "")
        artifact_id = dep_json.get("artifactId", "")
        version = dep_json.get("version", "unknown")
        dep_name = f"{group_id}:{artifact_id}"

        # Skip if already seen
        if dep_name in seen:
            # Still add edge even if dependency was seen before
            edges.append(DependencyEdge(source=parent_name, target=dep_name))
            return

        seen.add(dep_name)

        # Create dependency info
        dep = DependencyInfo(
            name=dep_name,
            ecosystem="java",
            version=version,
            is_direct=(depth == 1),
            depth=depth,
        )

        if depth == 1:
            direct_deps.append(dep)
        else:
            transitive_deps.append(dep)

        # Add edge
        edges.append(DependencyEdge(source=parent_name, target=dep_name))

        # Process children (transitive dependencies)
        children = dep_json.get("children", [])
        for child in children:
            self._process_dependency(
                child,
                dep_name,
                depth + 1,
                direct_deps,
                transitive_deps,
                edges,
                seen,
            )


def get_java_tool(preferred_tool: str | None = None) -> ExternalTool:
    """Get the best available Java dependency resolution tool.

    Args:
        preferred_tool: Optional tool name to prefer (e.g., "mvn", "gradle").
                       If specified and available, returns that tool.
                       If specified but not available, raises RuntimeError.
                       If None, uses auto-detection.

    Returns:
        ExternalTool instance

    Raises:
        RuntimeError: If preferred_tool is specified but not available
        ValueError: If preferred_tool is not a valid Java tool

    Priority order (when preferred_tool is None):
        1. mvn (Apache Maven - most widely used)
        2. (future: gradle)
    """
    # Map of tool names to tool classes
    JAVA_TOOLS = {
        "mvn": MavenTreeTool,
        "maven": MavenTreeTool,  # Alias
    }

    # If user specified a preferred tool
    if preferred_tool:
        if preferred_tool not in JAVA_TOOLS:
            raise ValueError(
                f"Tool '{preferred_tool}' is not available for java ecosystem. "
                f"Available tools: {', '.join(JAVA_TOOLS.keys())}"
            )

        tool = JAVA_TOOLS[preferred_tool]()
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{preferred_tool}' is not installed. "
                f"Please install it to trace java packages."
            )
        return tool

    # Auto-detection: Try Maven (standard tool)
    maven_tool = MavenTreeTool()
    if maven_tool.is_available():
        return maven_tool

    # If Maven not available, return it anyway (will error with helpful message)
    return maven_tool
