"""
Shared metric types and context helpers.
"""

from typing import Any, Callable, NamedTuple


class Metric(NamedTuple):
    """A single sustainability metric."""

    name: str
    score: int
    max_score: int
    message: str
    risk: str  # "Critical", "High", "Medium", "Low", "None"


class MetricContext(NamedTuple):
    """Context provided to metric checks."""

    owner: str
    name: str
    repo_url: str
    platform: str | None = None
    package_name: str | None = None


class MetricSpec(NamedTuple):
    """Specification for a metric check."""

    name: str
    checker: Callable[[dict[str, Any], MetricContext], Metric | None]
    on_error: Callable[[Exception], Metric] | None = None
    error_log: str | None = None
