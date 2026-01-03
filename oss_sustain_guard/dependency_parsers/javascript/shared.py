"""Shared helpers for JavaScript lockfile parsers."""

from __future__ import annotations

import json
from pathlib import Path


def get_javascript_project_name(directory: Path) -> str | None:
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


def get_javascript_direct_dependencies(directory: Path) -> set[str]:
    """Extract direct dependencies from package.json."""
    package_json_path = directory / "package.json"
    if not package_json_path.exists():
        return set()

    try:
        with open(package_json_path) as f:
            data = json.load(f)
    except Exception:
        return set()

    direct_names: set[str] = set()
    for section in ("dependencies", "optionalDependencies", "peerDependencies"):
        deps = data.get(section, {})
        if isinstance(deps, dict):
            direct_names.update(deps.keys())
    return direct_names


def get_javascript_dev_dependencies(directory: Path) -> set[str]:
    """Extract development dependencies from package.json."""
    package_json_path = directory / "package.json"
    if not package_json_path.exists():
        return set()

    try:
        with open(package_json_path) as f:
            data = json.load(f)
    except Exception:
        return set()

    deps = data.get("devDependencies", {})
    if isinstance(deps, dict):
        return set(deps.keys())
    return set()


def extract_npm_path_info(path: str) -> tuple[str | None, int]:
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


def extract_yarn_package_name(descriptor: str) -> str | None:
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


def extract_pnpm_package_name(package_key: str) -> str | None:
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


def extract_pnpm_package_version(package_key: str) -> str | None:
    """Extract version from a pnpm-lock package key."""
    if not package_key:
        return None
    trimmed = package_key.lstrip("/")
    if not trimmed:
        return None
    trimmed = trimmed.split("(", 1)[0]
    if "@" not in trimmed:
        return None
    return trimmed.rsplit("@", 1)[1] or None


def collect_pnpm_dependency_versions(
    dependencies: dict[str, object],
    versions_by_name: dict[str, tuple[str, str | None]],
) -> None:
    """Collect pnpm dependency versions into a mapping."""
    for name, value in dependencies.items():
        version: str | None = None
        if isinstance(value, str):
            version = value
        elif isinstance(value, dict):
            version_data = value.get("version")
            if isinstance(version_data, str):
                version = version_data
        versions_by_name.setdefault(name.lower(), (name, version))
