"""Rust Cargo.lock dependency parser."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from oss_sustain_guard.dependency_graph import tomllib
from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import DependencyGraph


PARSER = DependencyParserSpec(
    name="cargo",
    lockfile_names={"Cargo.lock"},
    parse=lambda lockfile_path: parse_cargo_lockfile(lockfile_path),
)


def parse_cargo_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse Cargo.lock (TOML format)."""
    from oss_sustain_guard.dependency_graph import (
        DependencyEdge,
        DependencyGraph,
        DependencyInfo,
    )

    lockfile_path = Path(lockfile_path)
    if not lockfile_path.exists():
        return None

    try:
        with open(lockfile_path, "rb") as f:
            data = tomllib.load(f)
    except OSError:
        return None

    direct_deps: list[DependencyInfo] = []
    transitive_deps: list[DependencyInfo] = []
    edges: list[DependencyEdge] = []

    packages = data.get("package", [])
    root_name = None

    for i, package in enumerate(packages):
        name = package.get("name", "")
        version = package.get("version", "")
        if not name:
            continue

        # First package is typically the root
        is_direct = i == 0
        if is_direct:
            root_name = name

        dep_info = DependencyInfo(
            name=name,
            ecosystem="rust",
            version=version,
            is_direct=is_direct,
            depth=0 if is_direct else 1,
        )

        if is_direct:
            direct_deps.append(dep_info)
        else:
            transitive_deps.append(dep_info)

        # Extract dependency edges
        dependencies = package.get("dependencies", [])
        if isinstance(dependencies, list):
            for dep in dependencies:
                if isinstance(dep, str):
                    # Format: "package_name version" or "package_name"
                    parts = dep.split(" ", 1)
                    dep_name = parts[0]
                    version_spec = parts[1] if len(parts) > 1 else None
                    edges.append(
                        DependencyEdge(
                            source=name,
                            target=dep_name,
                            version_spec=version_spec,
                        )
                    )

    return DependencyGraph(
        root_package=root_name or "unknown",
        ecosystem="rust",
        direct_dependencies=direct_deps,
        transitive_dependencies=transitive_deps,
        edges=edges,
    )
