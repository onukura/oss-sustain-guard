"""pip requirements lockfile dependency parser."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_parsers.python.shared import get_python_project_name

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo


PARSER = DependencyParserSpec(
    name="pip",
    lockfile_names={"requirements.txt"},
    parse=lambda lockfile_path: parse_pip_requirements(lockfile_path),
)


def parse_pip_requirements(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse requirements.txt and extract dependency names."""
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo

    lockfile_path = Path(lockfile_path)
    if not lockfile_path.exists():
        return None

    try:
        content = lockfile_path.read_text(encoding="utf-8")
    except OSError:
        return None

    deps: list[DependencyInfo] = []
    for line in content.splitlines():
        name = _parse_requirement_name(line)
        if not name:
            continue
        deps.append(
            DependencyInfo(
                name=name,
                ecosystem="python",
                version=None,
                is_direct=True,
                depth=0,
            )
        )

    root_name = get_python_project_name(lockfile_path.parent)

    return DependencyGraph(
        root_package=root_name or "unknown",
        ecosystem="python",
        direct_dependencies=deps,
        transitive_dependencies=[],
    )


def _parse_requirement_name(line: str) -> str | None:
    """Parse a dependency name from a requirements.txt line."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("-"):
        return None

    if "#egg=" in stripped:
        return stripped.split("#egg=", 1)[1].strip()

    for delimiter in [";", "@", "==", ">=", "<=", "!=", "~=", ">", "<"]:
        if delimiter in stripped:
            stripped = stripped.split(delimiter, 1)[0].strip()
            break

    if "[" in stripped:
        stripped = stripped.split("[", 1)[0].strip()

    return stripped or None
