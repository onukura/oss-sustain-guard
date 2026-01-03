"""Metric registry and discovery helpers."""

from importlib import import_module
from importlib.metadata import entry_points
from warnings import warn

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)

_BUILTIN_MODULES = [
    "oss_sustain_guard.metrics.bus_factor",
    "oss_sustain_guard.metrics.maintainer_drain",
    "oss_sustain_guard.metrics.zombie_status",
    "oss_sustain_guard.metrics.merge_velocity",
    "oss_sustain_guard.metrics.issue_resolution_duration",
    "oss_sustain_guard.metrics.funding",
    "oss_sustain_guard.metrics.release_cadence",
    "oss_sustain_guard.metrics.security_posture",
    "oss_sustain_guard.metrics.attraction",
    "oss_sustain_guard.metrics.retention",
    "oss_sustain_guard.metrics.review_health",
    "oss_sustain_guard.metrics.documentation_presence",
    "oss_sustain_guard.metrics.code_of_conduct",
    "oss_sustain_guard.metrics.pr_acceptance_ratio",
    "oss_sustain_guard.metrics.organizational_diversity",
    "oss_sustain_guard.metrics.fork_activity",
    "oss_sustain_guard.metrics.project_popularity",
    "oss_sustain_guard.metrics.license_clarity",
    "oss_sustain_guard.metrics.pr_responsiveness",
    "oss_sustain_guard.metrics.community_health",
    "oss_sustain_guard.metrics.ci_status",
    "oss_sustain_guard.metrics.stale_issue_ratio",
    "oss_sustain_guard.metrics.pr_merge_speed",
    "oss_sustain_guard.metrics.single_maintainer_load",
]


def _load_builtin_metric_specs() -> list[MetricSpec]:
    specs: list[MetricSpec] = []
    for module_path in _BUILTIN_MODULES:
        module = import_module(module_path)
        metric = getattr(module, "METRIC", None)
        if metric is not None:
            specs.append(metric)
    return specs


def _load_entrypoint_metric_specs() -> list[MetricSpec]:
    specs: list[MetricSpec] = []
    for entry_point in entry_points(group="oss_sustain_guard.metrics"):
        try:
            loaded = entry_point.load()
        except Exception as exc:
            warn(
                f"Note: Unable to load metric plugin '{entry_point.name}': {exc}",
                stacklevel=2,
            )
            continue
        if isinstance(loaded, MetricSpec):
            specs.append(loaded)
            continue
        if callable(loaded):
            try:
                spec = loaded()
            except Exception as exc:
                warn(
                    "Note: Unable to initialize metric plugin "
                    f"'{entry_point.name}': {exc}",
                    stacklevel=2,
                )
                continue
            if isinstance(spec, MetricSpec):
                specs.append(spec)
    return specs


def load_metric_specs() -> list[MetricSpec]:
    """Load built-in and entrypoint metric specs.

    Built-in metrics are always loaded. Entrypoint metrics are added if they do
    not share a name with an existing built-in metric.
    """
    specs = _load_builtin_metric_specs()
    existing = {spec.name for spec in specs}

    for spec in _load_entrypoint_metric_specs():
        if spec.name in existing:
            continue
        specs.append(spec)
        existing.add(spec.name)

    return specs


__all__ = [
    "Metric",
    "MetricChecker",
    "MetricContext",
    "MetricSpec",
    "load_metric_specs",
]
