"""Bun lockfile dependency parser."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_parsers.javascript.shared import (
    get_javascript_project_name,
)

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo


PARSER = DependencyParserSpec(
    name="bun",
    lockfile_names={"bun.lock", "bun.lockb"},
    parse=lambda lockfile_path: parse_bun_lockfile(lockfile_path),
)


def parse_bun_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse bun.lock (JSON format) and extract dependencies.

    Bun lockfiles can be in text (bun.lock) or binary (bun.lockb) format.
    This parser handles the text JSON format.
    """
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo

    lockfile_path = Path(lockfile_path)
    if not lockfile_path.exists():
        return None

    # Handle binary lockb format by delegating to bun
    if lockfile_path.name == "bun.lockb":
        return _parse_bun_lockb(lockfile_path)

    # Handle text bun.lock format
    try:
        with open(lockfile_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    direct_deps: list[DependencyInfo] = []
    transitive_deps: list[DependencyInfo] = []

    # bun.lock stores packages under "packages" with scoped format
    packages = data.get("packages", {})
    direct_deps_set = _get_bun_direct_dependencies(lockfile_path.parent)

    for _pkg_key, pkg_info in packages.items():
        if not isinstance(pkg_info, dict):
            continue

        # Extract package name and version
        name = pkg_info.get("name")
        version = pkg_info.get("version")

        if not name:
            continue

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

    root_name = get_javascript_project_name(lockfile_path.parent)

    return DependencyGraph(
        root_package=root_name or "unknown",
        ecosystem="javascript",
        direct_dependencies=direct_deps,
        transitive_dependencies=transitive_deps,
    )


def _parse_bun_lockb(lockfile_path: Path) -> DependencyGraph | None:
    """Parse binary bun.lockb format.

    Note: Full binary parsing would require bun binary or bun library.
    For now, we attempt JSON fallback if available.
    """
    # bun.lockb is binary, try to use bun CLI if available
    import subprocess

    try:
        # Try to use bun to export lockfile as JSON
        result = subprocess.run(
            ["bun", "pm", "ls", "--format", "json"],
            cwd=lockfile_path.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            import json

            data = json.loads(result.stdout)
            # Recursively parse the JSON output
            return _parse_bun_json_output(lockfile_path, data)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    return None


def _parse_bun_json_output(lockfile_path: Path, data: dict) -> DependencyGraph | None:
    """Parse JSON output from bun pm ls."""
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo

    direct_deps: list[DependencyInfo] = []
    direct_deps_set = _get_bun_direct_dependencies(lockfile_path.parent)

    # bun pm ls output contains dependencies under various keys
    for key in ["dependencies", "packages"]:
        deps = data.get(key, {})
        if not isinstance(deps, dict):
            continue

        for name, info in deps.items():
            if not isinstance(info, dict):
                continue

            version = info.get("version") or info.get("resolved", "").split("@")[-1]

            dep_info = DependencyInfo(
                name=name,
                ecosystem="javascript",
                version=version,
                is_direct=name in direct_deps_set,
                depth=0,
            )
            direct_deps.append(dep_info)

    root_name = get_javascript_project_name(lockfile_path.parent)

    return DependencyGraph(
        root_package=root_name or "unknown",
        ecosystem="javascript",
        direct_dependencies=direct_deps,
        transitive_dependencies=[],
    )


def _get_bun_direct_dependencies(directory: Path) -> set[str]:
    """Extract direct dependencies from package.json (same as npm/yarn)."""
    from oss_sustain_guard.dependency_parsers.javascript.shared import (
        get_javascript_dev_dependencies,
        get_javascript_direct_dependencies,
    )

    direct = get_javascript_direct_dependencies(directory)
    dev = get_javascript_dev_dependencies(directory)
    return direct | dev
