"""Helpers for resolver-backed dependency parser specs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.resolvers import get_resolver

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo
    from oss_sustain_guard.resolvers.base import PackageInfo


def make_resolver_parser(
    name: str, ecosystem: str, lockfile_names: set[str]
) -> DependencyParserSpec:
    """Build a resolver-backed dependency parser spec."""

    def _parse(lockfile_path: str | Path) -> DependencyGraph | None:
        import asyncio

        from oss_sustain_guard.dependency_graph import DependencyGraph

        lockfile = Path(lockfile_path)
        if lockfile.name not in lockfile_names:
            return None

        if not lockfile.exists():
            return None

        resolver = get_resolver(ecosystem)
        if not resolver:
            return None

        # Check if resolver supports parse_lockfile
        if not hasattr(resolver, "parse_lockfile"):
            return None

        try:
            # Handle both sync and async parse_lockfile
            result = resolver.parse_lockfile(str(lockfile))
            if asyncio.iscoroutine(result):  # async result
                packages = asyncio.run(result)
            else:
                packages = result

            if not packages:
                return None

            direct_deps = [_to_dependency_info(pkg) for pkg in packages]

            return DependencyGraph(
                root_package="unknown",
                ecosystem=ecosystem,
                direct_dependencies=direct_deps,
                transitive_dependencies=[],
            )
        except (FileNotFoundError, ValueError, Exception):
            # Gracefully handle parsing errors
            return None

    return DependencyParserSpec(
        name=name,
        lockfile_names=lockfile_names,
        parse=_parse,
    )


def _to_dependency_info(pkg: PackageInfo) -> DependencyInfo:
    from oss_sustain_guard.dependency_graph import DependencyInfo

    return DependencyInfo(
        name=pkg.name,
        ecosystem=pkg.ecosystem,
        version=pkg.version,
        is_direct=True,
        depth=0,
    )
