"""uv lockfile dependency parser."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from oss_sustain_guard.dependency_graph import tomllib
from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_parsers.python.shared import get_python_project_name

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo


PARSER = DependencyParserSpec(
    name="uv",
    lockfile_names={"uv.lock"},
    parse=lambda lockfile_path: parse_uv_lockfile(lockfile_path),
)


def parse_uv_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse uv.lock file (TOML format with [[package]] entries)."""
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo

    lockfile_path = Path(lockfile_path)
    if not lockfile_path.exists():
        return None

    try:
        with open(lockfile_path, "rb") as f:
            data = tomllib.load(f)
    except OSError:
        return None

    direct_deps: list[DependencyInfo] = []
    all_packages: dict[str, str] = {}

    for package in data.get("package", []):
        name = package.get("name", "")
        version = package.get("version", "")
        if name:
            all_packages[name.lower()] = version

    seen = set()
    for package in data.get("package", []):
        name = package.get("name", "")
        if name and name.lower() not in seen:
            version = package.get("version", "")
            direct_deps.append(
                DependencyInfo(
                    name=name,
                    ecosystem="python",
                    version=version,
                    is_direct=True,
                    depth=0,
                )
            )
            seen.add(name.lower())

    root_name = get_python_project_name(lockfile_path.parent)

    return DependencyGraph(
        root_package=root_name or "unknown",
        ecosystem="python",
        direct_dependencies=direct_deps[:10],
        transitive_dependencies=direct_deps[10:],
    )
