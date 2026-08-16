"""Yarn lockfile dependency parser."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_parsers.javascript.shared import (
    extract_yarn_package_name,
    get_javascript_dev_dependencies,
    get_javascript_direct_dependencies,
    get_javascript_project_name,
)

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo


PARSER = DependencyParserSpec(
    name="yarn",
    lockfile_names={"yarn.lock"},
    parse=lambda lockfile_path: parse_yarn_lockfile(lockfile_path),
)


def parse_yarn_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse yarn.lock (supports Yarn v1 format)."""
    from oss_sustain_guard.dependency_graph import (
        DependencyEdge,
        DependencyGraph,
        DependencyInfo,
    )

    lockfile_path = Path(lockfile_path)
    if not lockfile_path.exists():
        return None

    try:
        content = lockfile_path.read_text(encoding="utf-8")
    except OSError:
        return None

    versions_by_name: dict[str, tuple[str, str | None]] = {}
    current_packages: list[str] = []
    edges: list[DependencyEdge] = []
    current_package_name: str | None = None

    for line in content.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            current_packages = []
            current_package_name = None
            continue

        if not line.startswith(" ") and line.endswith(":"):
            header = line.rstrip(":")
            descriptors = [part.strip() for part in header.split(",")]
            current_packages = []
            for descriptor in descriptors:
                name = extract_yarn_package_name(descriptor)
                if not name:
                    continue
                current_packages.append(name)
                current_package_name = name
                versions_by_name.setdefault(name.lower(), (name, None))
            continue

        version_match = re.match(r'\s+version\s+"?([^"\s]+)"?', line)
        if version_match and current_packages:
            version = version_match.group(1).strip()
            for name in current_packages:
                versions_by_name[name.lower()] = (name, version)
            continue

        # Extract dependencies (dependencies section in yarn.lock)
        dep_match = re.match(r"\s+(\w[\w\-\.]*)\s+(.+)", line)
        if dep_match and current_package_name:
            dep_name = dep_match.group(1).strip()
            dep_spec = dep_match.group(2).strip()
            if dep_name and dep_spec:
                edges.append(
                    DependencyEdge(
                        source=current_package_name,
                        target=dep_name,
                        version_spec=dep_spec,
                    )
                )

    direct_names = get_javascript_direct_dependencies(lockfile_path.parent)
    dev_names = get_javascript_dev_dependencies(lockfile_path.parent)
    direct_deps: list[DependencyInfo] = []
    transitive_deps: list[DependencyInfo] = []

    direct_name_set = {name.lower() for name in direct_names}
    dev_name_set = {name.lower() for name in dev_names}

    for name_lower, (name, version) in versions_by_name.items():
        is_direct = (
            not direct_name_set and not dev_name_set
        ) or name_lower in direct_name_set
        dep_info = DependencyInfo(
            name=name,
            ecosystem="javascript",
            version=version,
            is_direct=is_direct,
            depth=0 if is_direct else 1,
        )
        if is_direct:
            direct_deps.append(dep_info)
        else:
            transitive_deps.append(dep_info)

    root_name = get_javascript_project_name(lockfile_path.parent)

    return DependencyGraph(
        root_package=root_name or "unknown",
        ecosystem="javascript",
        direct_dependencies=direct_deps,
        transitive_dependencies=transitive_deps,
        edges=edges,
    )
