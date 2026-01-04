"""npm lockfile dependency parser."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_parsers.javascript.shared import (
    extract_npm_path_info,
    get_javascript_project_name,
)

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo


PARSER = DependencyParserSpec(
    name="npm",
    lockfile_names={"package-lock.json"},
    parse=lambda lockfile_path: parse_npm_lockfile(lockfile_path),
)


def parse_npm_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse package-lock.json (npm v7+ format with nested packages)."""
    from oss_sustain_guard.dependency_graph import (
        DependencyEdge,
        DependencyGraph,
        DependencyInfo,
    )

    lockfile_path = Path(lockfile_path)
    if not lockfile_path.exists():
        return None

    try:
        with open(lockfile_path) as f:
            data = json.load(f)
    except OSError:
        return None

    direct_deps: list[DependencyInfo] = []
    transitive_deps: list[DependencyInfo] = []
    edges: list[DependencyEdge] = []

    packages = data.get("packages", {})
    for pkg_spec, pkg_data in packages.items():
        if pkg_spec == "":
            continue

        name, depth = extract_npm_path_info(pkg_spec)
        if not name:
            continue
        version = pkg_data.get("version", "")

        dep_info = DependencyInfo(
            name=name,
            ecosystem="javascript",
            version=version if version else None,
            is_direct=depth == 0,
            depth=depth,
        )

        if depth == 0:
            direct_deps.append(dep_info)
        else:
            transitive_deps.append(dep_info)

        # Extract dependency edges
        dependencies = pkg_data.get("dependencies", {})
        if isinstance(dependencies, dict):
            for dep_name in dependencies.keys():
                edges.append(
                    DependencyEdge(
                        source=name,
                        target=dep_name,
                        version_spec=None,
                    )
                )

    root_name = get_javascript_project_name(lockfile_path.parent)

    return DependencyGraph(
        root_package=root_name or "unknown",
        ecosystem="javascript",
        direct_dependencies=direct_deps,
        transitive_dependencies=transitive_deps,
        edges=edges,
    )
