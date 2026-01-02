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

        name, depth = _extract_npm_path_info(pkg_spec)
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


def get_package_dependencies(lockfile_path: str | Path, package_name: str) -> list[str]:
    """
    Extract dependencies for a specific package from a lockfile.

    Args:
        lockfile_path: Path to the lockfile.
        package_name: Name of the package to get dependencies for.

    Returns:
        List of dependency package names.
    """
    lockfile_path = Path(lockfile_path)
    if not lockfile_path.exists():
        return []

    filename = lockfile_path.name
    package_name_lower = package_name.lower()

    try:
        if filename == "uv.lock":
            return _get_uv_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "poetry.lock":
            return _get_poetry_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "Pipfile.lock":
            return _get_pipfile_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "package-lock.json":
            return _get_npm_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "yarn.lock":
            return _get_yarn_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "pnpm-lock.yaml":
            return _get_pnpm_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "Cargo.lock":
            return _get_cargo_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "Gemfile.lock":
            return _get_gemfile_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "composer.lock":
            return _get_composer_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "go.sum":
            return _get_go_package_dependencies(lockfile_path, package_name_lower)
        else:
            return []
    except Exception:
        return []


def _get_uv_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from uv.lock."""
    with open(lockfile_path, "rb") as f:
        data = tomllib.load(f)

    for package in data.get("package", []):
        name = package.get("name", "")
        if name.lower() == package_name_lower:
            dependencies = package.get("dependencies", [])
            dep_names = []
            for dep in dependencies:
                if isinstance(dep, dict):
                    dep_name = dep.get("name", "")
                    if dep_name:
                        dep_names.append(dep_name)
                elif isinstance(dep, str):
                    dep_names.append(dep)
            return dep_names
    return []


def _get_poetry_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from poetry.lock."""
    with open(lockfile_path, "rb") as f:
        data = tomllib.load(f)

    for package in data.get("package", []):
        name = package.get("name", "")
        if name.lower() == package_name_lower:
            dependencies = package.get("dependencies", {})
            if isinstance(dependencies, dict):
                return list(dependencies.keys())
            return []
    return []


def _get_pipfile_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from Pipfile.lock."""
    with open(lockfile_path) as f:
        data = json.load(f)

    # Check both default and develop sections
    for section in ["default", "develop"]:
        packages = data.get(section, {})
        for pkg_name, _pkg_data in packages.items():
            if pkg_name.lower() == package_name_lower:
                # Pipfile.lock doesn't store per-package dependencies
                # Return empty list as it's flat
                return []
    return []


def _get_npm_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from package-lock.json."""
    with open(lockfile_path) as f:
        data = json.load(f)

    # npm v7+ uses "packages" with paths
    packages = data.get("packages", {})
    for path, pkg_data in packages.items():
        name = pkg_data.get("name", "")
        if not name and path:
            name, _depth = _extract_npm_path_info(path)

        if name and name.lower() == package_name_lower:
            dependencies = pkg_data.get("dependencies", {})
            if isinstance(dependencies, dict):
                return list(dependencies.keys())
            return []
    return []


def _get_yarn_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from yarn.lock."""
    content = lockfile_path.read_text(encoding="utf-8")
    deps_by_package: dict[str, set[str]] = {}
    current_packages: list[str] = []
    in_dependencies = False

    for line in content.splitlines():
        if not line.strip():
            current_packages = []
            in_dependencies = False
            continue

        if not line.startswith(" ") and line.endswith(":"):
            header = line.rstrip(":")
            descriptors = [part.strip() for part in header.split(",")]
            current_packages = []
            for descriptor in descriptors:
                name = _extract_yarn_package_name(descriptor)
                if not name:
                    continue
                name_key = name.lower()
                current_packages.append(name_key)
                deps_by_package.setdefault(name_key, set())
            in_dependencies = False
            continue

        stripped = line.strip()
        if stripped == "dependencies:":
            in_dependencies = True
            continue

        if in_dependencies:
            if line.startswith("    "):
                dep_name = stripped.split(" ", 1)[0].strip('"')
                for pkg_name in current_packages:
                    deps_by_package[pkg_name].add(dep_name)
            else:
                in_dependencies = False

    return sorted(deps_by_package.get(package_name_lower, []))


def _extract_yarn_package_name(descriptor: str) -> str | None:
    """Extract package name from a yarn.lock descriptor."""
    cleaned = descriptor.strip().strip('"').strip("'")
    if not cleaned:
        return None

    if cleaned.startswith("@"):
        at_index = cleaned.find("@", 1)
        if at_index == -1:
            return cleaned
        return cleaned[:at_index]

    return cleaned.split("@", 1)[0]


def _get_pnpm_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from pnpm-lock.yaml."""
    try:
        import yaml
    except ImportError:
        return []

    with open(lockfile_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    packages = data.get("packages", {})
    deps: set[str] = set()

    for key, pkg_data in packages.items():
        name = _extract_pnpm_package_name(str(key))
        if not name or name.lower() != package_name_lower:
            continue

        for section in ("dependencies", "optionalDependencies", "peerDependencies"):
            section_data = pkg_data.get(section, {})
            if isinstance(section_data, dict):
                deps.update(section_data.keys())

    return sorted(deps)


def _extract_pnpm_package_name(package_key: str) -> str | None:
    """Extract package name from pnpm-lock package key."""
    if not package_key:
        return None

    trimmed = package_key.lstrip("/")
    if not trimmed:
        return None

    parts = trimmed.split("/")
    if not parts:
        return None

    if parts[0].startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def _get_cargo_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from Cargo.lock."""
    with open(lockfile_path, "rb") as f:
        data = tomllib.load(f)

    for package in data.get("package", []):
        name = package.get("name", "")
        if name.lower() != package_name_lower:
            continue
        dependencies = package.get("dependencies", [])
        dep_names = []
        for dep in dependencies:
            if isinstance(dep, str):
                dep_name = dep.split(" ", 1)[0]
                if dep_name:
                    dep_names.append(dep_name)
        return dep_names
    return []


def _get_gemfile_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from Gemfile.lock."""
    content = lockfile_path.read_text(encoding="utf-8")
    deps_by_package: dict[str, set[str]] = {}
    current_pkg: str | None = None
    in_specs = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "specs:":
            in_specs = True
            continue

        if in_specs and line and not line.startswith(" "):
            in_specs = False
            current_pkg = None

        if not in_specs:
            continue

        if line.startswith("    ") and not line.startswith("      ") and "(" in line:
            name = line.strip().split(" (", 1)[0]
            current_pkg = name.lower()
            deps_by_package.setdefault(current_pkg, set())
            continue

        if current_pkg and line.startswith("      "):
            dep_name = stripped.split(" ", 1)[0]
            deps_by_package[current_pkg].add(dep_name)

    return sorted(deps_by_package.get(package_name_lower, []))


def _get_composer_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from composer.lock."""
    with open(lockfile_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for pkg in data.get("packages", []):
        name = pkg.get("name", "")
        if name.lower() != package_name_lower:
            continue

        deps: dict[str, object] = {}
        for section in ("require", "require-dev"):
            section_data = pkg.get(section, {})
            if isinstance(section_data, dict):
                deps.update(section_data)

        dep_names = [
            dep
            for dep in deps.keys()
            if dep != "php"
            and not dep.startswith("ext-")
            and not dep.startswith("lib-")
        ]
        return dep_names
    return []


def _get_go_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a module from go.mod when go.sum is present."""
    go_mod_path = lockfile_path.with_name("go.mod")
    if not go_mod_path.exists():
        return []

    module_name = None
    dependencies: list[str] = []
    in_require = False

    for line in go_mod_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("module "):
            module_name = stripped.split(" ", 1)[1].strip()
            continue

        if stripped == "require (":
            in_require = True
            continue

        if in_require and stripped == ")":
            in_require = False
            continue

        if in_require:
            if stripped and not stripped.startswith("//"):
                parts = stripped.split()
                if parts:
                    dependencies.append(parts[0])
            continue

        if stripped.startswith("require ") and "(" not in stripped:
            parts = stripped.replace("require ", "").split()
            if parts:
                dependencies.append(parts[0])

    if module_name and module_name.lower() == package_name_lower:
        return dependencies
    return []


def _extract_npm_path_info(path: str) -> tuple[str | None, int]:
    """Extract npm package name and depth from a package-lock path."""
    if not path:
        return None, 0

    parts = path.split("/")
    node_modules_indices = [
        idx for idx, part in enumerate(parts) if part == "node_modules"
    ]
    if not node_modules_indices:
        return None, 0

    last_index = node_modules_indices[-1]
    name_parts = parts[last_index + 1 :]
    if not name_parts:
        return None, 0

    if name_parts[0].startswith("@") and len(name_parts) >= 2:
        name = "/".join(name_parts[:2])
    else:
        name = name_parts[0]

    depth = len(node_modules_indices) - 1
    return name, depth
