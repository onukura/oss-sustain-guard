"""Shared helpers for Python lockfile parsers."""

from __future__ import annotations

from pathlib import Path

from oss_sustain_guard.dependency_graph import tomllib


def get_python_project_name(directory: Path) -> str | None:
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


def get_poetry_direct_dependencies(directory: Path) -> set[str]:
    """Extract direct dependencies from pyproject.toml (Poetry format)."""
    pyproject_path = directory / "pyproject.toml"
    if not pyproject_path.exists():
        return set()

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        poetry_section = data.get("tool", {}).get("poetry", {})
        deps = set()

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
