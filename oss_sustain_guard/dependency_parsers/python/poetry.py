"""Poetry lockfile dependency parser."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from oss_sustain_guard.dependency_graph import tomllib
from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_parsers.python.shared import (
    get_poetry_direct_dependencies,
    get_python_project_name,
)

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo


PARSER = DependencyParserSpec(
    name="poetry",
    lockfile_names={"poetry.lock"},
    parse=lambda lockfile_path: parse_poetry_lockfile(lockfile_path),
)


def parse_poetry_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse poetry.lock file."""
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
    direct_package_names = get_poetry_direct_dependencies(lockfile_path.parent)
    edges: list[DependencyEdge] = []

    for package in data.get("package", []):
        name = package.get("name", "")
        version = package.get("version", "")
        if not name:
            continue

        is_direct = name.lower() in {p.lower() for p in direct_package_names}
        dep_info = DependencyInfo(
            name=name,
            ecosystem="python",
            version=version,
            is_direct=is_direct,
            depth=0 if is_direct else 1,
        )

        if is_direct:
            direct_deps.append(dep_info)
        else:
            transitive_deps.append(dep_info)

        # Extract dependency edges
        dependencies = package.get("dependencies", {})
        if isinstance(dependencies, dict):
            for dep_name, dep_spec in dependencies.items():
                version_spec = None
                if isinstance(dep_spec, dict):
                    version_spec = dep_spec.get("version")
                elif isinstance(dep_spec, str):
                    version_spec = dep_spec
                edges.append(
                    DependencyEdge(
                        source=name,
                        target=dep_name,
                        version_spec=version_spec,
                    )
                )

    root_name = get_python_project_name(lockfile_path.parent)

    return DependencyGraph(
        root_package=root_name or "unknown",
        ecosystem="python",
        direct_dependencies=direct_deps,
        transitive_dependencies=transitive_deps,
        edges=edges,
    )
