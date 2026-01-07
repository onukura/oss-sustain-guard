"""Helper functions for CLI commands."""

import asyncio
from functools import wraps
from pathlib import Path
from typing import Any

import typer

from oss_sustain_guard.cache import load_cache
from oss_sustain_guard.config import (
    is_cache_enabled,
    load_profile_config,
)
from oss_sustain_guard.core import (
    AnalysisResult,
    Metric,
    MetricModel,
    apply_profile_overrides,
)
from oss_sustain_guard.resolvers import get_all_resolvers

from .constants import ANALYSIS_VERSION, console


def syncify(f):
    """Decorator to run async functions synchronously."""
    return wraps(f)(lambda *args, **kwargs: asyncio.run(f(*args, **kwargs)))


def apply_scoring_profiles(profile_file: Path | None) -> None:
    """Apply scoring profile overrides from configuration."""
    try:
        profile_overrides = load_profile_config(profile_file)
        apply_profile_overrides(profile_overrides)
    except ValueError as exc:
        console.print(f"[yellow]⚠️  {exc}[/yellow]")
        raise typer.Exit(code=1) from exc


def load_database(
    use_cache: bool = True, use_local_cache: bool = True, verbose: bool = False
) -> dict:
    """Load the sustainability database with caching support.

    Loads data with the following priority:
    1. User cache (~/.cache/oss-sustain-guard/*.json) if enabled and valid
    2. Real-time analysis (if no cached data available)

    Args:
        use_cache: If False, skip all cached data sources and perform real-time analysis only.
        use_local_cache: If False, skip local cache loading (only affects initial load).
        verbose: If True, display cache loading information.

    Returns:
        Dictionary of package data keyed by "ecosystem:package_name".
    """
    merged = {}

    # If use_cache is False, return empty dict to force real-time analysis for all packages
    if not use_cache:
        return merged

    # List of ecosystems to load
    ecosystems = sorted({r.ecosystem_name for r in get_all_resolvers()})

    # Load from local cache first if enabled
    if use_local_cache and is_cache_enabled():
        for ecosystem in ecosystems:
            cached_data = load_cache(ecosystem, expected_version=ANALYSIS_VERSION)
            if cached_data:
                merged.update(cached_data)
                if verbose:
                    console.print(
                        f"[dim]Loaded {len(cached_data)} entries from local cache: {ecosystem}[/dim]"
                    )

    # Determine which packages need to be fetched from remote
    # We'll collect package names from the check command and fetch only those
    # For now, if cache is disabled, we skip remote fetching and go straight to real-time analysis

    return merged


def _summarize_observations(metrics: list[Metric]) -> str:
    """Summarize key observations from metrics with supportive language."""
    observations = [
        metric.message for metric in metrics if metric.risk in ("High", "Critical")
    ]
    if observations:
        observation_text = " • ".join(observations[:2])
        if len(observations) > 2:
            observation_text += f" (+{len(observations) - 2} more)"
        return observation_text
    return "No significant concerns detected"


def _format_health_status(score: int) -> tuple[str, str]:
    """Return (status_text, color) for a score."""
    if score >= 80:
        return "Healthy", "green"
    if score >= 50:
        return "Monitor", "yellow"
    return "Needs support", "red"


def _build_summary(results: list[AnalysisResult]) -> dict[str, int | float]:
    """Build summary statistics for report outputs."""
    scores = [result.total_score for result in results]
    total_packages = len(scores)
    average_score = round(sum(scores) / total_packages, 1) if total_packages else 0.0
    healthy_count = sum(1 for score in scores if score >= 80)
    needs_attention_count = sum(1 for score in scores if 50 <= score < 80)
    needs_support_count = sum(1 for score in scores if score < 50)
    return {
        "total_packages": total_packages,
        "average_score": average_score,
        "healthy_count": healthy_count,
        "needs_attention_count": needs_attention_count,
        "needs_support_count": needs_support_count,
    }


def _dedupe_packages(
    packages: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Remove duplicate (ecosystem, package) tuples while preserving order."""
    seen = set()
    unique_packages = []
    for eco, pkg in packages:
        key = f"{eco}:{pkg}"
        if key in seen:
            continue
        seen.add(key)
        unique_packages.append((eco, pkg))
    return unique_packages


def _coerce_int(value: Any, default: int = 0) -> int:
    """Coerce value to int with default fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _analysis_result_from_payload(payload: dict) -> AnalysisResult:
    """Reconstruct AnalysisResult from cached payload."""
    repo_url = payload.get("repo_url") or payload.get("github_url") or "unknown"
    metrics_payload = payload.get("metrics") or []
    metrics: list[Metric] = []
    for metric in metrics_payload:
        if isinstance(metric, Metric):
            metrics.append(metric)
            continue
        if not isinstance(metric, dict):
            continue
        metrics.append(
            Metric(
                str(metric.get("name", "")),
                _coerce_int(metric.get("score", 0)),
                _coerce_int(metric.get("max_score", 0)),
                str(metric.get("message", "")),
                str(metric.get("risk", "None")),
            )
        )

    models_payload = payload.get("models") or []
    models: list[MetricModel] = []
    for model in models_payload:
        if isinstance(model, MetricModel):
            models.append(model)
            continue
        if not isinstance(model, dict):
            continue
        models.append(
            MetricModel(
                str(model.get("name", "")),
                _coerce_int(model.get("score", 0)),
                _coerce_int(model.get("max_score", 0)),
                str(model.get("observation", "")),
            )
        )

    dependency_scores = payload.get("dependency_scores") or {}
    if isinstance(dependency_scores, dict):
        dependency_scores = {
            str(name): _coerce_int(score) for name, score in dependency_scores.items()
        }
    else:
        dependency_scores = {}

    funding_links = payload.get("funding_links")
    if not isinstance(funding_links, list):
        funding_links = []

    signals = payload.get("signals") if isinstance(payload.get("signals"), dict) else {}
    sample_counts = (
        payload.get("sample_counts")
        if isinstance(payload.get("sample_counts"), dict)
        else {}
    )
    skipped_metrics = payload.get("skipped_metrics")
    if not isinstance(skipped_metrics, list):
        skipped_metrics = []

    return AnalysisResult(
        repo_url=str(repo_url),
        total_score=_coerce_int(payload.get("total_score", 0)),
        metrics=metrics,
        funding_links=funding_links,
        is_community_driven=bool(payload.get("is_community_driven", False)),
        models=models,
        signals=signals,
        dependency_scores=dependency_scores,
        ecosystem=str(payload.get("ecosystem") or ""),
        sample_counts=sample_counts,
        skipped_metrics=skipped_metrics,
    )


def parse_package_spec(spec: str) -> tuple[str, str]:
    """
    Parse package specification in format 'ecosystem:package' or 'package'.

    Args:
        spec: Package specification string.

    Returns:
        Tuple of (ecosystem, package_name).
    """
    if ":" in spec:
        parts = spec.split(":", 1)
        return parts[0].lower(), parts[1]
    else:
        return "python", spec  # Default to Python for backward compatibility


def _resolve_lockfile_path(
    ecosystem: str,
    lockfile_path: str | Path | dict[str, Path] | None,
) -> Path | None:
    """Resolve the lockfile path for a given ecosystem."""
    if lockfile_path is None:
        return None
    if isinstance(lockfile_path, dict):
        return lockfile_path.get(ecosystem)
    return Path(lockfile_path)
