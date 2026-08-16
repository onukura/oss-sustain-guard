"""Deno lockfile dependency parser."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import (
        DependencyEdge,
        DependencyGraph,
        DependencyInfo,
    )


PARSER = DependencyParserSpec(
    name="deno",
    lockfile_names={"deno.lock"},
    parse=lambda lockfile_path: parse_deno_lockfile(lockfile_path),
)


def parse_deno_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse deno.lock and extract dependencies.

    Deno lockfile format stores remote dependencies with their URLs and integrity hashes.
    Supports both legacy format (with 'remote' section) and new v5 format (with 'specifiers' and 'npm' sections).
    """
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo

    lockfile_path = Path(lockfile_path)
    if not lockfile_path.exists():
        return None

    try:
        with open(lockfile_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    direct_deps: list[DependencyInfo] = []
    transitive_deps: list[DependencyInfo] = []

    # Get direct dependencies from deno.json if available
    direct_deps_set = _get_deno_direct_dependencies(lockfile_path.parent)

    processed = set()

    # New v5 format: check 'specifiers' section
    specifiers = data.get("specifiers", {})
    if specifiers:
        for spec_key, _spec_value in specifiers.items():
            # spec_key format: "npm:package@version"
            name_version = _extract_deno_package_info(spec_key)
            if not name_version or name_version[0] in processed:
                continue

            name, version = name_version
            processed.add(name)

            dep_info = DependencyInfo(
                name=name,
                ecosystem="javascript",
                version=version,
                is_direct=name in direct_deps_set,
                depth=0,
            )

            if name in direct_deps_set:
                direct_deps.append(dep_info)
            else:
                transitive_deps.append(dep_info)

    # Legacy format: check 'remote' section
    remote = data.get("remote", {})
    if remote:
        for url, _metadata in remote.items():
            # Extract package name and version from URL
            name_version = _extract_deno_package_info(url)
            if not name_version or name_version[0] in processed:
                continue

            name, version = name_version
            processed.add(name)

            dep_info = DependencyInfo(
                name=name,
                ecosystem="javascript",
                version=version,
                is_direct=name in direct_deps_set,
                depth=0,
            )

            if name in direct_deps_set:
                direct_deps.append(dep_info)
            else:
                transitive_deps.append(dep_info)

    # Try to get project name from deno.json
    root_name = _get_deno_project_name(lockfile_path.parent)

    # Extract dependency edges from npm section
    from oss_sustain_guard.dependency_graph import DependencyEdge

    edges: list[DependencyEdge] = []
    npm_packages = data.get("npm", {})
    if isinstance(npm_packages, dict):
        for pkg_key, pkg_data in npm_packages.items():
            if not isinstance(pkg_data, dict):
                continue

            # Extract package name and version from key (format: "package@version")
            if "@" in pkg_key:
                # Handle scoped packages like "@babel/core@7.28.5"
                parts = pkg_key.rsplit("@", 1)
                source_name = parts[0] if len(parts) > 0 else pkg_key
            else:
                source_name = pkg_key

            # Get dependencies array
            deps = pkg_data.get("dependencies", [])
            if isinstance(deps, list):
                for dep_name in deps:
                    if isinstance(dep_name, str):
                        # Dependencies may include version info (e.g., "debug@4.4.3")
                        if "@" in dep_name:
                            # Extract just the package name for target
                            dep_parts = dep_name.rsplit("@", 1)
                            target_name = dep_parts[0]
                            version_spec = dep_parts[1] if len(dep_parts) > 1 else None
                        else:
                            target_name = dep_name
                            version_spec = None

                        edges.append(
                            DependencyEdge(
                                source=source_name,
                                target=target_name,
                                version_spec=version_spec,
                            )
                        )

    return DependencyGraph(
        root_package=root_name or "unknown",
        ecosystem="javascript",
        direct_dependencies=direct_deps,
        transitive_dependencies=transitive_deps,
        edges=edges,
    )


def _extract_deno_package_info(url: str) -> tuple[str, str | None] | None:
    """Extract package name and version from Deno module URL.

    Examples:
    - https://deno.land/std@0.208.0/fs/mod.ts -> ("std", "0.208.0")
    - https://deno.land/x/fresh@1.4.0/dev.ts -> ("fresh", "1.4.0")
    - npm:react@18.2.0 -> ("react", "18.2.0")
    """
    # Handle npm: protocol URLs
    if url.startswith("npm:"):
        # Format: npm:package@version or npm:@scope/package@version
        npm_part = url[4:]  # Remove "npm:" prefix
        if "@" in npm_part:
            parts = npm_part.rsplit("@", 1)
            if len(parts) == 2:
                name, version = parts
                return name, version if version else None
        return npm_part, None

    # Handle deno.land URLs
    if "deno.land" in url:
        # Extract from URL path
        import re

        # Match patterns like: std@0.208.0, x/fresh@1.4.0
        match = re.search(r"deno\.land/(?:std|x)/([a-z_\-]+)@([0-9.]+)", url)
        if match:
            name, version = match.groups()
            return name, version

        # Handle URLs without version
        match = re.search(r"deno\.land/(?:std|x)/([a-z_\-]+)", url)
        if match:
            name = match.group(1)
            return name, None

    # Handle other registry URLs (github, esm.sh, etc.)
    import re

    # Try to extract from common patterns
    match = re.search(r"([a-z_\-]+)@([0-9.]+)", url)
    if match:
        name, version = match.groups()
        return name, version

    # Fallback: extract domain/last part
    if "/" in url:
        parts = url.split("/")
        name = parts[-1].split("@")[0].split(".")[0]
        if name and name not in ("raw", "blob", "tree"):
            return name, None

    return None


def _get_deno_direct_dependencies(directory: Path) -> set[str]:
    """Extract direct dependencies from deno.json or deno.jsonc."""
    deno_json_path = directory / "deno.json"
    if not deno_json_path.exists():
        deno_json_path = directory / "deno.jsonc"
    if not deno_json_path.exists():
        return set()

    try:
        with open(deno_json_path) as f:
            # Simple JSON parsing (doesn't handle comments in jsonc)
            content = f.read()
            # Remove comments if JSONC format
            if "// " in content:
                lines = []
                for line in content.split("\n"):
                    if "//" in line:
                        line = line[: line.index("//")]
                    lines.append(line)
                content = "\n".join(lines)

            data = json.loads(content)
    except Exception:
        return set()

    # Collect from imports section
    direct_deps: set[str] = set()
    imports = data.get("imports", {})
    if isinstance(imports, dict):
        for key in imports.keys():
            # Remove trailing slash and extract name
            name = key.strip("/")
            if "/" in name:
                name = name.split("/")[0]
            if name:
                direct_deps.add(name)

    # Also check for dependencies section (newer Deno format)
    deps = data.get("dependencies", {})
    if isinstance(deps, dict):
        for key in deps.keys():
            name = key.strip("/").split("/")[0]
            if name:
                direct_deps.add(name)

    return direct_deps


def _get_deno_project_name(directory: Path) -> str | None:
    """Extract Deno project name from deno.json."""
    deno_json_path = directory / "deno.json"
    if not deno_json_path.exists():
        deno_json_path = directory / "deno.jsonc"
    if not deno_json_path.exists():
        return None

    try:
        with open(deno_json_path) as f:
            data = json.load(f)
        return data.get("name")
    except Exception:
        return None
