"""Base types for dependency parser plugins."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, NamedTuple

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from oss_sustain_guard.dependency_graph import DependencyGraph


class DependencyParserSpec(NamedTuple):
    """Metadata for a dependency parser plugin."""

    name: str
    lockfile_names: set[str]
    parse: Callable[[str | Path], DependencyGraph | None]
