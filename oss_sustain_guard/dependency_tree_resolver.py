"""Dependency tree resolution using external package manager tools."""

from pathlib import Path

from oss_sustain_guard.cli_utils.helpers import parse_package_spec
from oss_sustain_guard.dependency_graph import DependencyGraph


def is_lockfile_path(input_str: str) -> bool:
    """Determine if input is a lockfile path or a package name.

    Args:
        input_str: User input string

    Returns:
        True if input appears to be a file path, False if it's a package name
    """
    path = Path(input_str)

    # If file exists, it's definitely a lockfile
    if path.exists():
        return True

    # If contains path separators, treat as file path
    if "/" in input_str or "\\" in input_str:
        return True

    # If has common lockfile extensions, treat as file path
    if path.suffix in [".txt", ".lock", ".json", ".toml", ".yaml", ".yml"]:
        return True

    # Otherwise, treat as package name
    return False


async def resolve_dependency_tree(
    package_name: str,
    ecosystem: str | None = None,
    version: str | None = None,
    max_depth: int | None = None,
    tool_name: str | None = None,
) -> DependencyGraph:
    """Resolve dependency tree for a package using external tools.

    Args:
        package_name: Name of the package to trace
        ecosystem: Package ecosystem (python, javascript, rust, etc.)
                  If None, defaults to python
        version: Specific version to analyze (if None, uses latest)
        max_depth: Maximum depth to traverse (if None, unlimited)
        tool_name: Specific tool to use (e.g., "npm", "pnpm", "uv").
                  If None, uses auto-detection based on availability.

    Returns:
        DependencyGraph containing all resolved dependencies

    Raises:
        RuntimeError: If required tool is not installed
        ValueError: If package not found, invalid, or tool_name incompatible with ecosystem
    """
    # Parse ecosystem:package format if ecosystem not explicitly provided
    if ecosystem is None:
        # Use parse_package_spec which defaults to python
        parsed_ecosystem, parsed_package = parse_package_spec(package_name)
        ecosystem = parsed_ecosystem
        package_name = parsed_package

    # Import tool implementations here to avoid circular imports
    if ecosystem == "python":
        from oss_sustain_guard.external_tools.python_tools import get_python_tool

        tool = get_python_tool(preferred_tool=tool_name)
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{tool.name}' is not installed. "
                f"Please install it to trace {ecosystem} packages."
            )

        return await tool.resolve_tree(package_name, version)

    elif ecosystem == "javascript":
        from oss_sustain_guard.external_tools.javascript_tools import (
            get_javascript_tool,
        )

        tool = get_javascript_tool(preferred_tool=tool_name)
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{tool.name}' is not installed. "
                f"Please install pnpm, bun, or npm to trace {ecosystem} packages."
            )

        return await tool.resolve_tree(package_name, version)

    elif ecosystem == "rust":
        from oss_sustain_guard.external_tools.rust_tools import get_rust_tool

        tool = get_rust_tool(preferred_tool=tool_name)
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{tool.name}' is not installed. "
                f"Please install cargo to trace {ecosystem} packages."
            )

        return await tool.resolve_tree(package_name, version)

    elif ecosystem == "ruby":
        from oss_sustain_guard.external_tools.ruby_tools import get_ruby_tool

        tool = get_ruby_tool(preferred_tool=tool_name)
        if not tool.is_available():
            raise RuntimeError(
                f"Required tool '{tool.name}' is not installed. "
                f"Please install bundler to trace {ecosystem} packages."
            )

        return await tool.resolve_tree(package_name, version)

    else:
        raise NotImplementedError(
            f"Package mode is not yet implemented for {ecosystem} ecosystem. "
            f"Currently supported: Python, JavaScript, Rust, Ruby. "
            f"For other ecosystems, please use lockfile mode: os4g trace <lockfile>"
        )
