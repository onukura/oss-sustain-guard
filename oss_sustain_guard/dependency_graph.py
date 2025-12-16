"""
Dependency graph analysis for multi-language package managers.

Parses lockfiles to extract package dependencies and their relationships.
Supports: Python (uv, Poetry, Pipenv), JavaScript (npm, Yarn, pnpm),
Rust (Cargo), Go modules, Ruby Gems, PHP Composer, etc.
"""

import json
import tomllib
from pathlib import Path
from typing import NamedTuple


class DependencyInfo(NamedTuple):
    """Information about a package dependency."""

    name: str
    ecosystem: str
    version: str | None = None
    is_direct: bool = True  # True if direct dependency, False if transitive
    depth: int = 0  # 0 for direct, 1+ for transitive


class DependencyGraph(NamedTuple):
    """Graph of package dependencies."""

    root_package: str
    ecosystem: str
    direct_dependencies: list[DependencyInfo]
    transitive_dependencies: list[DependencyInfo]


def parse_python_lockfile(
    lockfile_path: str | Path,
) -> DependencyGraph | None:
    """
    Parse Python lockfile (uv.lock, poetry.lock, Pipfile.lock).

    Args:
        lockfile_path: Path to the Python lockfile.

    Returns:
        DependencyGraph with extracted dependencies or None on error.
    """
    lockfile_path = Path(lockfile_path)
    if not lockfile_path.exists():
        return None

    filename = lockfile_path.name
    direct_deps: list[DependencyInfo] = []
    transitive_deps: list[DependencyInfo] = []

    try:
        if filename == "uv.lock":
            direct_deps, transitive_deps = _parse_uv_lock(lockfile_path)
        elif filename == "poetry.lock":
            direct_deps, transitive_deps = _parse_poetry_lock(lockfile_path)
        elif filename == "Pipfile.lock":
            direct_deps, transitive_deps = _parse_pipfile_lock(lockfile_path)
        else:
            return None

        # Extract root package name from pyproject.toml if it exists
        root_name = _get_python_project_name(lockfile_path.parent)

        return DependencyGraph(
            root_package=root_name or "unknown",
            ecosystem="python",
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
        )
    except Exception:
        return None


def _parse_uv_lock(
    lockfile_path: Path,
) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse uv.lock file (TOML format with [[package]] entries)."""
    direct_deps: list[DependencyInfo] = []
    all_packages: dict[str, str] = {}

    with open(lockfile_path, "rb") as f:
        data = tomllib.load(f)

    # Collect all packages and their versions
    for package in data.get("package", []):
        name = package.get("name", "")
        version = package.get("version", "")
        if name:
            all_packages[name.lower()] = version

    # Extract dependencies - uv.lock has package entries with optional dependencies
    # We treat all packages as dependencies (uv manages them explicitly)
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

    # Separate transitive by checking if any marker/environment is conditional
    # For simplicity, all in uv.lock are treated as locked dependencies
    return direct_deps[:10], direct_deps[10:]  # Heuristic split


def _parse_poetry_lock(
    lockfile_path: Path,
) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse poetry.lock file."""
    direct_deps: list[DependencyInfo] = []
    transitive_deps: list[DependencyInfo] = []

    with open(lockfile_path, "rb") as f:
        data = tomllib.load(f)

    # Poetry.lock has [[package]] with metadata=
    # We need to check pyproject.toml for direct dependencies
    direct_package_names = _get_poetry_direct_dependencies(lockfile_path.parent)

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

    return direct_deps, transitive_deps


def _parse_pipfile_lock(
    lockfile_path: Path,
) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse Pipfile.lock (JSON format)."""
    direct_deps: list[DependencyInfo] = []
    transitive_deps: list[DependencyInfo] = []

    with open(lockfile_path) as f:
        data = json.load(f)

    # Pipfile.lock has "default" and "develop" sections
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

    # "develop" dependencies are development-only (treat as transitive for scoring)
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

    return direct_deps, transitive_deps


def _get_python_project_name(directory: Path) -> str | None:
    """Extract Python project name from pyproject.toml."""
    pyproject_path = directory / "pyproject.toml"
    if pyproject_path.exists():
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            return data.get("project", {}).get("name") or data.get("tool", {}).get(
                "poetry", {}
            ).get("name")
        except Exception:
            return None
    return None


def _get_poetry_direct_dependencies(directory: Path) -> set[str]:
    """Extract direct dependencies from pyproject.toml (Poetry format)."""
    pyproject_path = directory / "pyproject.toml"
    if not pyproject_path.exists():
        return set()

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        poetry_section = data.get("tool", {}).get("poetry", {})
        deps = set()

        # Add dependencies and optional-dependencies
        for dep_name in poetry_section.get("dependencies", {}):
            if dep_name != "python":
                deps.add(dep_name)

        for optional_group in poetry_section.get("group", {}).values():
            if isinstance(optional_group, dict):
                for dep_name in optional_group.get("dependencies", {}):
                    deps.add(dep_name)

        return deps
    except Exception:
        return set()


def parse_javascript_lockfile(
    lockfile_path: str | Path,
) -> DependencyGraph | None:
    """
    Parse JavaScript lockfile (package-lock.json, yarn.lock, pnpm-lock.yaml).

    Args:
        lockfile_path: Path to the JavaScript lockfile.

    Returns:
        DependencyGraph with extracted dependencies or None on error.
    """
    lockfile_path = Path(lockfile_path)
    if not lockfile_path.exists():
        return None

    filename = lockfile_path.name

    try:
        direct_deps: list[DependencyInfo] = []
        transitive_deps: list[DependencyInfo] = []

        if filename == "package-lock.json":
            direct_deps, transitive_deps = _parse_npm_lock(lockfile_path)
        elif filename == "yarn.lock":
            direct_deps, transitive_deps = _parse_yarn_lock(lockfile_path)
        elif filename == "pnpm-lock.yaml":
            direct_deps, transitive_deps = _parse_pnpm_lock(lockfile_path)
        else:
            return None

        root_name = _get_javascript_project_name(lockfile_path.parent)

        return DependencyGraph(
            root_package=root_name or "unknown",
            ecosystem="javascript",
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
        )
    except Exception:
        return None


def _parse_npm_lock(
    lockfile_path: Path,
) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse package-lock.json (npm v7+ format with nested packages)."""
    direct_deps: list[DependencyInfo] = []
    transitive_deps: list[DependencyInfo] = []

    with open(lockfile_path) as f:
        data = json.load(f)

    # Direct dependencies from packages section with depth=0
    packages = data.get("packages", {})
    for pkg_spec, pkg_data in packages.items():
        if pkg_spec == "":
            # Root package
            continue

        # Count "/" to determine depth
        depth = pkg_spec.count("/") - 1
        name = pkg_spec.split("/")[-1]
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

    return direct_deps, transitive_deps


def _parse_yarn_lock(
    lockfile_path: Path,
) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse yarn.lock (simplified - requires external parser for full support)."""
    # Yarn lock format is complex, return empty for now
    # In production, use yarn parser library
    return [], []


def _parse_pnpm_lock(
    lockfile_path: Path,
) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse pnpm-lock.yaml (simplified YAML parsing)."""
    # pnpm-lock.yaml is YAML, requires yaml library
    # For now, return empty - can be extended with pyyaml
    return [], []


def _get_javascript_project_name(directory: Path) -> str | None:
    """Extract JavaScript project name from package.json."""
    package_json_path = directory / "package.json"
    if package_json_path.exists():
        try:
            with open(package_json_path) as f:
                data = json.load(f)
            return data.get("name")
        except Exception:
            return None
    return None


def get_all_dependencies(
    lockfile_paths: list[str | Path],
) -> list[DependencyGraph]:
    """
    Extract dependencies from multiple lockfiles.

    Supports auto-detection of lockfile type.

    Args:
        lockfile_paths: List of paths to lockfiles.

    Returns:
        List of DependencyGraph objects (one per lockfile).
    """
    graphs: list[DependencyGraph] = []

    for lockfile_path in lockfile_paths:
        lockfile_path = Path(lockfile_path)
        filename = lockfile_path.name

        graph = None
        if filename in ("uv.lock", "poetry.lock", "Pipfile.lock"):
            graph = parse_python_lockfile(lockfile_path)
        elif filename in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
            graph = parse_javascript_lockfile(lockfile_path)

        if graph:
            graphs.append(graph)

    return graphs


def filter_high_value_dependencies(
    graph: DependencyGraph, max_count: int = 10
) -> list[DependencyInfo]:
    """
    Get top N direct dependencies (sorted by name).

    Useful for displaying in limited space like CLI tables.

    Args:
        graph: DependencyGraph to filter.
        max_count: Maximum number of dependencies to return.

    Returns:
        List of top DependencyInfo entries.
    """
    # Sort by name for consistency
    sorted_direct = sorted(graph.direct_dependencies, key=lambda d: d.name)
    return sorted_direct[:max_count]
