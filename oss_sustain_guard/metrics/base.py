"""
Shared metric types and context helpers.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, NamedTuple

from oss_sustain_guard.vcs.base import VCSRepositoryData


class Metric(NamedTuple):
    """A single sustainability metric."""

    name: str
    score: int
    max_score: int
    message: str
    risk: str  # "Critical", "High", "Medium", "Low", "None"
    metadata: dict[str, Any] | None = None  # Structured data independent of message


class MetricContext(NamedTuple):
    """Context provided to metric checks."""

    owner: str
    name: str
    repo_url: str
    platform: str | None = None
    package_name: str | None = None


class MetricChecker(ABC):
    """VCS-agnostic metric checker base class."""

    @abstractmethod
    def check(
        self, vcs_data: VCSRepositoryData, context: MetricContext
    ) -> Metric | None:
        """Check metric using normalized VCS data."""
        pass


class MetricSpec(NamedTuple):
    """Specification for a metric check."""

    name: str
    checker: Callable[[dict[str, Any], MetricContext], Metric | None] | MetricChecker
    on_error: Callable[[Exception], Metric] | None = None
    error_log: str | None = None
