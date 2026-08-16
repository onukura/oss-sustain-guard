"""pnpm lockfile dependency parser."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_parsers.javascript.shared import (
    collect_pnpm_dependency_versions,
    extract_pnpm_package_name,
    extract_pnpm_package_version,
    get_javascript_dev_dependencies,
    get_javascript_direct_dependencies,
    get_javascript_project_name,
)

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import (
        DependencyEdge,
        DependencyGraph,
        DependencyInfo,
    )


PARSER = DependencyParserSpec(
    name="pnpm",
    lockfile_names={"pnpm-lock.yaml"},
    parse=lambda lockfile_path: parse_pnpm_lockfile(lockfile_path),
)


def parse_pnpm_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse pnpm-lock.yaml (supports importer and packages sections)."""
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo

    lockfile_path = Path(lockfile_path)
    if not lockfile_path.exists():
        return None

    try:
        data = yaml.safe_load(lockfile_path.read_text(encoding="utf-8")) or {}
    except OSError:
        return None

    if not isinstance(data, dict):
        return None

    direct_names = get_javascript_direct_dependencies(lockfile_path.parent)
    dev_names = get_javascript_dev_dependencies(lockfile_path.parent)
    versions_by_name: dict[str, tuple[str, str | None]] = {}

    dependencies = data.get("dependencies", {})
    if isinstance(dependencies, dict):
        collect_pnpm_dependency_versions(dependencies, versions_by_name)

    optional_dependencies = data.get("optionalDependencies", {})
    if isinstance(optional_dependencies, dict):
        collect_pnpm_dependency_versions(optional_dependencies, versions_by_name)

    dev_dependencies = data.get("devDependencies", {})
    if isinstance(dev_dependencies, dict):
        collect_pnpm_dependency_versions(dev_dependencies, versions_by_name)

    importers = data.get("importers", {})
    importer_direct: set[str] = set()
    importer_dev: set[str] = set()
    if isinstance(importers, dict):
        for importer in importers.values():
            if not isinstance(importer, dict):
                continue
            for section in (
                "dependencies",
                "optionalDependencies",
                "peerDependencies",
                "devDependencies",
            ):
                section_data = importer.get(section, {})
                if isinstance(section_data, dict):
                    collect_pnpm_dependency_versions(section_data, versions_by_name)
                    target_set = (
                        importer_dev
                        if section == "devDependencies"
                        else importer_direct
                    )
                    target_set.update(section_data.keys())

    packages_section = data.get("packages", {})
    if isinstance(packages_section, dict):
        for key in packages_section.keys():
            name = extract_pnpm_package_name(str(key))
            if not name:
                continue
            version = extract_pnpm_package_version(str(key))
            versions_by_name.setdefault(name.lower(), (name, version))

    direct_deps: list[DependencyInfo] = []
    transitive_deps: list[DependencyInfo] = []
    direct_name_set = {name.lower() for name in direct_names}
    dev_name_set = {name.lower() for name in dev_names}
    if not direct_name_set and importer_direct:
        direct_name_set = {name.lower() for name in importer_direct}
    if not dev_name_set and importer_dev:
        dev_name_set = {name.lower() for name in importer_dev}

    for name_lower, (name, version) in versions_by_name.items():
        if not direct_name_set and not dev_name_set:
            is_direct = True
        else:
            is_direct = name_lower in direct_name_set
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

    # Extract dependency edges from packages section
    from oss_sustain_guard.dependency_graph import DependencyEdge

    edges: list[DependencyEdge] = []
    packages_section = data.get("packages", {})
    if isinstance(packages_section, dict):
        for pkg_key, pkg_data in packages_section.items():
            if not isinstance(pkg_data, dict):
                continue

            # Extract source package name from key
            source_name = extract_pnpm_package_name(str(pkg_key))
            if not source_name:
                continue

            # Get dependencies from package data
            deps = pkg_data.get("dependencies", {})
            if isinstance(deps, dict):
                for dep_name, dep_version in deps.items():
                    # dep_version format: "1.2.3" or path reference
                    version_spec = str(dep_version) if dep_version else None
                    edges.append(
                        DependencyEdge(
                            source=source_name,
                            target=dep_name,
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
