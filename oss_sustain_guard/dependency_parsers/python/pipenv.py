"""pipenv lockfile dependency parser."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_parsers.python.shared import get_python_project_name

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo


PARSER = DependencyParserSpec(
    name="pipenv",
    lockfile_names={"Pipfile.lock"},
    parse=lambda lockfile_path: parse_pipenv_lockfile(lockfile_path),
)


def parse_pipenv_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse Pipfile.lock (JSON format)."""
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo

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

    for package_name, package_data in data.get("default", {}).items():
        version = package_data.get("version", "").lstrip("=")
        direct_deps.append(
            DependencyInfo(
                name=package_name,
                ecosystem="python",
                version=version if version else None,
                is_direct=True,
                depth=0,
            )
        )

    for package_name, package_data in data.get("develop", {}).items():
        version = package_data.get("version", "").lstrip("=")
        transitive_deps.append(
            DependencyInfo(
                name=package_name,
                ecosystem="python",
                version=version if version else None,
                is_direct=False,
                depth=1,
            )
        )

    root_name = get_python_project_name(lockfile_path.parent)

    return DependencyGraph(
        root_package=root_name or "unknown",
        ecosystem="python",
        direct_dependencies=direct_deps,
        transitive_dependencies=transitive_deps,
    )
