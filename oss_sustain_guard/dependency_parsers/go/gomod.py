"""Go module dependency parser."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import DependencyGraph


PARSER = DependencyParserSpec(
    name="gomod",
    lockfile_names={"go.mod", "go.sum"},
    parse=lambda lockfile_path: parse_go_modules(lockfile_path),
)


def parse_go_modules(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse go.mod or go.sum file."""
    from oss_sustain_guard.dependency_graph import (
        DependencyEdge,
        DependencyGraph,
        DependencyInfo,
    )

    lockfile_path = Path(lockfile_path)
    lockfile_name = lockfile_path.name

    # Try go.sum if go.mod doesn't exist
    if lockfile_name == "go.mod" or lockfile_name not in ("go.mod", "go.sum"):
        go_mod = lockfile_path.parent / "go.mod"
        if go_mod.exists():
            lockfile_path = go_mod
        else:
            go_sum = lockfile_path.parent / "go.sum"
            if go_sum.exists():
                lockfile_path = go_sum

    if not lockfile_path.exists():
        return None

    try:
        content = lockfile_path.read_text(encoding="utf-8")
    except OSError:
        return None

    direct_deps: list[DependencyInfo] = []
    transitive_deps: list[DependencyInfo] = []
    edges: list[DependencyEdge] = []
    root_name = None
    in_require = False

    for line in content.splitlines():
        line = line.strip()

        # Extract module name from "module github.com/user/project"
        if line.startswith("module "):
            root_name = line.split(" ", 1)[1].strip()
            continue

        # Parse require block
        if line == "require (":
            in_require = True
            continue
        elif line == ")" and in_require:
            in_require = False
            continue

        # Parse individual requires
        if (in_require or line.startswith("require ")) and line:
            if line.startswith("require "):
                require_line = line[8:].strip()
            else:
                require_line = line

            parts = require_line.split()
            if len(parts) >= 2:
                pkg_name = parts[0]
                version = parts[1]

                is_direct = True  # go.mod only lists direct deps
                dep_info = DependencyInfo(
                    name=pkg_name,
                    ecosystem="go",
                    version=version,
                    is_direct=is_direct,
                    depth=0,
                )
                direct_deps.append(dep_info)

    return DependencyGraph(
        root_package=root_name or "unknown",
        ecosystem="go",
        direct_dependencies=direct_deps,
        transitive_dependencies=transitive_deps,
        edges=edges,
    )
