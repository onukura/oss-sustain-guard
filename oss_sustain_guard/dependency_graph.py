"""
Dependency graph analysis for multi-language package managers.

Parses lockfiles to extract package dependencies and their relationships.
Supports: Python (uv, Poetry, Pipenv), JavaScript (npm, Yarn, pnpm),
Rust (Cargo), Go modules, Ruby Gems, PHP Composer, etc.
"""

import json
import re

import yaml

try:
    import tomllib  # ty:ignore[unresolved-import]
except ImportError:  # pragma: no cover - fallback for Python < 3.11
    import tomli as tomllib
from pathlib import Path
from typing import NamedTuple

from oss_sustain_guard.repository import parse_repository_url


class DependencyInfo(NamedTuple):
    """Information about a package dependency."""

    name: str
    ecosystem: str
    version: str | None = None
    is_direct: bool = True  # True if direct dependency, False if transitive
    depth: int = 0  # 0 for direct, 1+ for transitive


class DependencyEdge(NamedTuple):
    """Edge representing a dependency relationship."""

    source: str  # Package that depends on target
    target: str  # Package being depended on
    version_spec: str | None = None  # Version specifier (e.g., ">=2.0")


class DependencyGraph(NamedTuple):
    """Graph of package dependencies."""

    root_package: str
    ecosystem: str
    direct_dependencies: list[DependencyInfo]
    transitive_dependencies: list[DependencyInfo]
    edges: list[DependencyEdge] = []  # Package dependency relationships


def parse_python_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse Python lockfile using plugin system (deprecated).

    This function is deprecated. Use get_all_dependencies() instead.
    """
    results = get_all_dependencies([lockfile_path])
    return results[0] if results else None


def parse_javascript_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse JavaScript lockfile using plugin system (deprecated).

    This function is deprecated. Use get_all_dependencies() instead.
    """
    results = get_all_dependencies([lockfile_path])
    return results[0] if results else None


def get_all_dependencies(
    lockfile_paths: list[str | Path],
) -> list[DependencyGraph]:
    """
    Extract dependencies from multiple lockfiles using plugin-based parsers.

    Automatically detects lockfile type based on filename and uses registered
    dependency parser plugins to parse each file. Supports all registered
    language ecosystems (Python, JavaScript, Rust, Go, Ruby, PHP, etc.).

    Args:
        lockfile_paths: List of paths to lockfiles.

    Returns:
        List of DependencyGraph objects (one per successfully parsed lockfile).
        Returns empty list if no lockfiles are found or parsing fails.
    """
    from oss_sustain_guard.dependency_parsers import load_dependency_parser_specs

    graphs: list[DependencyGraph] = []
    parser_specs = load_dependency_parser_specs()

    for lockfile_path in lockfile_paths:
        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            continue

        filename = lockfile_path.name
        parser = next(
            (spec for spec in parser_specs if filename in spec.lockfile_names),
            None,
        )

        if not parser:
            continue

        try:
            graph = parser.parse(lockfile_path)
            if graph:
                graphs.append(graph)
        except Exception:
            # Silently skip files that fail to parse
            continue

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
        elif filename == "mix.lock":
            return _get_mix_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "pubspec.lock":
            return _get_pubspec_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "renv.lock":
            return _get_renv_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "Package.resolved":
            return _get_spm_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "cpanfile.snapshot":
            return _get_cpanfile_snapshot_dependencies(
                lockfile_path, package_name_lower
            )
        elif filename == "cabal.project.freeze":
            return _get_cabal_project_freeze_dependencies(
                lockfile_path, package_name_lower
            )
        elif filename == "stack.yaml.lock":
            return _get_stack_lock_dependencies(lockfile_path, package_name_lower)
        elif filename == "Cargo.lock":
            return _get_cargo_package_dependencies(lockfile_path, package_name_lower)
        elif filename == "packages.lock.json":
            return _get_packages_lock_dependencies(lockfile_path, package_name_lower)
        elif filename == "go.mod":
            return _get_go_mod_dependencies(lockfile_path, package_name_lower)
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


def _get_mix_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from mix.lock."""
    content = lockfile_path.read_text(encoding="utf-8")
    entry = _find_mix_lock_entry(content, package_name_lower)
    if not entry:
        return []

    lists = _extract_bracketed_lists(entry)
    if len(lists) < 2:
        return []

    deps_list = lists[1]
    dep_names = set(re.findall(r'\{:"([^"]+)"', deps_list))
    dep_names.update(re.findall(r"\{:(\w+)", deps_list))
    return sorted(dep_names)


def _find_mix_lock_entry(content: str, package_name_lower: str) -> str | None:
    """Locate a mix.lock entry for a given package name."""
    match = re.search(
        rf'"{re.escape(package_name_lower)}"\s*:',
        content,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    start = content.find("{:hex", match.end())
    if start == -1:
        return None

    depth = 0
    for idx in range(start, len(content)):
        if content[idx] == "{":
            depth += 1
        elif content[idx] == "}":
            depth -= 1
            if depth == 0:
                return content[start : idx + 1]

    return None


def _extract_bracketed_lists(text: str) -> list[str]:
    """Extract top-level bracketed list blocks from text."""
    lists = []
    depth = 0
    start = None

    for idx, ch in enumerate(text):
        if ch == "[":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "]" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                lists.append(text[start : idx + 1])
                start = None

    return lists


def _get_pubspec_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies from pubspec.yaml when pubspec.lock is present."""
    pubspec_path = lockfile_path.with_name("pubspec.yaml")
    if not pubspec_path.exists():
        return []

    try:
        import yaml
    except ImportError:
        return []

    data = yaml.safe_load(pubspec_path.read_text(encoding="utf-8")) or {}
    project_name = data.get("name")
    if not isinstance(project_name, str):
        return []
    if project_name.lower() != package_name_lower:
        return []

    deps: set[str] = set()
    for section in ("dependencies", "dev_dependencies", "dependency_overrides"):
        section_data = data.get(section, {})
        if isinstance(section_data, dict):
            for name in section_data.keys():
                if name != "flutter":
                    deps.add(name)

    return sorted(deps)


def _get_renv_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from renv.lock."""
    with open(lockfile_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for name, info in (data.get("Packages") or {}).items():
        if not isinstance(info, dict) or name.lower() != package_name_lower:
            continue

        deps: set[str] = set()
        for key in ("Requirements", "Dependencies", "Depends", "Imports", "LinkingTo"):
            value = info.get(key)
            if isinstance(value, list):
                deps.update(value)
            elif isinstance(value, str):
                deps.update(_split_r_dependency_list(value))
        deps.discard("R")
        return sorted(dep for dep in deps if dep)

    return []


def _split_r_dependency_list(value: str) -> list[str]:
    """Split an R dependency string into package names."""
    deps = []
    for entry in value.split(","):
        name = entry.strip().split("(")[0].strip()
        if name:
            deps.append(name)
    return deps


def _get_spm_package_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a Swift package from Package.swift."""
    manifest_path = lockfile_path.with_name("Package.swift")
    if not manifest_path.exists():
        return []

    try:
        content = manifest_path.read_text(encoding="utf-8")
    except OSError:
        return []

    package_name = _extract_swift_package_name(content)
    if not package_name or package_name.lower() != package_name_lower:
        return []

    deps = []
    for url in _extract_swift_package_urls(content):
        repo = parse_repository_url(url)
        deps.append(f"{repo.owner}/{repo.name}" if repo else url)
    return deps


def _extract_swift_package_name(content: str) -> str | None:
    """Extract the top-level package name from a Package.swift manifest."""
    match = re.search(
        r"Package\s*\(\s*name\s*:\s*[\"']([^\"']+)[\"']",
        content,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return None


def _extract_swift_package_urls(content: str) -> list[str]:
    """Extract dependency URLs from a Package.swift manifest."""
    pattern = re.compile(r"\.package\s*\(\s*url\s*:\s*[\"']([^\"']+)[\"']")
    return pattern.findall(content)


def _get_cpanfile_snapshot_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from cpanfile.snapshot."""
    content = lockfile_path.read_text(encoding="utf-8")
    deps_by_package: dict[str, set[str]] = {}
    current_name = None
    in_requires = False
    requires_indent: int | None = None
    in_distributions = False

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if stripped == "DISTRIBUTIONS":
            in_distributions = True
            current_name = None
            in_requires = False
            requires_indent = None
            continue

        if not in_distributions:
            continue

        if stripped.startswith("distribution:"):
            current_name = _strip_distribution_version(
                stripped.split("distribution:", 1)[1].strip()
            ).lower()
            deps_by_package.setdefault(current_name, set())
            in_requires = False
            requires_indent = None
            continue

        if stripped.startswith("requires:") or stripped.startswith("requirements:"):
            if current_name:
                in_requires = True
                requires_indent = len(line) - len(line.lstrip(" "))
            continue

        if in_requires:
            indent = len(line) - len(line.lstrip(" "))
            if requires_indent is None or indent <= requires_indent:
                in_requires = False
                requires_indent = None
                continue
            if ": " in stripped:
                dep_name = stripped.split(": ", 1)[0].strip()
            else:
                dep_name = stripped.split(None, 1)[0].strip()
            if dep_name and current_name:
                deps_by_package.setdefault(current_name, set()).add(dep_name)

    return sorted(deps_by_package.get(package_name_lower, []))


def _get_cabal_project_freeze_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from cabal.project.freeze."""
    content = lockfile_path.read_text(encoding="utf-8")
    constraints_text = _extract_cabal_constraints(content)
    deps = _parse_cabal_constraint_packages(constraints_text)
    project_name = _get_haskell_project_name(lockfile_path.parent)
    if project_name and project_name.lower() != package_name_lower:
        return []
    return deps


def _extract_cabal_constraints(content: str) -> str:
    """Extract the constraints block from a cabal.project.freeze file."""
    lines = content.splitlines()
    buffer = []
    in_constraints = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("constraints:"):
            in_constraints = True
            buffer.append(stripped.split("constraints:", 1)[1])
            continue
        if in_constraints:
            if line.startswith(" ") or line.startswith("\t"):
                buffer.append(stripped)
            else:
                break
    return " ".join(buffer)


def _parse_cabal_constraint_packages(text: str) -> list[str]:
    """Parse cabal constraint packages from a constraints string."""
    deps: set[str] = set()
    for part in text.split(","):
        chunk = part.strip()
        if not chunk:
            continue
        if chunk.startswith("any."):
            chunk = chunk[4:]
        name = re.split(r"[<>=\s]", chunk, maxsplit=1)[0]
        if name:
            deps.add(name)
    return sorted(deps)


def _get_stack_lock_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies from stack.yaml.lock."""
    try:
        import yaml
    except ImportError:
        return []

    data = yaml.safe_load(lockfile_path.read_text(encoding="utf-8")) or {}
    packages = data.get("packages", [])
    deps = _extract_stack_packages(packages)
    project_name = _get_haskell_project_name(lockfile_path.parent)
    if project_name and project_name.lower() != package_name_lower:
        return []
    return deps


def _extract_stack_packages(packages: object) -> list[str]:
    """Extract package names from stack.yaml.lock packages entries."""
    deps: set[str] = set()
    if isinstance(packages, list):
        for entry in packages:
            if isinstance(entry, str):
                dep_name = _strip_stack_package_name(entry)
                if dep_name:
                    deps.add(dep_name)
            elif isinstance(entry, dict):
                for key in ("original", "hackage", "git", "archive"):
                    value = entry.get(key)  # ty:ignore[invalid-argument-type]
                    if isinstance(value, str):
                        dep_name = _strip_stack_package_name(value)
                        if dep_name:
                            deps.add(dep_name)
    return sorted(dep for dep in deps if dep)


def _strip_stack_package_name(value: str) -> str:
    """Strip version information from stack package identifiers."""
    cleaned = value.strip()
    if ":" in cleaned:
        prefix, rest = cleaned.split(":", 1)
        if prefix.strip() in {"hackage", "git", "archive"}:
            cleaned = rest.strip()
    cleaned = cleaned.split(" ", 1)[0].split("@", 1)[0]
    match = re.match(r"^(?P<name>.+)-\d", cleaned)
    if match:
        return match.group("name")
    return cleaned


def _get_packages_lock_dependencies(
    lockfile_path: Path, package_name_lower: str
) -> list[str]:
    """Extract dependencies for a package from packages.lock.json."""
    with open(lockfile_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    deps: set[str] = set()
    dependencies = data.get("dependencies", {})
    for _framework, packages_dict in dependencies.items():
        if not isinstance(packages_dict, dict):
            continue
        for name, pkg_data in packages_dict.items():
            if name.lower() != package_name_lower:
                continue
            if isinstance(pkg_data, dict):
                package_deps = pkg_data.get("dependencies", {})
                if isinstance(package_deps, dict):
                    deps.update(package_deps.keys())
    return sorted(deps)


def _get_go_mod_dependencies(lockfile_path: Path, package_name_lower: str) -> list[str]:
    """Extract dependencies for a module from go.mod."""
    module_name, dependencies = _parse_go_mod_dependencies(lockfile_path)
    if module_name and module_name.lower() == package_name_lower:
        return dependencies
    return []


def _parse_go_mod_dependencies(lockfile_path: Path) -> tuple[str | None, list[str]]:
    """Parse go.mod for module name and dependencies."""
    module_name = None
    dependencies: list[str] = []
    in_require = False

    for line in lockfile_path.read_text(encoding="utf-8").splitlines():
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

    return module_name, dependencies


def _get_haskell_project_name(directory: Path) -> str | None:
    """Extract a Haskell project name from package.yaml or .cabal file."""
    package_yaml = directory / "package.yaml"
    if package_yaml.exists():
        try:
            import yaml as yaml_module

            data = yaml_module.safe_load(package_yaml.read_text(encoding="utf-8")) or {}
            name = data.get("name")
            if isinstance(name, str):
                return name
        except ImportError:
            pass

    cabal_files = list(directory.glob("*.cabal"))
    if cabal_files:
        try:
            content = cabal_files[0].read_text(encoding="utf-8")
        except OSError:
            return None
        for line in content.splitlines():
            if line.lower().startswith("name:"):
                return line.split(":", 1)[1].strip()
    return None


def _strip_distribution_version(name: str) -> str:
    """Strip version suffix from CPAN distribution names."""
    match = re.match(r"^(?P<base>.+)-\d", name)
    if match:
        return match.group("base")
    return name


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

    module_name, dependencies = _parse_go_mod_dependencies(go_mod_path)
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
