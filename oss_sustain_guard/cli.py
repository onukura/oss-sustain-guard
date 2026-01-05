"""
Command-line interface for OSS Sustain Guard.
"""

import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from functools import wraps
from html import escape
from importlib import resources
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from oss_sustain_guard.cache import (
    clear_cache,
    clear_expired_cache,
    get_cache_stats,
    get_cached_packages,
    load_cache,
    save_cache,
)
from oss_sustain_guard.config import (
    get_cache_ttl,
    get_lfx_config,
    get_output_style,
    is_cache_enabled,
    is_package_excluded,
    is_verbose_enabled,
    load_profile_config,
    set_cache_dir,
    set_cache_ttl,
    set_verify_ssl,
)
from oss_sustain_guard.core import (
    SCORING_PROFILES,
    AnalysisResult,
    Metric,
    MetricModel,
    analysis_result_to_dict,
    analyze_repository,
    apply_profile_overrides,
    compute_weighted_total_score,
    get_metric_weights,
)
from oss_sustain_guard.dependency_graph import get_all_dependencies
from oss_sustain_guard.http_client import close_async_http_client
from oss_sustain_guard.integrations.lfx import get_lfx_info
from oss_sustain_guard.resolvers import (
    detect_ecosystems,
    find_lockfiles,
    find_manifest_files,
    get_all_resolvers,
    get_resolver,
)
from oss_sustain_guard.visualization import (
    PlotlyVisualizer,
    build_networkx_graph,
)

# Schema version for cached data compatibility
ANALYSIS_VERSION = "1.5"

# project_root is the parent directory of oss_sustain_guard/
project_root = Path(__file__).resolve().parent.parent

# --- Constants ---
LATEST_DIR = project_root / "data" / "latest"

# --- Typer App ---
app = typer.Typer()
console = Console()

# --- Lockfile Cache ---
# Cache parsed lockfiles to avoid re-parsing during dependency analysis
_lockfile_cache: dict[str, dict[str, list[str]]] = {}


def syncify(f):
    return wraps(f)(lambda *args, **kwargs: asyncio.run(f(*args, **kwargs)))


def get_cached_lockfile_dependencies(
    lockfile_path: Path, package_name: str
) -> list[str] | None:
    """Get dependencies from cached lockfile parsing."""
    cache_key = str(lockfile_path.absolute())
    if cache_key in _lockfile_cache:
        return _lockfile_cache[cache_key].get(package_name)
    return None


def cache_lockfile_dependencies(
    lockfile_path: Path, package_deps: dict[str, list[str]]
):
    """Cache parsed lockfile dependencies."""
    cache_key = str(lockfile_path.absolute())
    _lockfile_cache[cache_key] = package_deps


def clear_lockfile_cache():
    """Clear the lockfile cache."""
    _lockfile_cache.clear()


# --- Helper Functions ---


def _cache_analysis_result(
    ecosystem: str,
    package_name: str,
    result: AnalysisResult,
    source: str = "realtime",
) -> None:
    """Persist analysis results to the local cache for reuse."""
    db_key = f"{ecosystem}:{package_name}"
    payload = analysis_result_to_dict(result)
    cache_entry = {
        db_key: {
            "ecosystem": ecosystem,
            "package_name": package_name,
            "github_url": result.repo_url,
            "metrics": payload.get("metrics", []),
            "funding_links": list(result.funding_links or []),
            "is_community_driven": result.is_community_driven,
            "models": result.models or [],
            "signals": result.signals or {},
            "sample_counts": result.sample_counts or {},
            "analysis_version": ANALYSIS_VERSION,
            "cache_metadata": {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "ttl_seconds": get_cache_ttl(),
                "source": source,
            },
        }
    }
    save_cache(ecosystem, cache_entry)


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


def _build_dependency_summary(
    direct_packages: list[tuple[str, str]],
    results_map: dict[tuple[str, str], AnalysisResult],
) -> dict[str, int]:
    """Build a dependency score summary for direct dependencies."""
    name_counts = Counter(pkg for _eco, pkg in direct_packages)
    summary: dict[str, int] = {}

    for eco, pkg in direct_packages:
        result = results_map.get((eco, pkg))
        if not result:
            continue
        display_name = f"{eco}:{pkg}" if name_counts[pkg] > 1 else pkg
        summary[display_name] = result.total_score

    return summary


def _write_json_results(
    results: list[AnalysisResult],
    profile: str,
    output_file: Path | None,
    dependency_summary: dict[str, int] | None = None,
    demo_notice: str | None = None,
) -> None:
    """Write results as JSON to stdout or a file."""
    weights = get_metric_weights(profile)

    # Load LFX configuration
    lfx_config = get_lfx_config()
    lfx_enabled = lfx_config.get("enabled", True)
    lfx_project_map = lfx_config.get("project_map", {})
    lfx_badge_types = lfx_config.get("badges", ["health-score", "active-contributors"])

    # Add LFX info to results
    results_with_lfx = []
    for result in results:
        result_dict = analysis_result_to_dict(result)

        if lfx_enabled:
            repo_name = result.repo_url.replace("https://github.com/", "")
            package_id = (
                f"{result.ecosystem}:{repo_name}" if result.ecosystem else repo_name
            )

            lfx_info = get_lfx_info(
                package_name=package_id,
                repo_url=result.repo_url,
                config_mapping=lfx_project_map,
                badge_types=lfx_badge_types,
            )

            if lfx_info:
                result_dict["lfx"] = {
                    "project_slug": lfx_info.project_slug,
                    "project_url": lfx_info.project_url,
                    "badges": lfx_info.badges,
                    "resolution": lfx_info.resolution,
                }

        results_with_lfx.append(result_dict)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "profile_metadata": {
            "name": profile,
            "metric_weights": weights,
        },
        "summary": _build_summary(results),
        "results": results_with_lfx,
    }
    if dependency_summary:
        payload["dependency_summary"] = dependency_summary
    if demo_notice:
        payload["demo"] = True
        payload["demo_notice"] = demo_notice
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json_text + "\n", encoding="utf-8")
        console.print(f"[green]✅ JSON report saved to {output_file}[/green]")
    else:
        sys.stdout.write(json_text + "\n")


def _load_report_template() -> str:
    """Load the HTML report template from package data or docs fallback."""
    try:
        package_template = resources.files("oss_sustain_guard").joinpath(
            "assets/report_template.html"
        )
        if package_template.is_file():
            return package_template.read_text(encoding="utf-8")
    except (AttributeError, FileNotFoundError, ModuleNotFoundError):
        pass

    template_path = project_root / "docs" / "assets" / "report_template.html"
    if not template_path.exists():
        raise FileNotFoundError(
            "HTML report template not found in package data or docs/assets."
        )
    return template_path.read_text(encoding="utf-8")


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _analysis_result_from_payload(payload: dict) -> AnalysisResult:
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


def _load_demo_payload() -> dict:
    candidates = []
    try:
        candidates.append(
            resources.files("oss_sustain_guard").joinpath(
                "assets/demo/demo_results.json"
            )
        )
    except (AttributeError, FileNotFoundError, ModuleNotFoundError):
        pass
    candidates.append(project_root / "examples" / "demo" / "demo_results.json")

    for candidate in candidates:
        try:
            if candidate.is_file():
                return json.loads(candidate.read_text(encoding="utf-8"))
        except OSError:
            continue

    raise FileNotFoundError(
        "Demo data not found. Expected assets/demo/demo_results.json."
    )


def _load_demo_results() -> tuple[list[AnalysisResult], str]:
    payload = _load_demo_payload()
    if isinstance(payload, dict):
        profile = str(payload.get("profile", "balanced"))
        results_payload = payload.get("results", [])
    else:
        profile = "balanced"
        results_payload = payload

    if not isinstance(results_payload, list):
        raise ValueError("Demo data format is invalid.")

    results = [
        _analysis_result_from_payload(item)
        for item in results_payload
        if isinstance(item, dict)
    ]

    if not results:
        raise ValueError("Demo data is empty.")

    return results, profile


def _render_html_report(
    results: list[AnalysisResult],
    profile: str,
    dependency_summary: dict[str, int] | None = None,
    demo_notice: str | None = None,
) -> str:
    """Render HTML report from template and results."""

    summary = _build_summary(results)
    demo_notice_block = ""
    if demo_notice:
        demo_notice_block = f'<div class="notice">{escape(demo_notice)}</div>'
    summary_cards = [
        ("Packages analyzed", str(summary["total_packages"])),
        ("Average score", f"{summary['average_score']:.1f}"),
        ("Healthy", str(summary["healthy_count"])),
        ("Monitor", str(summary["needs_attention_count"])),
        ("Needs support", str(summary["needs_support_count"])),
    ]
    summary_cards_html = "\n".join(
        f'<div class="summary-card"><div class="label">{escape(label)}</div>'
        f'<div class="value">{escape(value)}</div></div>'
        for label, value in summary_cards
    )

    # Load LFX configuration
    lfx_config = get_lfx_config()
    lfx_enabled = lfx_config.get("enabled", True)
    lfx_project_map = lfx_config.get("project_map", {})
    lfx_badge_types = lfx_config.get("badges", ["health-score", "active-contributors"])

    rows_html = []
    for result in results:
        status_text, status_color = _format_health_status(result.total_score)
        repo_name = result.repo_url.replace("https://github.com/", "")

        # Generate LFX info
        lfx_html = '<td class="lfx-not-available">—</td>'
        if lfx_enabled:
            # Create package identifier for LFX mapping
            package_id = (
                f"{result.ecosystem}:{repo_name}" if result.ecosystem else repo_name
            )

            lfx_info = get_lfx_info(
                package_name=package_id,
                repo_url=result.repo_url,
                config_mapping=lfx_project_map,
                badge_types=lfx_badge_types,
            )

            if lfx_info:
                # Build LFX cell HTML with link and badges
                badge_imgs = " ".join(
                    f'<img src="{badge_url}" alt="{badge_type}" title="{badge_type}">'
                    for badge_type, badge_url in lfx_info.badges.items()
                )
                lfx_html = (
                    f'<td><div class="lfx-badges">'
                    f'<a href="{lfx_info.project_url}" class="lfx-link" target="_blank" rel="noopener">View</a>'
                    f"{badge_imgs}"
                    f"</div></td>"
                )

        rows_html.append(
            "<tr>"
            f"<td>{escape(repo_name)}</td>"
            f"<td>{escape(result.ecosystem or 'unknown')}</td>"
            f'<td class="score {status_color}">{result.total_score}/100</td>'
            f'<td class="status {status_color}">{escape(status_text)}</td>'
            f"<td>{escape(_summarize_observations(result.metrics))}</td>"
            f"{lfx_html}"
            "</tr>"
        )

    json_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "profile_metadata": {
            "name": profile,
            "metric_weights": get_metric_weights(profile),
        },
        "summary": summary,
        "results": [analysis_result_to_dict(result) for result in results],
    }
    if dependency_summary:
        json_payload["dependency_summary"] = dependency_summary
    json_payload = json.dumps(
        json_payload,
        ensure_ascii=False,
        indent=2,
    )
    json_payload = json_payload.replace("</", "<\\/")

    template = _load_report_template()
    return template.format(
        report_title="OSS Sustain Guard Report",
        generated_at=escape(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
        profile=escape(profile),
        demo_notice_block=demo_notice_block,
        summary_cards=summary_cards_html,
        results_table_rows="\n".join(rows_html),
        results_json=json_payload,
    )


def _write_html_results(
    results: list[AnalysisResult],
    profile: str,
    output_file: Path | None,
    dependency_summary: dict[str, int] | None = None,
    demo_notice: str | None = None,
) -> None:
    """Write results as HTML to a file."""
    output_path = output_file or Path("oss-sustain-guard-report.html")
    output_path = output_path.expanduser()
    if output_path.exists() and output_path.is_dir():
        raise IsADirectoryError(f"Output path is a directory: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_text = _render_html_report(
        results, profile, dependency_summary, demo_notice=demo_notice
    )
    output_path.write_text(html_text, encoding="utf-8")
    console.print(f"[green]✅ HTML report saved to {output_path}[/green]")


def display_results_compact(
    results: list[AnalysisResult],
    show_dependencies: bool = False,
    dependency_summary: dict[str, int] | None = None,
):
    """Display analysis results in compact format (CI/CD-friendly)."""
    for result in results:
        # Determine status icon and color
        if result.total_score >= 80:
            icon = "✓"
            score_color = "green"
            status = "Healthy"
        elif result.total_score >= 50:
            icon = "⚠"
            score_color = "yellow"
            status = "Monitor"
        else:
            icon = "✗"
            score_color = "red"
            status = "Needs support"

        # Extract package name from repo URL
        package_name = result.repo_url.replace("https://github.com/", "")

        # One-line output: icon package [ecosystem] (score) - status
        if result.ecosystem:
            console.print(
                f"[{score_color}]{icon}[/{score_color}] "
                f"[cyan]{package_name}[/cyan] "
                f"[dim]\\[{result.ecosystem}][/dim] "
                f"[{score_color}]({result.total_score}/100)[/{score_color}] - "
                f"{status}"
            )
        else:
            console.print(
                f"[{score_color}]{icon}[/{score_color}] "
                f"[cyan]{package_name}[/cyan] "
                f"[{score_color}]({result.total_score}/100)[/{score_color}] - "
                f"{status}"
            )

        # Show dependency scores summary if available and requested
        if show_dependencies and result.dependency_scores:
            scores = list(result.dependency_scores.values())
            if scores:
                avg_score = sum(scores) / len(scores)
                min_score = min(scores)
                max_score = max(scores)
                console.print(
                    f"  🔗 Dependencies: avg={avg_score:.0f}, min={min_score}, max={max_score}, count={len(scores)}"
                )

    if dependency_summary:
        scores = list(dependency_summary.values())
        if scores:
            avg_score = sum(scores) / len(scores)
            min_score = min(scores)
            max_score = max(scores)
            console.print(
                f"🔗 Dependencies: avg={avg_score:.0f}, min={min_score}, max={max_score}, count={len(scores)}"
            )


def display_results_table(
    results: list[AnalysisResult],
    show_models: bool = False,
    show_dependencies: bool = False,
    dependency_summary: dict[str, int] | None = None,
):
    """Display the analysis results in a rich table."""
    table = Table(title="OSS Sustain Guard Report")
    table.add_column("Package", justify="left", style="cyan", no_wrap=True)
    table.add_column("Ecosystem", justify="left", style="blue", no_wrap=True)
    table.add_column("Score", justify="center", style="magenta")
    table.add_column("Health Status", justify="left")
    table.add_column("Key Observations", justify="left")

    for result in results:
        score_color = "green"
        if result.total_score < 50:
            score_color = "red"
        elif result.total_score < 80:
            score_color = "yellow"

        # Determine health status with supportive language
        if result.total_score >= 80:
            health_status = "[green]Healthy ✓[/green]"
        elif result.total_score >= 50:
            health_status = "[yellow]Monitor[/yellow]"
        else:
            health_status = "[red]Needs support[/red]"

        observation_text = _summarize_observations(result.metrics)

        table.add_row(
            result.repo_url.replace("https://github.com/", ""),
            result.ecosystem or "unknown",
            f"[{score_color}]{result.total_score}/100[/{score_color}]",
            health_status,
            observation_text,
        )

    console.print(table)

    # Display skipped metrics if any
    for result in results:
        if result.skipped_metrics:
            console.print(
                f"\n⚠️  [yellow]{result.repo_url.replace('https://github.com/', '')}:[/yellow] "
                f"[yellow]{len(result.skipped_metrics)} metric(s) not measured:[/yellow] {', '.join(result.skipped_metrics)}"
            )

    # Display LFX Insights links if available
    lfx_config = get_lfx_config()
    if lfx_config.get("enabled", True):
        lfx_project_map = lfx_config.get("project_map", {})
        for result in results:
            repo_name = result.repo_url.replace("https://github.com/", "")
            package_id = (
                f"{result.ecosystem}:{repo_name}" if result.ecosystem else repo_name
            )

            lfx_info = get_lfx_info(
                package_name=package_id,
                repo_url=result.repo_url,
                config_mapping=lfx_project_map,
            )

            if lfx_info:
                console.print(
                    f"\n📊 [bold cyan]{repo_name}[/bold cyan] "
                    f"- LFX Insights: [link={lfx_info.project_url}]{lfx_info.project_url}[/link]"
                )

    # Display funding links if available
    for result in results:
        if result.funding_links:
            console.print(
                f"\n💝 [bold cyan]{result.repo_url.replace('https://github.com/', '')}[/bold cyan] "
                f"- Consider supporting:"
            )
            for link in result.funding_links:
                platform = link.get("platform", "Unknown")
                url = link.get("url", "")
                console.print(f"   • {platform}: [link={url}]{url}[/link]")

    # Display dependency scores if available and requested
    if show_dependencies:
        for result in results:
            if result.dependency_scores:
                console.print(
                    f"\n🔗 [bold cyan]{result.repo_url.replace('https://github.com/', '')}[/bold cyan] "
                    f"- Dependency Reference Scores (Top 10):"
                )
                # Sort by score descending
                sorted_deps = sorted(
                    result.dependency_scores.items(), key=lambda x: x[1], reverse=True
                )
                for dep_name, dep_score in sorted_deps[:10]:
                    if dep_score >= 80:
                        health = "[green]✓ Healthy[/green]"
                    elif dep_score >= 50:
                        health = "[yellow]⚠ Monitor[/yellow]"
                    else:
                        health = "[red]✗ Needs support[/red]"
                    score_color = (
                        "green"
                        if dep_score >= 80
                        else ("yellow" if dep_score >= 50 else "red")
                    )
                    console.print(
                        f"   • [{score_color}]{dep_name}[/{score_color}] "
                        f"[{score_color}]{dep_score}/100[/{score_color}] {health}"
                    )
                if len(result.dependency_scores) > 10:
                    console.print(
                        f"   [dim]... and {len(result.dependency_scores) - 10} more dependencies[/dim]"
                    )

    if dependency_summary:
        console.print("\n🔗 Dependency Reference Scores (Top 10):")
        sorted_deps = sorted(
            dependency_summary.items(), key=lambda x: x[1], reverse=True
        )
        for dep_name, dep_score in sorted_deps[:10]:
            if dep_score >= 80:
                health = "[green]✓ Healthy[/green]"
            elif dep_score >= 50:
                health = "[yellow]⚠ Monitor[/yellow]"
            else:
                health = "[red]✗ Needs support[/red]"
            score_color = (
                "green" if dep_score >= 80 else ("yellow" if dep_score >= 50 else "red")
            )
            console.print(
                f"   • [{score_color}]{dep_name}[/{score_color}] "
                f"[{score_color}]{dep_score}/100[/{score_color}] {health}"
            )
        if len(dependency_summary) > 10:
            console.print(
                f"   [dim]... and {len(dependency_summary) - 10} more dependencies[/dim]"
            )

    # Display CHAOSS metric models if available and requested
    if show_models:
        for result in results:
            if result.models:
                # Replace github.com or gitlab.com appropriately
                repo_display = result.repo_url.replace(
                    "https://github.com/", ""
                ).replace("https://gitlab.com/", "gitlab:")
                console.print(
                    f"\n📊 [bold cyan]{repo_display}[/bold cyan] - CHAOSS Metric Models:"
                )
                for model in result.models:
                    # Model is a list: [name, score, max_score, observation]
                    model_name = model[0]
                    model_score = model[1]
                    model_max_score = model[2]
                    model_observation = model[3]

                    # Color code based on model score
                    model_color = "green"
                    if model_score < 50:
                        model_color = "red"
                    elif model_score < 80:
                        model_color = "yellow"

                    console.print(
                        f"   • {model_name}: [{model_color}]{model_score}/{model_max_score}[/{model_color}] - {model_observation}"
                    )


def display_results(
    results: list[AnalysisResult],
    show_models: bool = False,
    show_dependencies: bool = False,
    output_format: str = "terminal",
    output_file: Path | None = None,
    output_style: str = "normal",
    profile: str = "balanced",
    dependency_summary: dict[str, int] | None = None,
    demo_notice: str | None = None,
) -> None:
    """Display or export analysis results by format."""
    if output_format in {"json", "html"}:
        try:
            if output_format == "json":
                _write_json_results(
                    results,
                    profile,
                    output_file,
                    dependency_summary=dependency_summary,
                    demo_notice=demo_notice,
                )
            else:
                _write_html_results(
                    results,
                    profile,
                    output_file,
                    dependency_summary=dependency_summary,
                    demo_notice=demo_notice,
                )
        except (FileNotFoundError, IsADirectoryError, OSError) as exc:
            console.print(f"[yellow]⚠️  Unable to write report: {exc}[/yellow]")
            raise typer.Exit(code=1) from exc
        return

    if demo_notice:
        console.print(f"[yellow]ℹ️  {demo_notice}[/yellow]")

    if output_style == "compact":
        display_results_compact(
            results,
            show_dependencies=show_dependencies,
            dependency_summary=dependency_summary,
        )
    elif output_style == "detail":
        display_results_detailed(
            results,
            show_signals=True,
            show_models=show_models,
            profile=profile,
            dependency_summary=dependency_summary,
        )
    else:
        display_results_table(
            results,
            show_models=show_models,
            show_dependencies=show_dependencies,
            dependency_summary=dependency_summary,
        )


def display_results_detailed(
    results: list[AnalysisResult],
    show_signals: bool = False,
    show_models: bool = False,
    profile: str = "balanced",
    dependency_summary: dict[str, int] | None = None,
):
    """Display detailed analysis results with all metrics for each package."""
    # Get weights for current profile
    weights = get_metric_weights(profile)

    # Display profile information at the beginning
    console.print(
        f"\n[bold magenta]📊 Scoring Profile: {profile.title()}[/bold magenta]"
    )

    # Display metric weights
    weights_parts = []
    for metric_name, weight in sorted(weights.items(), key=lambda x: -x[1]):
        weights_parts.append(f"{metric_name}={weight}")
    console.print(f"[dim]Metric Weights: {', '.join(weights_parts[:5])}")
    if len(weights) > 5:
        console.print(
            f"[dim]                ... and {len(weights) - 5} more metrics[/dim]"
        )
    console.print()

    for result in results:
        # Determine overall color
        risk_color = "green"
        if result.total_score < 50:
            risk_color = "red"
        elif result.total_score < 80:
            risk_color = "yellow"

        # Header
        ecosystem_label = f" ({result.ecosystem})" if result.ecosystem else ""
        console.print(
            f"\n📦 [bold cyan]{result.repo_url.replace('https://github.com/', '')}{ecosystem_label}[/bold cyan]"
        )
        console.print(
            f"   Total Score: [{risk_color}]{result.total_score}/100[/{risk_color}]"
        )

        # Display LFX Insights link if available
        lfx_config = get_lfx_config()
        if lfx_config.get("enabled", True):
            lfx_project_map = lfx_config.get("project_map", {})
            repo_name = result.repo_url.replace("https://github.com/", "")
            package_id = (
                f"{result.ecosystem}:{repo_name}" if result.ecosystem else repo_name
            )

            lfx_info = get_lfx_info(
                package_name=package_id,
                repo_url=result.repo_url,
                config_mapping=lfx_project_map,
            )

            if lfx_info:
                console.print(
                    f"   📊 [bold cyan]LFX Insights:[/bold cyan] [link={lfx_info.project_url}]{lfx_info.project_url}[/link]"
                )

        # Display funding information if available
        if result.funding_links:
            console.print(
                "   💝 [bold cyan]Funding support available[/bold cyan] - Consider supporting:"
            )
            for link in result.funding_links:
                platform = link.get("platform", "Unknown")
                url = link.get("url", "")
                console.print(f"      • {platform}: [link={url}]{url}[/link]")

        # Display sample counts for transparency
        if result.sample_counts:
            sample_info_parts = []
            if result.sample_counts.get("commits", 0) > 0:
                sample_info_parts.append(f"commits={result.sample_counts['commits']}")
            if result.sample_counts.get("merged_prs", 0) > 0:
                sample_info_parts.append(
                    f"merged_prs={result.sample_counts['merged_prs']}"
                )
            if result.sample_counts.get("closed_prs", 0) > 0:
                sample_info_parts.append(
                    f"closed_prs={result.sample_counts['closed_prs']}"
                )
            if result.sample_counts.get("open_issues", 0) > 0:
                sample_info_parts.append(
                    f"open_issues={result.sample_counts['open_issues']}"
                )
            if result.sample_counts.get("closed_issues", 0) > 0:
                sample_info_parts.append(
                    f"closed_issues={result.sample_counts['closed_issues']}"
                )
            if result.sample_counts.get("releases", 0) > 0:
                sample_info_parts.append(f"releases={result.sample_counts['releases']}")

            if sample_info_parts:
                console.print(
                    f"   [dim]💾 Analysis based on: {', '.join(sample_info_parts)}[/dim]"
                )

        # Metrics table
        metrics_table = Table(show_header=True, header_style="bold magenta")
        metrics_table.add_column("Metric", style="cyan", no_wrap=True)
        metrics_table.add_column("Score", justify="center", style="magenta")
        metrics_table.add_column("Weight", justify="center", style="dim cyan")
        metrics_table.add_column("Status", justify="left")
        metrics_table.add_column("Observation", justify="left")

        for metric in result.metrics:
            # Status color coding with supportive language based on both risk and score
            status_style = "green"
            status_text = "Good"

            # Primary: use risk level if available
            if metric.risk in ("Critical", "High"):
                status_style = "red"
                status_text = "Needs attention"
            elif metric.risk == "Medium":
                status_style = "yellow"
                status_text = "Monitor"
            elif metric.risk == "Low":
                status_style = "yellow"
                status_text = "Consider improving"
            elif metric.risk == "None":
                # Secondary: check score ratio for "None" risk (all metrics now 0-10)
                score_ratio = metric.score / 10.0
                if score_ratio >= 0.8:
                    status_style = "green"
                    status_text = "Healthy"
                elif score_ratio >= 0.5:
                    status_style = "yellow"
                    status_text = "Monitor"
                else:
                    status_style = "red"
                    status_text = "Needs attention"
            else:
                # Default to green for unknown risk
                status_style = "green"
                status_text = "Healthy"

            # Get weight for this metric
            metric_weight = weights.get(metric.name, 1)

            metrics_table.add_row(
                metric.name,
                f"[cyan]{metric.score}[/cyan]",
                f"[dim cyan]{metric_weight}[/dim cyan]",
                f"[{status_style}]{status_text}[/{status_style}]",
                metric.message,
            )

        console.print(metrics_table)

        # Display skipped metrics if any
        if result.skipped_metrics:
            console.print(
                f"   [yellow]⚠️  {len(result.skipped_metrics)} metric(s) not measured:[/yellow] {', '.join(result.skipped_metrics)}"
            )

        # Display CHAOSS metric models if available and requested
        if show_models and result.models:
            console.print("\n   📊 [bold magenta]CHAOSS Metric Models:[/bold magenta]")
            models_table = Table(show_header=True, header_style="bold cyan")
            models_table.add_column("Model", style="cyan", no_wrap=True)
            models_table.add_column("Score", justify="center", style="magenta")
            models_table.add_column("Max", justify="center", style="magenta")
            models_table.add_column("Observation", justify="left")

            for model in result.models:
                # Color code based on model score
                model_color = "green"
                if model.score < 50:
                    model_color = "red"
                elif model.score < 80:
                    model_color = "yellow"

                models_table.add_row(
                    model.name,
                    f"[{model_color}]{model.score}[/{model_color}]",
                    f"[cyan]{model.max_score}[/cyan]",
                    model.observation,
                )

            console.print(models_table)

        # Display raw signals if available and requested
        if show_signals and result.signals:
            console.print("\n   🔍 [bold magenta]Raw Signals:[/bold magenta]")
            signals_table = Table(show_header=True, header_style="bold cyan")
            signals_table.add_column("Signal", style="cyan", no_wrap=True)
            signals_table.add_column("Value", justify="left")

            for signal_name, signal_value in result.signals.items():
                signals_table.add_row(signal_name, str(signal_value))

            console.print(signals_table)

        # Display dependency scores if available
        if result.dependency_scores:
            console.print(
                "\n   🔗 [bold magenta]Dependency Reference Scores:[/bold magenta]"
            )
            deps_table = Table(show_header=True, header_style="bold cyan")
            deps_table.add_column("Package", style="cyan", no_wrap=True)
            deps_table.add_column("Score", justify="center", style="magenta")
            deps_table.add_column("Health", justify="left")

            # Sort by score descending
            sorted_deps = sorted(
                result.dependency_scores.items(), key=lambda x: x[1], reverse=True
            )
            for dep_name, dep_score in sorted_deps[:15]:  # Show top 15 dependencies
                if dep_score >= 80:
                    health = "[green]Healthy[/green]"
                elif dep_score >= 50:
                    health = "[yellow]Monitor[/yellow]"
                else:
                    health = "[red]Needs support[/red]"

                score_color = (
                    "green"
                    if dep_score >= 80
                    else ("yellow" if dep_score >= 50 else "red")
                )
                deps_table.add_row(
                    dep_name,
                    f"[{score_color}]{dep_score}/100[/{score_color}]",
                    health,
                )

            if len(result.dependency_scores) > 15:
                deps_table.add_row(
                    f"[dim]... and {len(result.dependency_scores) - 15} more[/dim]",
                    "",
                    "",
                )

            console.print(deps_table)

    if dependency_summary:
        console.print(
            "\n🔗 [bold magenta]Dependency Reference Scores (Top 15):[/bold magenta]"
        )
        deps_table = Table(show_header=True, header_style="bold cyan")
        deps_table.add_column("Package", style="cyan", no_wrap=True)
        deps_table.add_column("Score", justify="center", style="magenta")
        deps_table.add_column("Health", justify="left")

        sorted_deps = sorted(
            dependency_summary.items(), key=lambda x: x[1], reverse=True
        )
        for dep_name, dep_score in sorted_deps[:15]:
            if dep_score >= 80:
                health = "[green]Healthy[/green]"
            elif dep_score >= 50:
                health = "[yellow]Monitor[/yellow]"
            else:
                health = "[red]Needs support[/red]"

            score_color = (
                "green" if dep_score >= 80 else ("yellow" if dep_score >= 50 else "red")
            )
            deps_table.add_row(
                dep_name,
                f"[{score_color}]{dep_score}/100[/{score_color}]",
                health,
            )

        if len(dependency_summary) > 15:
            deps_table.add_row(
                f"[dim]... and {len(dependency_summary) - 15} more[/dim]",
                "",
                "",
            )

        console.print(deps_table)


async def analyze_packages_parallel(
    packages_data: list[tuple[str, str]],
    db: dict,
    profile: str = "balanced",
    show_dependencies: bool = False,
    lockfile_path: str | Path | dict[str, Path] | None = None,
    verbose: bool = False,
    use_local_cache: bool = True,
    max_workers: int = 5,
) -> tuple[list[AnalysisResult | None], dict[str, list[str]]]:
    """
    Analyze multiple packages in parallel using ThreadPoolExecutor.

    Args:
        packages_data: List of (ecosystem, package_name) tuples.
        db: Cached database dictionary.
        profile: Scoring profile name.
        show_dependencies: Analyze and include dependency scores.
        lockfile_path: Path to lockfile for dependency analysis (or mapping by ecosystem).
        verbose: If True, display cache source information.
        use_local_cache: If False, skip local cache lookup.
        max_workers: Maximum number of parallel workers (default: 5).

    Returns:
        Tuple of (List of AnalysisResult or None for each package, verbose logs dict)
    """
    results = []
    total = len(packages_data)
    verbose_logs: dict[str, list[str]] = {}  # Collect logs instead of printing directly

    if total == 0:
        return results, verbose_logs

    # For single package, don't use parallel processing
    if total == 1:
        ecosystem, pkg = packages_data[0]
        result = await analyze_package(
            pkg,
            ecosystem,
            db,
            profile,
            show_dependencies,
            lockfile_path,
            verbose,
            use_local_cache,
        )
        return [result], verbose_logs

    # Use progress bar for multiple packages
    # Suppress stderr from resolvers during analysis to keep progress bar clean
    from io import StringIO

    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,  # Auto-hide progress bar after completion
        ) as progress:
            task = progress.add_task("[cyan]Analyzing packages...", total=total)

            # Step 1: Check cache and resolve repositories
            uncached_packages: list[tuple[str, str]] = []  # (ecosystem, pkg)
            pkg_to_index: dict[tuple[str, str], int] = {}
        results_map: dict[int, AnalysisResult | None] = {}

        for idx, (ecosystem, pkg) in enumerate(packages_data):
            pkg_to_index[(ecosystem, pkg)] = idx
            db_key = f"{ecosystem}:{pkg}"

            # Check if in cache
            if use_local_cache and db_key in db:
                cached_data = db[db_key]
                payload_version = cached_data.get("analysis_version")
                if payload_version == ANALYSIS_VERSION:
                    # Use cached data
                    metrics = [
                        Metric(
                            m["name"],
                            m["score"],
                            m["max_score"],
                            m["message"],
                            m["risk"],
                        )
                        for m in cached_data.get("metrics", [])
                    ]
                    recalculated_score = compute_weighted_total_score(metrics, profile)
                    result = AnalysisResult(
                        repo_url=cached_data.get("github_url", "unknown"),
                        total_score=recalculated_score,
                        metrics=metrics,
                        funding_links=cached_data.get("funding_links", []),
                        is_community_driven=cached_data.get(
                            "is_community_driven", False
                        ),
                        models=cached_data.get("models", []),
                        signals=cached_data.get("signals", {}),
                        dependency_scores={},
                        ecosystem=ecosystem,
                        sample_counts=cached_data.get("sample_counts", {}),
                    )
                    resolved_lockfile = _resolve_lockfile_path(ecosystem, lockfile_path)
                    if show_dependencies and resolved_lockfile:
                        dep_scores = await _analyze_dependencies_for_package(
                            ecosystem=ecosystem,
                            lockfile_path=resolved_lockfile,
                            db=db,
                            package_name=pkg,
                            profile=profile,
                            max_workers=max_workers,
                        )
                        result = result._replace(dependency_scores=dep_scores)
                    results_map[idx] = result
                    progress.advance(task)
                    continue

            # Not in cache - need to resolve and analyze
            resolver = get_resolver(ecosystem)
            if not resolver:
                results_map[idx] = None
                progress.advance(task)
                continue

            repo_info = await resolver.resolve_repository(pkg)
            if not repo_info:
                results_map[idx] = None
                progress.advance(task)
                continue

            uncached_packages.append((ecosystem, pkg))

        # Step 2: Analyze uncached packages in parallel using asyncio with rate limiting
        if uncached_packages:
            # Create a semaphore to limit concurrent API calls (avoid hitting GitHub rate limits)
            # GitHub allows 5000 API calls/hour for authenticated requests
            # Using max_workers to control concurrency
            semaphore = asyncio.Semaphore(max_workers)

            async def analyze_with_semaphore(
                ecosystem: str, pkg: str
            ) -> AnalysisResult | None:
                async with semaphore:
                    return await analyze_package(
                        pkg,
                        ecosystem,
                        db,
                        profile,
                        show_dependencies,
                        lockfile_path,
                        verbose,
                        use_local_cache,
                        verbose_logs,
                    )

            async def analyze_all() -> list[Any]:
                tasks = [
                    analyze_with_semaphore(ecosystem, pkg)
                    for ecosystem, pkg in uncached_packages
                ]
                return await asyncio.gather(*tasks, return_exceptions=True)

            results_list = await analyze_all()

            for idx_offset, result in enumerate(results_list):
                ecosystem, pkg = uncached_packages[idx_offset]
                idx = pkg_to_index[(ecosystem, pkg)]
                try:
                    if isinstance(result, Exception):
                        results_map[idx] = None
                    else:
                        results_map[idx] = result
                except Exception:
                    results_map[idx] = None
                progress.advance(task)

        # Return results in original order
        results = [results_map.get(i) for i in range(total)]

    finally:
        # Restore stderr
        sys.stderr = old_stderr

    return results, verbose_logs


async def _analyze_dependencies_for_package(
    ecosystem: str,
    lockfile_path: str | Path,
    db: dict,
    package_name: str,
    profile: str = "balanced",
    analyze_missing: bool = True,
    max_workers: int = 5,
) -> dict[str, int]:
    """
    Analyze dependencies for a specific package from a lockfile and return their scores.

    Args:
        ecosystem: Ecosystem name (python, javascript, etc).
        lockfile_path: Path to the lockfile.
        db: Database dictionary with cached package metrics.
        package_name: Name of the package to get dependencies for.
        profile: Scoring profile to use for calculating scores.
        analyze_missing: If True, analyze dependencies not found in cache.

    Returns:
        Dictionary mapping dependency package names to their scores.
    """
    try:
        from oss_sustain_guard.dependency_graph import get_package_dependencies

        lockfile_path = Path(lockfile_path)
        if not lockfile_path.exists():
            return {}

        # Check cache first
        cached_deps = get_cached_lockfile_dependencies(lockfile_path, package_name)
        if cached_deps is not None:
            dep_names = cached_deps
        else:
            # Parse lockfile and cache results
            dep_names = get_package_dependencies(lockfile_path, package_name)
            if dep_names:
                # Cache for future use (simple single-package cache)
                cache_lockfile_dependencies(lockfile_path, {package_name: dep_names})

        if not dep_names:
            return {}

        dep_scores: dict[str, int] = {}
        missing_deps: list[str] = []

        # Look up metrics for each dependency from local db first
        for dep_name in dep_names:
            db_key = f"{ecosystem}:{dep_name}"
            if db_key in db:
                try:
                    pkg_data = db[db_key]
                    # Check if cached version is compatible
                    payload_version = pkg_data.get("analysis_version")
                    if payload_version == ANALYSIS_VERSION:
                        # Calculate score from metrics using the specified profile
                        metrics_data = pkg_data.get("metrics", [])
                        if metrics_data:
                            metrics = [
                                Metric(
                                    m["name"],
                                    m["score"],
                                    m["max_score"],
                                    m["message"],
                                    m["risk"],
                                )
                                for m in metrics_data
                            ]
                            score = compute_weighted_total_score(metrics, profile)
                            dep_scores[dep_name] = score
                    else:
                        # Version mismatch, need to re-analyze
                        missing_deps.append(dep_name)
                except (KeyError, TypeError):
                    missing_deps.append(dep_name)
            else:
                missing_deps.append(dep_name)

        # Analyze missing dependencies if requested
        if analyze_missing and missing_deps:
            # Prepare packages for batch analysis
            packages_to_analyze = [(ecosystem, dep) for dep in missing_deps]

            # Analyze in parallel (using the existing parallel analysis function)
            results, _ = await analyze_packages_parallel(
                packages_to_analyze,
                db,
                profile,
                show_dependencies=False,  # Don't recurse
                lockfile_path=None,
                verbose=False,
                use_local_cache=True,
                max_workers=max_workers,
            )

            # Add scores from newly analyzed packages
            for idx, result in enumerate(results):
                if result:
                    dep_name = missing_deps[idx]
                    dep_scores[dep_name] = result.total_score

        return dep_scores
    except Exception as e:
        console.print(f"    [dim]Note: Unable to analyze dependencies: {e}[/dim]")
        return {}


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


async def analyze_package(
    package_name: str,
    ecosystem: str,
    db: dict,
    profile: str = "balanced",
    show_dependencies: bool = False,
    lockfile_path: str | Path | dict[str, Path] | None = None,
    verbose: bool = False,
    use_local_cache: bool = True,
    log_buffer: dict[str, list[str]] | None = None,
    max_workers: int = 5,
) -> AnalysisResult | None:
    """
    Analyze a single package.

    Args:
        package_name: Name of the package.
        ecosystem: Ecosystem name (python, javascript, go, rust).
        db: Cached database dictionary.
        profile: Scoring profile name.
        show_dependencies: Analyze and include dependency scores.
        lockfile_path: Path to lockfile for dependency analysis (or mapping by ecosystem).
        verbose: If True, collect verbose information.
        use_local_cache: If False, skip local cache lookup.
        log_buffer: Dictionary to collect verbose logs (for parallel execution).

    Returns:
        AnalysisResult or None if analysis fails.
    """
    if log_buffer is None:
        log_buffer = {}

    # Check if package is excluded
    if is_package_excluded(package_name):
        return None

    # Create database key
    db_key = f"{ecosystem}:{package_name}"

    # Check local cache first
    if db_key in db:
        if verbose:
            if db_key not in log_buffer:
                log_buffer[db_key] = []
            log_buffer[db_key].append(
                f"  -> 💾 Found [bold green]{db_key}[/bold green] in local cache"
            )
        cached_data = db[db_key]
        payload_version = cached_data.get("analysis_version")
        if payload_version != ANALYSIS_VERSION:
            if verbose:
                if db_key not in log_buffer:
                    log_buffer[db_key] = []
                log_buffer[db_key].append(
                    f"[dim]ℹ️  Cache version mismatch for {db_key} "
                    f"({payload_version or 'unknown'} != {ANALYSIS_VERSION}). "
                    f"Fetching fresh data...[/dim]"
                )
        else:
            if verbose:
                if db_key not in log_buffer:
                    log_buffer[db_key] = []
                log_buffer[db_key].append(
                    f"  -> 🔄 Reconstructing metrics from cached data (analysis_version: {payload_version})"
                )

            # Reconstruct metrics from cached data
            metrics = [
                Metric(
                    m["name"],
                    m["score"],
                    m["max_score"],
                    m["message"],
                    m["risk"],
                )
                for m in cached_data.get("metrics", [])
            ]

            if verbose:
                if db_key not in log_buffer:
                    log_buffer[db_key] = []
                log_buffer[db_key].append(
                    f"     ✓ Reconstructed {len(metrics)} metrics"
                )

            # Recalculate total score with selected profile
            recalculated_score = compute_weighted_total_score(metrics, profile)

            if verbose:
                if db_key not in log_buffer:
                    log_buffer[db_key] = []
                log_buffer[db_key].append(
                    f"     ✓ Recalculated total score using profile '{profile}': {recalculated_score}/100"
                )

            # Reconstruct AnalysisResult
            result = AnalysisResult(
                repo_url=cached_data.get("github_url", "unknown"),
                total_score=recalculated_score,
                metrics=metrics,
                funding_links=cached_data.get("funding_links", []),
                is_community_driven=cached_data.get("is_community_driven", False),
                models=cached_data.get("models", []),
                signals=cached_data.get("signals", {}),
                dependency_scores={},  # Empty for cached results
                ecosystem=ecosystem,
                sample_counts=cached_data.get("sample_counts", {}),
            )

            # If show_dependencies is requested, analyze dependencies
            resolved_lockfile = _resolve_lockfile_path(ecosystem, lockfile_path)
            if show_dependencies and resolved_lockfile:
                dep_scores = await _analyze_dependencies_for_package(
                    ecosystem=ecosystem,
                    lockfile_path=resolved_lockfile,
                    db=db,
                    package_name=package_name,
                    profile=profile,
                    max_workers=max_workers,
                )
                result = result._replace(dependency_scores=dep_scores)

            return result

    # Resolve GitHub URL using appropriate resolver
    resolver = get_resolver(ecosystem)
    if not resolver:
        if verbose:
            if db_key not in log_buffer:
                log_buffer[db_key] = []
            log_buffer[db_key].append(
                f"  -> [yellow]ℹ️  Ecosystem '{ecosystem}' is not yet supported[/yellow]"
            )
        return None

    repo_info = await resolver.resolve_repository(package_name)
    if not repo_info:
        if verbose:
            if db_key not in log_buffer:
                log_buffer[db_key] = []
            log_buffer[db_key].append(
                f"  -> [yellow]ℹ️  Repository not found for {db_key}. Package may not have public source code.[/yellow]"
            )
        return None

    # Get provider and repository info
    provider = repo_info.provider

    # For GitLab, use the full path; for GitHub, use owner/name
    if provider == "gitlab":
        # GitLab supports nested groups, so we need to split path into parent/repo
        path_segments = repo_info.path.split("/")
        if len(path_segments) < 2:
            if verbose:
                if db_key not in log_buffer:
                    log_buffer[db_key] = []
                log_buffer[db_key].append(
                    f"  -> [yellow]ℹ️  Invalid repository path for {db_key}[/yellow]"
                )
            return None
        # Owner is everything except the last segment (project name)
        owner = "/".join(path_segments[:-1])
        repo_name = path_segments[-1]
    else:
        owner, repo_name = repo_info.owner, repo_info.name

    if verbose:
        if db_key not in log_buffer:
            log_buffer[db_key] = []
        log_buffer[db_key].append(
            f"  -> 🔍 [bold yellow]{db_key}[/bold yellow] analyzing real-time (no cache)..."
        )

    try:
        analysis_result = await analyze_repository(
            owner,
            repo_name,
            profile=profile,
            vcs_platform=provider,
        )

        # Add ecosystem to result
        analysis_result = analysis_result._replace(ecosystem=ecosystem)

        # Save to cache for future use (without total_score - it will be recalculated based on profile)
        _cache_analysis_result(ecosystem, package_name, analysis_result)
        if verbose:
            if db_key not in log_buffer:
                log_buffer[db_key] = []
            log_buffer[db_key].append("    [dim]💾 Cached for future use[/dim]")

        # If show_dependencies is requested, analyze dependencies
        resolved_lockfile = _resolve_lockfile_path(ecosystem, lockfile_path)
        if show_dependencies and resolved_lockfile:
            dep_scores = await _analyze_dependencies_for_package(
                ecosystem=ecosystem,
                lockfile_path=resolved_lockfile,
                db=db,
                package_name=package_name,
                profile=profile,
                max_workers=max_workers,
            )
            analysis_result = analysis_result._replace(dependency_scores=dep_scores)

        return analysis_result
    except ValueError as e:
        # Handle user-friendly error messages
        error_msg = str(e).lower()
        if "token" in error_msg:
            console.print(
                f"    [yellow]⚠️  {owner}/{repo_name}: GitHub token required or invalid. "
                "Check GITHUB_TOKEN environment variable.[/yellow]"
            )
        elif "not found" in error_msg:
            console.print(
                f"    [yellow]⚠️  {owner}/{repo_name}: Repository not found or inaccessible.[/yellow]"
            )
        else:
            console.print(f"    [yellow]⚠️  {owner}/{repo_name}: {e}[/yellow]")
        return None
    except Exception as e:
        # Generic exception handler with user-friendly messaging
        error_msg = str(e).lower()
        if "rate" in error_msg or "429" in error_msg:
            console.print(
                f"    [yellow]⚠️  {owner}/{repo_name}: GitHub API rate limit reached. "
                "Please try again later or check your token scopes.[/yellow]"
            )
        elif "timeout" in error_msg or "connection" in error_msg:
            console.print(
                f"    [yellow]⚠️  {owner}/{repo_name}: Network timeout. "
                "Check your internet connection and try again.[/yellow]"
            )
        else:
            console.print(
                f"    [yellow]⚠️  {owner}/{repo_name}: Unable to complete analysis.[/yellow]"
            )
        return None


@app.command()
@syncify
async def check(
    packages: list[str] = typer.Argument(
        None,
        help="Packages to analyze (format: 'package', 'ecosystem:package', or file path). Examples: 'requests', 'npm:react', 'go:gin', 'php:symfony/console', 'java:com.google.guava:guava', 'csharp:Newtonsoft.Json'. If omitted, auto-detects from manifest files.",
    ),
    ecosystem: str = typer.Option(
        "auto",
        "--ecosystem",
        "-e",
        help=(
            "Default ecosystem for unqualified packages (python, javascript, go, rust, "
            "php, java, kotlin, scala, csharp, dotnet, dart, elixir, haskell, perl, r, "
            "ruby, swift). Use 'auto' to detect."
        ),
    ),
    include_lock: bool = typer.Option(
        False,
        "--include-lock",
        "-l",
        help="Include packages from lockfiles in the current directory.",
    ),
    verbose: bool | None = typer.Option(
        None,
        "--verbose",
        "-v",
        help="Enable verbose logging (cache operations, metric reconstruction details). If not specified, uses config file default.",
    ),
    output_style: str | None = typer.Option(
        None,
        "--output-style",
        "-o",
        help="Output format style for terminal output: compact (one line per package, CI/CD-friendly), normal (table with key observations), detail (full metrics table with signals). If not specified, uses config file default.",
    ),
    output_format: str = typer.Option(
        "terminal",
        "--output-format",
        "-F",
        help="Output format: terminal (default), json, html.",
    ),
    output_file: Path | None = typer.Option(
        None,
        "--output-file",
        "-O",
        help="Write output to a file (recommended for json or html).",
    ),
    demo: bool = typer.Option(
        False,
        "--demo",
        help="Run with built-in demo data (no GitHub API calls).",
    ),
    show_models: bool = typer.Option(
        False,
        "--show-models",
        "-M",
        help=(
            "Display CHAOSS-aligned metric models (Stability, Sustainability, "
            "Community Engagement, Project Maturity, Contributor Experience)."
        ),
    ),
    show_dependencies: bool = typer.Option(
        False,
        "--show-dependencies",
        "-D",
        help=(
            "Experimental: analyze and display dependency package scores (reference "
            "scores based on lockfile dependencies). Only works when lockfiles are "
            "present in the project directory (uv.lock, poetry.lock, "
            "package-lock.json, etc.)."
        ),
    ),
    profile: str = typer.Option(
        "balanced",
        "--profile",
        "-p",
        help="Scoring profile: balanced (default), security_first, contributor_experience, long_term_stability.",
    ),
    profile_file: Path | None = typer.Option(
        None,
        "--profile-file",
        help="Path to a TOML file with scoring profile definitions.",
    ),
    insecure: bool = typer.Option(
        False,
        "--insecure",
        help="Disable SSL certificate verification for HTTPS requests.",
    ),
    ca_cert: Path | None = typer.Option(
        None,
        "--ca-cert",
        help="Path to custom CA certificate file for SSL verification.",
    ),
    cache_dir: Path | None = typer.Option(
        None,
        "--cache-dir",
        help="Cache directory path (default: ~/.cache/oss-sustain-guard).",
    ),
    cache_ttl: int | None = typer.Option(
        None,
        "--cache-ttl",
        help="Cache TTL in seconds (default: 604800 = 7 days).",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable all caches (local and remote) and perform real-time analysis only.",
    ),
    no_local_cache: bool = typer.Option(
        False,
        "--no-local-cache",
        help="Disable local cache (~/.cache/oss-sustain-guard).",
    ),
    clear_cache_flag: bool = typer.Option(
        False,
        "--clear-cache",
        help="Clear cache and exit.",
    ),
    root_dir: Path = typer.Option(
        Path("."),
        "--root-dir",
        "-r",
        help="Root directory for auto-detection of manifest files (default: current directory).",
    ),
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        "-m",
        help="Path to a specific manifest file (e.g., package.json, requirements.txt, Cargo.toml). Overrides auto-detection.",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-R",
        help="Recursively scan subdirectories for manifest and lock files.",
    ),
    depth: int | None = typer.Option(
        None,
        "--depth",
        "-d",
        help="Maximum directory depth for recursive scanning (default: unlimited).",
    ),
    num_workers: int = typer.Option(
        5,
        "--num-workers",
        "-w",
        help="Maximum number of parallel workers (default: 5, adjust based on GitHub API rate limits).",
    ),
    scan_depth: str = typer.Option(
        "default",
        "--scan-depth",
        help="Data sampling depth: shallow (quick scan, fewer samples), default (balanced), deep (comprehensive), very_deep (maximum detail, most samples). Affects how much data is collected from GitHub/GitLab APIs.",
    ),
    days_lookback: int | None = typer.Option(
        None,
        "--days-lookback",
        help="Only analyze activity from the last N days (e.g., --days-lookback 90 for last 3 months). By default, analyzes all available data within sample limits.",
    ),
):
    """Analyze the sustainability of packages across multiple ecosystems (Python, JavaScript, Go, Rust, PHP, Java, Kotlin, Scala, C#, Ruby, R, Dart, Elixir, Haskell, Perl, Swift)."""
    # Apply config defaults if not specified via CLI
    if verbose is None:
        verbose = is_verbose_enabled()
    if output_style is None:
        output_style = get_output_style()

    # Validate scan depth
    valid_scan_depths = ["shallow", "default", "deep", "very_deep"]
    if scan_depth not in valid_scan_depths:
        console.print(
            f"[red]❌ Invalid scan depth: {scan_depth}[/red]\n"
            f"Valid options: {', '.join(valid_scan_depths)}"
        )
        raise typer.Exit(code=1)

    # Validate days lookback
    if days_lookback is not None and days_lookback < 0:
        console.print(
            f"[red]❌ Days lookback must be non-negative, got {days_lookback}[/red]"
        )
        raise typer.Exit(code=1)

    # Set global scan configuration
    from oss_sustain_guard.config import set_days_lookback, set_scan_depth

    set_scan_depth(scan_depth)
    set_days_lookback(days_lookback)

    # Display scan configuration if verbose
    if verbose:
        console.print(f"[dim]📊 Scan depth: {scan_depth}[/dim]")
        if days_lookback:
            console.print(f"[dim]📅 Time window: last {days_lookback} days[/dim]")
        else:
            console.print("[dim]📅 Time window: all available data[/dim]")

    apply_scoring_profiles(profile_file)

    # Validate and warn about plugin metric weights
    from oss_sustain_guard.metrics import load_metric_specs

    builtin_metrics = {
        "Contributor Redundancy",
        "Maintainer Retention",
        "Recent Activity",
        "Change Request Resolution",
        "Issue Resolution Duration",
        "Funding Signals",
        "Release Rhythm",
        "Security Signals",
        "Contributor Attraction",
        "Contributor Retention",
        "Review Health",
        "Documentation Presence",
        "Code of Conduct",
        "PR Acceptance Ratio",
        "Organizational Diversity",
        "Fork Activity",
        "Project Popularity",
        "License Clarity",
        "PR Responsiveness",
        "Community Health",
        "Build Health",
        "Stale Issue Ratio",
        "PR Merge Speed",
        "Maintainer Load Distribution",
    }

    weights = get_metric_weights(profile)
    metric_specs = load_metric_specs()
    plugin_metrics = [spec for spec in metric_specs if spec.name not in builtin_metrics]

    if plugin_metrics:
        console.print("[yellow]⚠️  Plugin metrics detected:[/yellow]")
        for metric in plugin_metrics:
            weight = weights.get(metric.name, 1)
            if weight == 1:
                console.print(
                    f"   [dim]{metric.name}: using default weight=1 (not explicitly configured)[/dim]"
                )
            else:
                console.print(
                    f"   [cyan]{metric.name}: weight={weight} (configured)[/cyan]"
                )
        console.print()

    # Validate profile
    if profile not in SCORING_PROFILES:
        console.print(
            f"[red]❌ Unknown profile '{profile}'.[/red]",
        )
        console.print(
            f"[dim]Available profiles: {', '.join(SCORING_PROFILES.keys())}[/dim]"
        )
        raise typer.Exit(code=1)

    # Validate output_style
    valid_output_styles = ["compact", "normal", "detail"]
    if output_style not in valid_output_styles:
        console.print(
            f"[red]❌ Unknown output style '{output_style}'.[/red]",
        )
        console.print(f"[dim]Available styles: {', '.join(valid_output_styles)}[/dim]")
        raise typer.Exit(code=1)

    valid_output_formats = ["terminal", "json", "html"]
    if output_format not in valid_output_formats:
        console.print(
            f"[red]❌ Unknown output format '{output_format}'.[/red]",
        )
        console.print(
            f"[dim]Available formats: {', '.join(valid_output_formats)}[/dim]"
        )
        raise typer.Exit(code=1)

    if output_format == "terminal" and output_file:
        console.print(
            "[yellow]ℹ️  --output-file is ignored for terminal output. "
            "Use --output-format json or html to save a report.[/yellow]"
        )

    # Handle --clear-cache option
    if clear_cache_flag:
        cleared = clear_cache()
        console.print(f"[green]✨ Cleared {cleared} cache file(s).[/green]")
        raise typer.Exit(code=0)

    if demo:
        if packages or manifest:
            console.print(
                "[dim]ℹ️  Demo mode ignores package inputs and uses built-in results.[/dim]"
            )
        try:
            demo_results, demo_profile = _load_demo_results()
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            console.print(f"[yellow]⚠️  Unable to load demo data: {exc}[/yellow]")
            raise typer.Exit(code=1) from exc

        demo_notice = (
            "Demo data is a snapshot for illustration and may differ from "
            "current repository status."
        )
        if demo_profile and demo_profile != profile:
            console.print(
                f"[dim]ℹ️  Demo data uses the '{demo_profile}' profile; "
                "--profile is ignored in demo mode.[/dim]"
            )

        console.print(
            "[green]✨ Running in demo mode with built-in sample data.[/green]"
        )
        display_results(
            demo_results,
            show_models=show_models,
            show_dependencies=show_dependencies,
            output_format=output_format,
            output_file=output_file,
            output_style=output_style,
            profile=demo_profile or profile,
            demo_notice=demo_notice,
        )
        await close_async_http_client()
        clear_lockfile_cache()
        raise typer.Exit(code=0)

    # Apply cache configuration
    if cache_dir:
        set_cache_dir(cache_dir)
    if cache_ttl:
        set_cache_ttl(cache_ttl)

    # Configure SSL verification
    if insecure and ca_cert:
        console.print("[red]❌ Cannot use both --insecure and --ca-cert options.[/red]")
        raise typer.Exit(code=1)
    if ca_cert:
        if not ca_cert.exists():
            console.print(f"[red]❌ CA certificate file not found: {ca_cert}[/red]")
            raise typer.Exit(code=1)
        set_verify_ssl(str(ca_cert))
    else:
        set_verify_ssl(not insecure)

    # Determine cache usage flags
    use_cache = not no_cache
    use_local = use_cache and not no_local_cache

    db = load_database(use_cache=use_cache, use_local_cache=use_local, verbose=verbose)
    results_to_display = []
    packages_to_analyze: list[tuple[str, str]] = []  # (ecosystem, package_name)
    direct_packages: list[tuple[str, str]] = []

    # Handle --manifest option (direct manifest file specification)
    if manifest:
        manifest = manifest.resolve()
        if not manifest.exists():
            console.print(f"[yellow]⚠️  Manifest file not found: {manifest}[/yellow]")
            console.print("[dim]Please check the file path and try again.[/dim]")
            raise typer.Exit(code=1)
        if not manifest.is_file():
            console.print(f"[yellow]⚠️  Path is not a file: {manifest}[/yellow]")
            console.print("[dim]Please provide a path to a manifest file.[/dim]")
            raise typer.Exit(code=1)

        console.print(f"📋 Reading manifest file: {manifest}")

        # Detect ecosystem from manifest filename
        manifest_name = manifest.name
        detected_eco = None

        # Try to match with known manifest file patterns
        for eco in [
            "python",
            "javascript",
            "dart",
            "elixir",
            "haskell",
            "perl",
            "r",
            "ruby",
            "rust",
            "go",
            "php",
            "java",
            "csharp",
            "swift",
        ]:
            resolver = get_resolver(eco)
            manifest_files = await resolver.get_manifest_files() if resolver else []
            if manifest_name in manifest_files:
                detected_eco = eco
                break

        if not detected_eco:
            console.print(
                f"[yellow]⚠️  Could not detect ecosystem from manifest file: {manifest_name}[/yellow]"
            )
            console.print(
                "[dim]Supported manifest files:[/dim] package.json, requirements.txt, pyproject.toml, Cargo.toml, go.mod, composer.json, pom.xml, build.gradle, build.gradle.kts, build.sbt, Gemfile, packages.config, DESCRIPTION, Package.swift, cabal.project, stack.yaml, package.yaml, pubspec.yaml, mix.exs, cpanfile"
            )
            raise typer.Exit(code=1)

        console.print(f"✅ Detected ecosystem: {detected_eco}")

        # Parse manifest file
        resolver = get_resolver(detected_eco)
        if not resolver:
            console.print(
                f"[yellow]⚠️  Unable to process {detected_eco} packages at this time[/yellow]"
            )
            raise typer.Exit(code=1)

        try:
            manifest_packages = await resolver.parse_manifest(str(manifest))
            console.print(
                f"   Found {len(manifest_packages)} package(s) in {manifest_name}"
            )
            for pkg_info in manifest_packages:
                packages_to_analyze.append((detected_eco, pkg_info.name))
                direct_packages.append((detected_eco, pkg_info.name))
        except Exception as e:
            console.print(f"[yellow]⚠️  Unable to parse {manifest_name}: {e}[/yellow]")
            console.print(
                "[dim]The file may be malformed or in an unexpected format.[/dim]"
            )
            raise typer.Exit(code=1) from None

    # Validate and resolve root directory (only if not using --manifest)
    elif (
        not packages and not manifest
    ):  # Only validate root_dir if not using --manifest and no packages specified
        root_dir = root_dir.resolve()
        if not root_dir.exists():
            console.print(f"[yellow]⚠️  Directory not found: {root_dir}[/yellow]")
            console.print("[dim]Please check the path and try again.[/dim]")
            raise typer.Exit(code=1)
        if not root_dir.is_dir():
            console.print(f"[yellow]⚠️  Path is not a directory: {root_dir}[/yellow]")
            console.print("[dim]Please provide a directory path with --root-dir.[/dim]")
            raise typer.Exit(code=1)

        # Auto-detect from manifest files in root_dir
        if recursive:
            depth_msg = (
                f" (depth: {depth})" if depth is not None else " (unlimited depth)"
            )
            console.print(
                f"🔍 No packages specified. Recursively scanning {root_dir}{depth_msg}..."
            )
        else:
            console.print(
                f"🔍 No packages specified. Auto-detecting from manifest files in {root_dir}..."
            )

        detected_ecosystems = await detect_ecosystems(
            str(root_dir), recursive=recursive, max_depth=depth
        )
        if detected_ecosystems:
            console.print(f"✅ Detected ecosystems: {', '.join(detected_ecosystems)}")

            # Find all manifest files (recursively if requested)
            manifest_files_dict = await find_manifest_files(
                str(root_dir), recursive=recursive, max_depth=depth
            )

            for detected_eco, manifest_paths in manifest_files_dict.items():
                resolver = get_resolver(detected_eco)
                if not resolver:
                    continue

                for manifest_path in manifest_paths:
                    relative_path = (
                        manifest_path.relative_to(root_dir)
                        if manifest_path.is_relative_to(root_dir)
                        else manifest_path
                    )
                    console.print(f"📋 Found manifest file: {relative_path}")
                    # Parse manifest to extract dependencies
                    try:
                        manifest_packages = await resolver.parse_manifest(
                            str(manifest_path)
                        )
                        console.print(
                            f"   Found {len(manifest_packages)} package(s) in {manifest_path.name}"
                        )
                        for pkg_info in manifest_packages:
                            packages_to_analyze.append((detected_eco, pkg_info.name))
                            direct_packages.append((detected_eco, pkg_info.name))
                    except Exception as e:
                        console.print(
                            f"   [dim]Note: Unable to parse {manifest_path.name} - {e}[/dim]"
                        )

            # If --include-lock is specified, also detect and parse lockfiles
            if include_lock:
                if recursive:
                    depth_msg = (
                        f" (depth: {depth})"
                        if depth is not None
                        else " (unlimited depth)"
                    )
                    console.print(
                        f"🔒 Recursively scanning for lockfiles{depth_msg}..."
                    )

                # Find all lockfiles (recursively if requested)
                lockfiles_dict = await find_lockfiles(
                    str(root_dir), recursive=recursive, max_depth=depth
                )

                for detected_eco, lockfile_paths in lockfiles_dict.items():
                    resolver = get_resolver(detected_eco)
                    if not resolver:
                        continue

                    if lockfile_paths:
                        relative_names = [
                            lf.relative_to(root_dir)
                            if lf.is_relative_to(root_dir)
                            else lf
                            for lf in lockfile_paths
                        ]
                        console.print(
                            f"🔒 Found lockfile(s) for {detected_eco}: {', '.join(str(l) for l in relative_names)}"
                        )
                        for lockfile in lockfile_paths:
                            try:
                                lock_packages = await resolver.parse_lockfile(
                                    str(lockfile)
                                )
                                console.print(
                                    f"   Found {len(lock_packages)} package(s) in {lockfile.name}"
                                )
                                for pkg_info in lock_packages:
                                    packages_to_analyze.append(
                                        (detected_eco, pkg_info.name)
                                    )
                            except Exception as e:
                                console.print(
                                    f"   [yellow]Note: Unable to parse {lockfile.name}: {e}[/yellow]"
                                )
        else:
            # No manifest files found - silently exit (useful for pre-commit hooks)
            raise typer.Exit(code=0)

    # Process package arguments (if packages specified and not using --manifest)
    elif packages and not manifest:
        # Process package arguments
        if len(packages) == 1 and Path(packages[0]).is_file():
            console.print(f"📄 Reading packages from [bold]{packages[0]}[/bold]")
            with open(packages[0], "r", encoding="utf-8") as f:
                # Basic parsing, ignores versions and comments
                package_list = [
                    line.strip().split("==")[0].split("#")[0]
                    for line in f
                    if line.strip() and not line.startswith("#")
                ]
                for pkg in package_list:
                    eco, pkg_name = parse_package_spec(pkg)
                    if ecosystem != "auto":
                        eco = ecosystem
                    packages_to_analyze.append((eco, pkg_name))
                    direct_packages.append((eco, pkg_name))
        else:
            # Parse command-line package specifications
            for pkg_spec in packages:
                eco, pkg_name = parse_package_spec(pkg_spec)
                # Override ecosystem if specified
                if ecosystem != "auto" and ":" not in pkg_spec:
                    eco = ecosystem
                packages_to_analyze.append((eco, pkg_name))
                direct_packages.append((eco, pkg_name))

    # Remove duplicates while preserving order (package name level only)
    packages_to_analyze = _dedupe_packages(packages_to_analyze)
    direct_packages = _dedupe_packages(direct_packages)

    # Dedupe by resolved repository to avoid analyzing the same repo multiple times
    # But only do this for the analysis phase, not for dependency tracking
    repo_seen = set()
    repo_to_pkg: dict[str, tuple[str, str]] = {}  # repo_key -> (ecosystem, package)
    unique_packages = []
    duplicate_count = 0

    for eco, pkg in packages_to_analyze:
        resolver = get_resolver(eco)
        if not resolver:
            unique_packages.append((eco, pkg))
            continue
        try:
            repo_info = await resolver.resolve_repository(pkg)
            if repo_info:
                key = f"{repo_info.owner}/{repo_info.name}"
                if key not in repo_seen:
                    repo_seen.add(key)
                    repo_to_pkg[key] = (eco, pkg)
                    unique_packages.append((eco, pkg))
                else:
                    # If duplicate repo, skip adding to unique_packages for analysis
                    duplicate_count += 1
                    console.print(
                        f"  -> [dim]Skipping [bold yellow]{eco}:{pkg}[/bold yellow] "
                        f"(maps to same repository as {repo_to_pkg[key][0]}:{repo_to_pkg[key][1]})[/dim]"
                    )
            else:
                unique_packages.append((eco, pkg))
        except Exception:
            unique_packages.append((eco, pkg))

    packages_to_analyze = unique_packages

    if duplicate_count > 0:
        console.print(
            f"[dim]ℹ️  Skipped {duplicate_count} package(s) mapping to duplicate repositories[/dim]\n"
        )

    console.print(f"🔍 Analyzing {len(packages_to_analyze)} package(s)...")

    # Find lockfiles for dependency analysis (if requested)
    lockfiles_map: dict[str, Path] = {}  # ecosystem -> lockfile path
    if show_dependencies:
        lockfiles_dict = await find_lockfiles(
            str(root_dir), recursive=recursive, max_depth=depth
        )
        for detected_eco, lockfile_paths in lockfiles_dict.items():
            if lockfile_paths:
                lockfiles_map[detected_eco] = lockfile_paths[0]  # Use first found

        # Warn if --show-dependencies was requested but no lockfiles found
        if not lockfiles_map:
            console.print(
                "[yellow]ℹ️  --show-dependencies specified but no lockfiles found in [bold]"
                f"{root_dir}[/bold][/yellow]"
            )
            console.print(
                "[dim]   Dependency scores are only available when analyzing projects with lockfiles.[/dim]"
            )

    excluded_count = 0
    # Filter out excluded packages
    packages_to_process = []
    for eco, pkg_name in packages_to_analyze:
        if is_package_excluded(pkg_name):
            excluded_count += 1
            console.print(
                f"  -> Skipping [bold yellow]{pkg_name}[/bold yellow] (excluded)"
            )
        else:
            packages_to_process.append((eco, pkg_name))

    result_map: dict[tuple[str, str], AnalysisResult] = {}

    # Parallel analysis for multiple packages
    if packages_to_process:
        lockfile = lockfiles_map if show_dependencies else None

        # Use parallel processing for better performance
        results, verbose_logs = await analyze_packages_parallel(
            packages_to_process,
            db,
            profile,
            show_dependencies,
            lockfile,
            verbose,
            use_local,
            max_workers=num_workers,
        )

        # Display verbose logs after progress bar is done
        if verbose and verbose_logs:
            for _db_key, logs in verbose_logs.items():
                for log in logs:
                    console.print(log)

        result_map = {
            packages_to_process[idx]: result
            for idx, result in enumerate(results)
            if result is not None
        }

        # Filter out None results
        results_to_display = [r for r in results if r is not None]

    dependency_summary = None
    summary_packages = direct_packages or packages_to_process
    if show_dependencies and lockfiles_map and summary_packages:
        dependency_summary = _build_dependency_summary(summary_packages, result_map)

    if results_to_display:
        display_results(
            results_to_display,
            show_models=show_models,
            show_dependencies=show_dependencies,
            output_format=output_format,
            output_file=output_file,
            output_style=output_style,
            profile=profile,
            dependency_summary=dependency_summary,
        )
        if excluded_count > 0:
            console.print(
                f"\n⏭️  Skipped {excluded_count} excluded package(s).",
                style="yellow",
            )

    else:
        console.print("No results to display.")

    # Clean up HTTP clients and lockfile cache
    clear_lockfile_cache()


@app.command()
def cache_stats(
    ecosystem: str | None = typer.Argument(
        None,
        help="Specific ecosystem to check (python, javascript, rust, etc.), or omit for all ecosystems.",
    ),
):
    """Display cache statistics."""
    stats = get_cache_stats(ecosystem, expected_version=ANALYSIS_VERSION)

    if not stats["exists"]:
        console.print(
            f"[yellow]Cache directory does not exist: {stats['cache_dir']}[/yellow]"
        )
        return

    console.print("[bold cyan]Cache Statistics[/bold cyan]")
    console.print(f"  Directory: {stats['cache_dir']}")
    console.print(f"  Total entries: {stats['total_entries']}")
    console.print(f"  Valid entries: [green]{stats['valid_entries']}[/green]")
    console.print(f"  Expired entries: [yellow]{stats['expired_entries']}[/yellow]")

    if stats["ecosystems"]:
        console.print("\n[bold cyan]Per-Ecosystem Breakdown:[/bold cyan]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Ecosystem", style="cyan")
        table.add_column("Total", justify="right")
        table.add_column("Valid", justify="right", style="green")
        table.add_column("Expired", justify="right", style="yellow")

        for eco, eco_stats in stats["ecosystems"].items():
            table.add_row(
                eco,
                str(eco_stats["total"]),
                str(eco_stats["valid"]),
                str(eco_stats["expired"]),
            )

        console.print(table)


@app.command(name="clear-cache")
def clear_cache_command(
    ecosystem: str | None = typer.Argument(
        None,
        help="Specific ecosystem to clear (python, javascript, rust, etc.), or omit to clear all ecosystems.",
    ),
    cache_dir: Path | None = typer.Option(
        None,
        "--cache-dir",
        help="Cache directory path (default: ~/.cache/oss-sustain-guard).",
    ),
    expired_only: bool = typer.Option(
        False,
        "--expired-only",
        help="Remove only expired entries, keeping valid ones.",
    ),
):
    """Clear the local cache.

    Examples:
      os4g clear-cache                    # Clear all caches
      os4g clear-cache python             # Clear only Python cache
      os4g clear-cache javascript         # Clear only JavaScript cache
      os4g clear-cache --expired-only     # Remove only expired entries
      os4g clear-cache python --expired-only  # Remove expired Python entries only
    """
    if cache_dir:
        set_cache_dir(cache_dir)

    if expired_only:
        cleared = clear_expired_cache(ecosystem, expected_version=ANALYSIS_VERSION)
        entry_word = "entry" if cleared == 1 else "entries"

        if cleared == 0:
            if ecosystem:
                console.print(
                    f"[yellow]ℹ️  No expired cache entries found for ecosystem: {ecosystem}[/yellow]"
                )
            else:
                console.print("[yellow]ℹ️  No expired cache entries found[/yellow]")
        else:
            if ecosystem:
                console.print(
                    f"[green]✨ Cleared {cleared} expired {entry_word} for {ecosystem}[/green]"
                )
            else:
                console.print(
                    f"[green]✨ Cleared {cleared} expired {entry_word}[/green]"
                )
    else:
        cleared = clear_cache(ecosystem)

        if cleared == 0:
            if ecosystem:
                console.print(
                    f"[yellow]ℹ️  No cache files found for ecosystem: {ecosystem}[/yellow]"
                )
            else:
                console.print("[yellow]ℹ️  No cache files found[/yellow]")
        else:
            if ecosystem:
                console.print(
                    f"[green]✨ Cleared {cleared} cache file(s) for {ecosystem}[/green]"
                )
            else:
                console.print(f"[green]✨ Cleared {cleared} cache file(s)[/green]")


@app.command(name="list-cache")
def list_cache_command(
    ecosystem: str | None = typer.Argument(
        None,
        help="Specific ecosystem to list (python, javascript, rust, etc.), or omit to list all ecosystems.",
    ),
    cache_dir: Path | None = typer.Option(
        None,
        "--cache-dir",
        help="Cache directory path (default: ~/.cache/oss-sustain-guard).",
    ),
    show_all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Show all cached packages including expired ones (default: only valid packages).",
    ),
    sort_by: str = typer.Option(
        "score",
        "--sort",
        "-s",
        help="Sort by: score, name, ecosystem, date (default: score).",
    ),
    profile: str = typer.Option(
        "balanced",
        "--profile",
        "-p",
        help="Scoring profile for score calculation: balanced (default), security_first, contributor_experience, long_term_stability.",
    ),
    profile_file: Path | None = typer.Option(
        None,
        "--profile-file",
        help="Path to a TOML file with scoring profile definitions.",
    ),
    limit: int | None = typer.Option(
        100,
        "--limit",
        "-l",
        help="Maximum number of packages to display (default: 100). Set to 0 or None for unlimited.",
    ),
    filter_keyword: str | None = typer.Option(
        None,
        "--filter",
        "-f",
        help="Filter packages by keyword in package name or repository URL (case-insensitive).",
    ),
):
    """List cached packages in a table format.

    Examples:
      os4g list-cache                            # List top 100 valid cached packages
      os4g list-cache python                     # List only Python packages
      os4g list-cache --all                      # Include expired cache entries
      os4g list-cache --sort name                # Sort by package name
      os4g list-cache --sort date                # Sort by cache date
      os4g list-cache --profile security_first   # Use security_first profile for scoring
      os4g list-cache --limit 50                 # Show top 50 packages
      os4g list-cache --limit 0                  # Show all packages (unlimited)
      os4g list-cache --filter requests          # Filter packages containing 'requests'
      os4g list-cache --filter github.com/psf    # Filter by repository URL
    """
    if cache_dir:
        set_cache_dir(cache_dir)

    apply_scoring_profiles(profile_file)

    # Validate profile
    if profile not in SCORING_PROFILES:
        console.print(
            f"[red]❌ Unknown profile '{profile}'.[/red]",
        )
        console.print(
            f"[dim]Available profiles: {', '.join(SCORING_PROFILES.keys())}[/dim]"
        )
        raise typer.Exit(code=1)

    packages = get_cached_packages(ecosystem, expected_version=ANALYSIS_VERSION)

    if not packages:
        if ecosystem:
            console.print(
                f"[yellow]ℹ️  No cached packages found for ecosystem: {ecosystem}[/yellow]"
            )
        else:
            console.print("[yellow]ℹ️  No cached packages found[/yellow]")
        console.print(
            "[dim]Run 'os4g check <package>' to analyze and cache packages.[/dim]"
        )
        return

    # Recalculate total_score for each package based on metrics using specified profile
    for pkg in packages:
        metrics_data = pkg.get("metrics", [])
        if metrics_data:
            # Convert dict metrics to Metric objects
            metrics = [
                Metric(
                    name=m.get("name", ""),
                    score=m.get("score", 0),
                    max_score=m.get("max_score", 0),
                    message=m.get("message", ""),
                    risk=m.get("risk", "None"),
                )
                for m in metrics_data
            ]
            # Recalculate with specified profile
            pkg["total_score"] = compute_weighted_total_score(metrics, profile)
        else:
            pkg["total_score"] = 0

    # Filter by validity if not showing all
    if not show_all:
        packages = [p for p in packages if p["is_valid"]]
        if not packages:
            console.print(
                "[yellow]ℹ️  No valid cached packages found (all expired)[/yellow]"
            )
            console.print(
                "[dim]Use --all to see expired entries or run analysis to refresh cache.[/dim]"
            )
            return

    # Apply keyword filter if specified
    total_before_filter = len(packages)
    if filter_keyword:
        filter_lower = filter_keyword.lower()
        packages = [
            p
            for p in packages
            if filter_lower in p["package_name"].lower()
            or filter_lower in p["github_url"].lower()
        ]
        if not packages:
            console.print(
                f"[yellow]ℹ️  No packages found matching filter: '{filter_keyword}'[/yellow]"
            )
            console.print(
                f"[dim]Total packages before filter: {total_before_filter}[/dim]"
            )
            return

    # Sort packages
    if sort_by == "score":
        packages.sort(key=lambda p: p["total_score"], reverse=True)
    elif sort_by == "name":
        packages.sort(key=lambda p: (p["ecosystem"], p["package_name"]))
    elif sort_by == "ecosystem":
        packages.sort(key=lambda p: (p["ecosystem"], p["total_score"]), reverse=True)
    elif sort_by == "date":
        packages.sort(key=lambda p: p["fetched_at"], reverse=True)
    else:
        console.print(
            f"[yellow]⚠️  Unknown sort option: {sort_by}. Using default (score).[/yellow]"
        )
        packages.sort(key=lambda p: p["total_score"], reverse=True)

    # Apply limit if specified (0 or None means unlimited)
    total_count = len(packages)
    limited = False
    if limit and limit > 0 and len(packages) > limit:
        packages = packages[:limit]
        limited = True

    # Display table
    title = "Cached Packages" if show_all else "Valid Cached Packages"
    if ecosystem:
        title += f" ({ecosystem})"
    # Show profile if not default
    if profile != "balanced":
        title += f" [Profile: {profile}]"

    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Package", style="cyan", no_wrap=True)
    table.add_column("Ecosystem", style="blue", no_wrap=True)
    table.add_column("Score", justify="center", style="magenta")
    table.add_column("Status", justify="left")
    table.add_column("Cached At", justify="left", style="dim")
    if show_all:
        table.add_column("Valid", justify="center")

    for pkg in packages:
        score = pkg["total_score"]

        # Determine status color and text
        if score >= 80:
            status_color = "green"
            status_text = "Healthy"
        elif score >= 50:
            status_color = "yellow"
            status_text = "Monitor"
        else:
            status_color = "red"
            status_text = "Needs support"

        # Format cached date
        try:
            fetched_dt = datetime.fromisoformat(pkg["fetched_at"])
            cached_str = fetched_dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            cached_str = "unknown"

        row = [
            pkg["package_name"],
            pkg["ecosystem"],
            f"[{status_color}]{score}/100[/{status_color}]",
            f"[{status_color}]{status_text}[/{status_color}]",
            cached_str,
        ]

        if show_all:
            valid_icon = "✓" if pkg["is_valid"] else "✗"
            valid_color = "green" if pkg["is_valid"] else "red"
            row.append(f"[{valid_color}]{valid_icon}[/{valid_color}]")

        table.add_row(*row)

    console.print(table)

    # Display summary information
    summary_parts = [f"Showing: {len(packages)} package(s)"]

    if limited:
        summary_parts.append(f"(limited from {total_count})")

    if filter_keyword:
        summary_parts.append(f"(filtered by: '{filter_keyword}')")

    console.print(f"\n[dim]{' '.join(summary_parts)}[/dim]")

    if not show_all:
        all_packages = get_cached_packages(ecosystem, expected_version=ANALYSIS_VERSION)
        expired_count = len(all_packages) - total_count
        if expired_count > 0:
            console.print(
                f"[dim]({expired_count} expired package(s) hidden. Use --all to show them.)[/dim]"
            )


@app.command()
def gratitude(
    top_n: int = typer.Option(
        3,
        "--top",
        "-t",
        help="Number of top projects to display for gratitude.",
    ),
    insecure: bool = typer.Option(
        False,
        "--insecure",
        help="Disable SSL certificate verification for development/testing.",
    ),
):
    """
    🎁 Gratitude Vending Machine - Support community-driven OSS projects.

    Displays top community-driven projects that need support based on:
    - Dependency impact (how many projects depend on it)
    - Maintainer load (low bus factor, review backlog)
    - Activity level (recent contributions)

    Opens funding links so you can show your appreciation!
    """
    import webbrowser

    # Set SSL verification flag
    if insecure:
        set_verify_ssl(False)

    console.print("\n[bold cyan]🎁 Gratitude Vending Machine[/bold cyan]")
    console.print(
        "[dim]Loading community projects that could use your support...[/dim]\n"
    )

    # Load database
    db = load_database(use_cache=True)

    if not db:
        console.print(
            "[yellow]No database available. Please run analysis first.[/yellow]"
        )
        return

    # Calculate support priority for each project
    support_candidates = []

    for key, data in db.items():
        # Skip if no funding links
        funding_links = data.get("funding_links", [])
        if not funding_links:
            continue

        # Only show community-driven projects (not corporate-backed)
        is_community = data.get("is_community_driven", False)
        if not is_community:
            continue

        # Calculate total_score from metrics (since it's not stored in cache)
        metrics_data = data.get("metrics", [])
        if not metrics_data:
            continue

        # Convert dict metrics to Metric objects
        metric_objects = [
            Metric(
                name=m.get("name", ""),
                score=m.get("score", 0),
                max_score=m.get("max_score", 0),
                message=m.get("message", ""),
                risk=m.get("risk", "None"),
            )
            for m in metrics_data
        ]

        # Compute total score using balanced profile (default for gratitude)
        total_score = compute_weighted_total_score(metric_objects, profile="balanced")

        # Find specific metrics that indicate need for support
        bus_factor_score = 10  # Default max (0-10 scale)
        maintainer_retention_score = 10  # Default max (0-10 scale)

        for metric in metrics_data:
            metric_name = metric.get("name", "")
            if "Bus Factor" in metric_name or "Contributor Redundancy" in metric_name:
                bus_factor_score = metric.get("score", 10)
            elif (
                "Maintainer Retention" in metric_name
                or "Maintainer Drain" in metric_name
            ):
                maintainer_retention_score = metric.get("score", 10)

        # Priority = (100 - total_score) + (10 - bus_factor) + (10 - maintainer_retention)
        # Higher priority = needs more support
        priority = (
            (100 - total_score)
            + (10 - bus_factor_score)
            + (10 - maintainer_retention_score)
        )

        support_candidates.append(
            {
                "key": key,
                "repo_url": data.get("github_url", data.get("repo_url", "")),
                "total_score": total_score,
                "priority": priority,
                "funding_links": funding_links,
                "bus_factor_score": bus_factor_score,
                "maintainer_retention_score": maintainer_retention_score,
            }
        )

    if not support_candidates:
        console.print(
            "[yellow]No community-driven projects with funding links found.[/yellow]"
        )
        console.print("[dim]Try running analysis on more packages first.[/dim]")
        return

    # Sort by priority (higher = needs more support)
    support_candidates.sort(key=lambda x: x["priority"], reverse=True)

    # Display top N
    top_projects = support_candidates[:top_n]

    # Show informative message about how many were requested vs found
    if len(support_candidates) < top_n:
        console.print(
            f"[bold green]Found {len(support_candidates)} project(s) that would appreciate your support:[/bold green]"
        )
        console.print(
            f"[dim](Requested top {top_n}, but only {len(support_candidates)} community-driven project(s) with funding links available)[/dim]\n"
        )
    else:
        console.print(
            f"[bold green]Top {len(top_projects)} projects that would appreciate your support:[/bold green]\n"
        )

    for i, project in enumerate(top_projects, 1):
        ecosystem, package_name = project["key"].split(":", 1)
        repo_url = project["repo_url"]
        total_score = project["total_score"]

        # Determine health status
        if total_score >= 80:
            status_color = "green"
            status_text = "Healthy"
        elif total_score >= 50:
            status_color = "yellow"
            status_text = "Monitor"
        else:
            status_color = "red"
            status_text = "Needs support"

        console.print(f"[bold cyan]{i}. {package_name}[/bold cyan] ({ecosystem})")
        console.print(f"   Repository: {repo_url}")
        console.print(
            f"   Health Score: [{status_color}]{total_score}/100[/{status_color}] ({status_text})"
        )
        console.print(f"   Contributor Redundancy: {project['bus_factor_score']}/10")
        console.print(
            f"   Maintainer Retention: {project['maintainer_retention_score']}/10"
        )

        # Display funding links
        funding_links = project["funding_links"]
        console.print("   [bold magenta]💝 Support options:[/bold magenta]")
        for link in funding_links:
            platform = link.get("platform", "Unknown")
            url = link.get("url", "")
            console.print(f"      • {platform}: {url}")

        console.print()

    # Interactive prompt
    console.print("[bold yellow]Would you like to open a funding link?[/bold yellow]")
    console.print(
        "Enter project number (1-{}) to open funding link, or 'q' to quit: ".format(
            len(top_projects)
        ),
        end="",
    )

    try:
        choice = input().strip().lower()

        if choice == "q":
            console.print(
                "[dim]Thank you for considering supporting OSS maintainers! 🙏[/dim]"
            )
            return

        try:
            project_idx = int(choice) - 1
            if 0 <= project_idx < len(top_projects):
                selected_project = top_projects[project_idx]
                funding_links = selected_project["funding_links"]

                if len(funding_links) == 1:
                    # Only one link, open it directly
                    url = funding_links[0]["url"]
                    console.print(
                        f"\n[green]Opening {funding_links[0]['platform']}...[/green]"
                    )
                    webbrowser.open(url)
                    console.print(
                        "[dim]Thank you for supporting OSS maintainers! 🙏[/dim]"
                    )
                else:
                    # Multiple links, ask which one
                    console.print("\n[bold]Select funding platform:[/bold]")
                    for i, link in enumerate(funding_links, 1):
                        console.print(f"{i}. {link['platform']}")
                    console.print("Enter platform number: ", end="")

                    platform_choice = input().strip()
                    platform_idx = int(platform_choice) - 1

                    if 0 <= platform_idx < len(funding_links):
                        url = funding_links[platform_idx]["url"]
                        platform = funding_links[platform_idx]["platform"]
                        console.print(f"\n[green]Opening {platform}...[/green]")
                        webbrowser.open(url)
                        console.print(
                            "[dim]Thank you for supporting OSS maintainers! 🙏[/dim]"
                        )
                    else:
                        console.print("[yellow]Invalid platform number.[/yellow]")
            else:
                console.print("[yellow]Invalid project number.[/yellow]")
        except ValueError:
            console.print(
                "[yellow]Invalid input. Please enter a number or 'q'.[/yellow]"
            )
    except (KeyboardInterrupt, EOFError):
        console.print(
            "\n[dim]Cancelled. Thank you for considering supporting OSS maintainers! 🙏[/dim]"
        )


# --- Dependency Graph Visualization ---


async def batch_analyze_packages(
    packages: list[str],
    db: dict,
    profile: str = "balanced",
    verbose: bool = False,
    use_local_cache: bool = True,
    max_workers: int = 5,
) -> dict[str, AnalysisResult | None]:
    """
    Analyze multiple packages in parallel, using cache when available.

    Args:
        packages: List of package names to analyze
        db: Cached database dictionary
        profile: Scoring profile to use
        verbose: If True, display cache source information
        use_local_cache: If False, skip local cache lookup
        max_workers: Maximum number of parallel workers

    Returns:
        Dict mapping package names to AnalysisResult or None if analysis failed
    """
    results: dict[str, AnalysisResult | None] = {}

    # Build package data list with (ecosystem, package_name) tuples
    packages_data: list[tuple[str, str]] = []
    for pkg_name in packages:
        # Parse package specification to get ecosystem
        ecosystem, package = parse_package_spec(pkg_name)
        packages_data.append((ecosystem, package))

    # Use the parallel analysis function from check command
    analyzed_results, _ = await analyze_packages_parallel(
        packages_data,
        db,
        profile=profile,
        show_dependencies=False,
        lockfile_path=None,
        verbose=verbose,
        use_local_cache=use_local_cache,
        max_workers=max_workers,
    )

    # Map results back to package names
    for idx, (_eco, pkg) in enumerate(packages_data):
        result = analyzed_results[idx]
        # Use the original package name (without ecosystem prefix)
        results[pkg] = result

    return results


@app.command()
@syncify
async def graph(
    lockfile: Path = typer.Argument(
        ...,
        help="Path to lockfile (requirements.txt, package.json, Cargo.lock, etc.)",
    ),
    output: str = typer.Option(
        "dependency_graph.html",
        "--output",
        "-o",
        help="Output file path (HTML or JSON)",
    ),
    profile: str = typer.Option(
        "balanced",
        "--profile",
        "-p",
        help=f"Scoring profile ({', '.join(SCORING_PROFILES.keys())})",
    ),
    profile_file: Path | None = typer.Option(
        None,
        "--profile-file",
        help="Path to a TOML file with scoring profile definitions.",
    ),
    direct_only: bool = typer.Option(
        False,
        "--direct-only",
        help="Show only direct dependencies (excludes transitive)",
    ),
    max_depth: int | None = typer.Option(
        None,
        "--max-depth",
        help="Maximum dependency depth to include (e.g., 1 for direct only, 2 for direct + first level transitive)",
    ),
    verbose: bool | None = typer.Option(
        None,
        "--verbose",
        "-v",
        help="Enable verbose logging (cache operations, metric reconstruction details). If not specified, uses config file default.",
    ),
    insecure: bool = typer.Option(
        False,
        "--insecure",
        help="Disable SSL certificate verification for HTTPS requests.",
    ),
    ca_cert: Path | None = typer.Option(
        None,
        "--ca-cert",
        help="Path to custom CA certificate file for SSL verification.",
    ),
    cache_dir: Path | None = typer.Option(
        None,
        "--cache-dir",
        help="Cache directory path (default: ~/.cache/oss-sustain-guard).",
    ),
    cache_ttl: int | None = typer.Option(
        None,
        "--cache-ttl",
        help="Cache TTL in seconds (default: 604800 = 7 days).",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable all caches (local and remote) and perform real-time analysis only.",
    ),
    no_local_cache: bool = typer.Option(
        False,
        "--no-local-cache",
        help="Disable local cache (~/.cache/oss-sustain-guard).",
    ),
    num_workers: int = typer.Option(
        5,
        "--num-workers",
        "-w",
        help="Maximum number of parallel workers (default: 5, adjust based on GitHub API rate limits).",
    ),
    scan_depth: str = typer.Option(
        "default",
        "--scan-depth",
        help="Data sampling depth: shallow (quick scan, fewer samples), default (balanced), deep (comprehensive), very_deep (maximum detail, most samples). Affects how much data is collected from GitHub/GitLab APIs.",
    ),
    days_lookback: int | None = typer.Option(
        None,
        "--days-lookback",
        help="Only analyze activity from the last N days (e.g., --days-lookback 90 for last 3 months). By default, analyzes all available data within sample limits.",
    ),
) -> None:
    """
    Generate interactive dependency graph visualization.

    Analyzes lockfile dependencies and creates an interactive graph showing
    package relationships colored by sustainability score.

    Example:
        osg graph requirements.txt --output=graph.html
        osg graph package.json --output=graph.json --profile=security
        osg graph package.json --direct-only
        osg graph package.json --max-depth=2
    """
    # Apply config defaults if not specified via CLI
    if verbose is None:
        verbose = is_verbose_enabled()

    # Validate scan depth
    valid_scan_depths = ["shallow", "default", "deep", "very_deep"]
    if scan_depth not in valid_scan_depths:
        console.print(
            f"[red]Invalid scan depth: {scan_depth}. Must be one of: {', '.join(valid_scan_depths)}[/red]"
        )
        raise typer.Exit(code=1)

    # Validate days lookback
    if days_lookback is not None and days_lookback < 0:
        console.print(
            "[red]Invalid days-lookback value. Must be a positive integer.[/red]"
        )
        raise typer.Exit(code=1)

    # Set global scan configuration
    from oss_sustain_guard.config import set_days_lookback, set_scan_depth

    set_scan_depth(scan_depth)
    set_days_lookback(days_lookback)

    # Display scan configuration if verbose
    if verbose:
        console.print(f"[dim]Scan depth: {scan_depth}[/dim]")
        if days_lookback:
            console.print(f"[dim]Days lookback: {days_lookback}[/dim]")

    # Apply scoring profile configuration
    apply_scoring_profiles(profile_file)

    # Validate profile
    if profile not in SCORING_PROFILES:
        console.print(
            f"[red]Invalid profile: {profile}. Available profiles: "
            f"{', '.join(SCORING_PROFILES.keys())}[/red]"
        )
        raise typer.Exit(code=1)

    # Apply cache configuration
    if cache_dir:
        set_cache_dir(cache_dir)
    if cache_ttl:
        set_cache_ttl(cache_ttl)

    # Configure SSL verification
    if insecure and ca_cert:
        console.print(
            "[yellow]⚠️  Both --insecure and --ca-cert specified. Using --ca-cert.[/yellow]"
        )
    if ca_cert:
        if not ca_cert.exists():
            console.print(f"[red]CA certificate file not found: {ca_cert}[/red]")
            raise typer.Exit(code=1)
        set_verify_ssl(str(ca_cert))
    else:
        set_verify_ssl(not insecure)

    if not lockfile.exists():
        console.print(f"[red]Error: Lockfile not found: {lockfile}[/red]")
        raise typer.Exit(1)

    # Determine cache usage flags
    use_cache = not no_cache
    use_local = use_cache and not no_local_cache

    # Load database with cache configuration
    db = load_database(use_cache=use_cache, use_local_cache=use_local, verbose=verbose)

    console.print(f"[cyan]Parsing lockfile: {lockfile}[/cyan]")

    # Parse dependencies
    dep_graphs = get_all_dependencies([lockfile])
    if not dep_graphs:
        console.print("[red]Error: Could not parse lockfile[/red]")
        raise typer.Exit(1)

    dep_graph = dep_graphs[0]
    console.print(
        f"[cyan]Found {len(dep_graph.direct_dependencies)} direct and "
        f"{len(dep_graph.transitive_dependencies)} transitive dependencies[/cyan]"
    )

    # Apply filters to dependency list
    all_deps_list = dep_graph.direct_dependencies + dep_graph.transitive_dependencies

    if direct_only:
        all_deps_list = [dep for dep in all_deps_list if dep.is_direct]
        console.print(
            f"[cyan]Filtering to {len(all_deps_list)} direct dependencies only[/cyan]"
        )

    if max_depth is not None:
        all_deps_list = [dep for dep in all_deps_list if dep.depth <= max_depth]
        console.print(
            f"[cyan]Filtering to depth <= {max_depth}: {len(all_deps_list)} packages[/cyan]"
        )

    # Collect all packages to analyze
    all_packages = [dep.name for dep in all_deps_list]

    # Run batch analysis
    console.print("[cyan]Analyzing packages for sustainability scores...[/cyan]")
    scores = await batch_analyze_packages(
        all_packages,
        db,
        profile=profile,
        verbose=verbose,
        use_local_cache=use_local,
        max_workers=num_workers,
    )

    # Build graph
    console.print("[cyan]Building graph...[/cyan]")
    nx_graph = build_networkx_graph(
        dep_graph, scores, direct_only=direct_only, max_depth=max_depth
    )

    # Export
    output_path = Path(output)
    visualizer = PlotlyVisualizer(nx_graph)

    if str(output_path).endswith(".json"):
        visualizer.export_json(output_path)
        console.print(f"[green]Graph exported to: {output_path}[/green]")
    else:
        visualizer.export_html(output_path)
        console.print(f"[green]Interactive graph exported to: {output_path}[/green]")

    # Print summary statistics
    stats = visualizer._get_health_distribution()
    console.print("\n[bold cyan]Health Distribution:[/bold cyan]")
    for status, count in stats.items():
        if count > 0:
            console.print(f"  {status}: {count}")

    # Clean up HTTP clients
    await close_async_http_client()


@app.command()
def trend(
    package: str = typer.Argument(
        ..., help="Package name or repository URL to analyze"
    ),
    ecosystem: str = typer.Option(
        None,
        "--ecosystem",
        "-e",
        help="Package ecosystem (python, javascript, rust, etc.)",
    ),
    interval: str = typer.Option(
        "monthly",
        "--interval",
        "-i",
        help="Display interval: daily, weekly, monthly, quarterly, semi-annual, annual",
    ),
    periods: int = typer.Option(
        6,
        "--periods",
        "-n",
        help="Number of time periods to analyze",
    ),
    window_days: int = typer.Option(
        30,
        "--window-days",
        "-w",
        help="Size of each time window in days",
    ),
    profile: str = typer.Option(
        "balanced",
        "--profile",
        "-p",
        help="Scoring profile (balanced, security_first, contributor_experience, long_term_stability)",
    ),
    profile_file: Path | None = typer.Option(
        None,
        "--profile-file",
        help="Path to a TOML file with scoring profile definitions.",
    ),
    scan_depth: str = typer.Option(
        "default",
        "--scan-depth",
        help="Data sampling depth: shallow, default, deep, very_deep",
    ),
    insecure: bool = typer.Option(
        False,
        "--insecure",
        help="Disable SSL certificate verification for HTTPS requests.",
    ),
    ca_cert: Path | None = typer.Option(
        None,
        "--ca-cert",
        help="Path to custom CA certificate file for SSL verification.",
    ),
    cache_dir: Path | None = typer.Option(
        None,
        "--cache-dir",
        help="Cache directory path (default: ~/.cache/oss-sustain-guard).",
    ),
    cache_ttl: int | None = typer.Option(
        None,
        "--cache-ttl",
        help="Cache TTL in seconds (default: 604800 = 7 days).",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable all caches (local and remote) and perform real-time analysis only.",
    ),
    no_local_cache: bool = typer.Option(
        False,
        "--no-local-cache",
        help="Disable local cache (~/.cache/oss-sustain-guard).",
    ),
    verbose: bool | None = typer.Option(
        None,
        "--verbose",
        "-v",
        help="Enable verbose logging. If not specified, uses config file default.",
    ),
):
    """
    Analyze sustainability score trends over time.

    This command performs trend analysis by collecting repository data across
    multiple time windows and showing how scores evolve over time.

    Note: This analysis is approximate. Some metrics (e.g., stars, security alerts)
    cannot be analyzed historically and are excluded from trend calculations.

    Examples:
      # Monthly trend for past 6 months (defaults to Python)
      os4g trend requests

      # With ecosystem prefix
      os4g trend python:requests
      os4g trend javascript:react

      # Or specify ecosystem with flag
      os4g trend requests -e python

      # Weekly trend for past 12 weeks (7-day windows)
      os4g trend requests --interval weekly --periods 12 --window-days 7

      # Quarterly trend for past year (90-day windows)
      os4g trend requests --interval quarterly --periods 4 --window-days 90

      # Direct repository URL
      os4g trend https://github.com/psf/requests
    """
    import asyncio

    asyncio.run(
        _trend_async(
            package,
            ecosystem,
            interval,
            periods,
            window_days,
            profile,
            profile_file,
            scan_depth,
            insecure,
            ca_cert,
            cache_dir,
            cache_ttl,
            no_cache,
            no_local_cache,
            verbose,
        )
    )


async def _trend_async(
    package: str,
    ecosystem: str | None,
    interval: str,
    periods: int,
    window_days: int,
    profile: str,
    profile_file: Path | None,
    scan_depth: str,
    insecure: bool,
    ca_cert: Path | None,
    cache_dir: Path | None,
    cache_ttl: int | None,
    no_cache: bool,
    no_local_cache: bool,
    verbose: bool | None,
):
    """Async implementation of trend command."""
    import re
    from re import Match

    from oss_sustain_guard.repository import RepositoryReference
    from oss_sustain_guard.resolvers import LanguageResolver
    from oss_sustain_guard.trend import (
        TrendDataPoint,
        TrendInterval,
        analyze_repository_trend,
    )

    # Apply config defaults if not specified via CLI
    if verbose is None:
        verbose = is_verbose_enabled()

    # Validate scan depth
    valid_scan_depths: list[str] = ["shallow", "default", "deep", "very_deep"]
    if scan_depth not in valid_scan_depths:
        console.print(
            f"[red]❌ Invalid scan depth: {scan_depth}[/red]\n"
            f"Valid options: {', '.join(valid_scan_depths)}"
        )
        raise typer.Exit(code=1)

    # Apply scoring profile configuration
    apply_scoring_profiles(profile_file)

    # Validate profile
    if profile not in SCORING_PROFILES:
        console.print(
            f"[red]❌ Unknown profile '{profile}'.[/red]",
        )
        console.print(
            f"[dim]Available profiles: {', '.join(SCORING_PROFILES.keys())}[/dim]"
        )
        raise typer.Exit(code=1)

    # Apply cache configuration
    if cache_dir:
        set_cache_dir(cache_dir)
    if cache_ttl:
        set_cache_ttl(cache_ttl)

    # Configure SSL verification
    if insecure and ca_cert:
        console.print("[red]❌ Cannot use both --insecure and --ca-cert options.[/red]")
        raise typer.Exit(code=1)
    if ca_cert:
        if not ca_cert.exists():
            console.print(f"[red]❌ CA certificate file not found: {ca_cert}[/red]")
            raise typer.Exit(code=1)
        set_verify_ssl(str(ca_cert))
    else:
        set_verify_ssl(not insecure)

    # Determine cache usage flags
    use_cache: bool = not no_cache
    _use_local: bool = use_cache and not no_local_cache

    # Display verbose configuration if enabled
    if verbose:
        console.print(f"[dim]📊 Scan depth: {scan_depth}[/dim]")
        console.print(f"[dim]📁 Cache: {'disabled' if no_cache else 'enabled'}[/dim]")
        if use_cache and no_local_cache:
            console.print("[dim]📁 Local cache: disabled[/dim]")

    try:
        # Validate interval
        try:
            trend_interval = TrendInterval(interval)
        except ValueError as e:
            console.print(
                f"[red]Invalid interval: {interval}[/red]\n"
                "Valid intervals: daily, weekly, monthly, quarterly, semi-annual, annual"
            )
            raise typer.Exit(1) from e

        # Resolve package to repository
        console.print(f"\n[bold cyan]Resolving package:[/bold cyan] {package}")
        if package.startswith(("http://", "https://")):
            # Direct repository URL - parse owner and repo
            repo_url: str = package

            # Parse GitHub URL
            github_match: Match[str] | None = re.match(
                r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url
            )
            # Parse GitLab URL
            gitlab_match: Match[str] | None = re.match(
                r"https?://gitlab\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url
            )

            if github_match:
                owner, repo_name = github_match.groups()
                vcs_platform = "github"
            elif gitlab_match:
                owner, repo_name = gitlab_match.groups()
                vcs_platform = "gitlab"
            else:
                console.print(f"[red]Unable to parse repository URL: {repo_url}[/red]")
                console.print("[yellow]Supported formats:[/yellow]")
                console.print("  - https://github.com/owner/repo")
                console.print("  - https://gitlab.com/owner/repo")
                raise typer.Exit(1)
        else:
            # Resolve from package registry
            # Parse package spec (ecosystem:package or just package)
            parsed_ecosystem, package_name = parse_package_spec(package)

            # Override with explicit ecosystem if provided
            if ecosystem:
                parsed_ecosystem = ecosystem

            # Check if ecosystem was determined
            if not parsed_ecosystem:
                console.print(
                    "[red]Ecosystem must be specified for package names (use -e/--ecosystem or ecosystem:package format)[/red]"
                )
                console.print("[yellow]Example:[/yellow] os4g trend python:requests")
                console.print("[yellow]Example:[/yellow] os4g trend requests -e python")
                raise typer.Exit(1)

            from oss_sustain_guard.resolvers import get_resolver

            resolver: LanguageResolver | None = get_resolver(parsed_ecosystem)
            if not resolver:
                console.print(f"[red]Unknown ecosystem: {parsed_ecosystem}[/red]")
                console.print(
                    "[dim]Available ecosystems: python, javascript, rust, go, php, java, ruby, csharp, etc.[/dim]"
                )
                raise typer.Exit(1)

            if verbose:
                console.print(f"[dim]Using ecosystem: {parsed_ecosystem}[/dim]")
                console.print(f"[dim]Resolving package: {package_name}[/dim]")

            repo_ref: RepositoryReference | None = await resolver.resolve_repository(
                package_name
            )
            if not repo_ref or not repo_ref.url:
                console.print(f"[red]Unable to resolve package: {package_name}[/red]")
                console.print(
                    f"[dim]Package may not exist in {parsed_ecosystem} registry or lacks repository metadata[/dim]"
                )
                raise typer.Exit(1)

            repo_url = repo_ref.url

            # Parse resolved URL
            github_match: Match[str] | None = re.match(
                r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url
            )
            gitlab_match: Match[str] | None = re.match(
                r"https?://gitlab\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url
            )

            if github_match:
                owner, repo_name = github_match.groups()
                vcs_platform = "github"
            elif gitlab_match:
                owner, repo_name = gitlab_match.groups()
                vcs_platform = "gitlab"
            else:
                console.print(f"[red]Unable to parse repository URL: {repo_url}[/red]")
                raise typer.Exit(1)

        console.print(f"[green]Repository:[/green] {repo_url}")
        console.print(
            f"\n[bold cyan]Analyzing trend:[/bold cyan] {periods} {interval} periods "
            f"(window size: {window_days} days)\n"
        )

        # Perform trend analysis
        trend_data: list[TrendDataPoint] = await analyze_repository_trend(
            owner=owner,
            name=repo_name,
            interval=trend_interval,
            periods=periods,
            window_days=window_days,
            profile=profile,
            vcs_platform=vcs_platform,
            scan_depth=scan_depth,
        )

        # Display results
        _display_trend_results(console, trend_data, repo_url, profile)

    except KeyboardInterrupt as e:
        console.print("\n[yellow]Analysis interrupted by user[/yellow]")
        raise typer.Exit(130) from e
    except Exception as e:
        console.print(f"\n[red]Error during trend analysis: {e}[/red]")
        import traceback

        traceback.print_exc()
        raise
    finally:
        # Clean up HTTP clients
        await close_async_http_client()


def _display_trend_results(
    console: Console,
    trend_data: list,
    repo_url: str,
    profile: str,
):
    """Display trend analysis results in terminal."""
    from oss_sustain_guard.trend import TrendDataPoint

    if not trend_data:
        console.print("[yellow]No trend data available[/yellow]")
        return

    # Create header with actual date ranges
    first_window = trend_data[0].window
    last_window = trend_data[-1].window

    date_range = (
        f"{first_window.start.strftime('%Y-%m-%d')} to "
        f"{last_window.end.strftime('%Y-%m-%d')}"
    )

    header = Panel(
        f"[bold]Sustainability Trend Analysis[/bold]\n"
        f"Repository: {repo_url}\n"
        f"Profile: {profile}\n"
        f"Period: {trend_data[0].window.label} → {trend_data[-1].window.label}\n"
        f"[dim]Date range: {date_range}[/dim]",
        style="cyan",
    )
    console.print(header)

    # Important note about approximations and metrics used/excluded
    first_point: TrendDataPoint = trend_data[0]
    included_metrics = [m.name for m in first_point.metrics]

    if included_metrics or first_point.excluded_metrics:
        scope_text = "[bold]Note:[/bold] This is an approximate analysis based on historical data.\n\n"

        if included_metrics:
            scope_text += (
                f"[green]Included metrics ({len(included_metrics)}):[/green]\n"
            )
            for metric in sorted(included_metrics):
                scope_text += f"  • {metric}\n"
            scope_text += "\n"

        if first_point.excluded_metrics:
            scope_text += f"[yellow]Excluded metrics ({len(first_point.excluded_metrics)}):[/yellow]\n"
            for metric in sorted(first_point.excluded_metrics):
                scope_text += f"  • {metric}\n"
            scope_text += "\n"
            scope_text += "[dim]These metrics depend on current state and cannot be historically analyzed.[/dim]"

        scope_panel = Panel(scope_text, title="Analysis Scope", style="dim")
        console.print(scope_panel)
        console.print()

    # Score trend table
    from rich.table import Table

    table = Table(title="Score Trend", show_header=True, header_style="bold cyan")
    table.add_column("Period", style="cyan")
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Change", justify="right")
    table.add_column("Trend", justify="center")

    prev_score = None
    for point in trend_data:
        score_str = str(point.total_score)

        if prev_score is None:
            change_str = ""
            trend_str = ""
        else:
            change = point.total_score - prev_score
            if change > 0:
                change_str = f"+{change}"
                trend_str = "[green]↑[/green]"
            elif change < 0:
                change_str = str(change)
                trend_str = "[red]↓[/red]"
            else:
                change_str = "0"
                trend_str = "[dim]→[/dim]"

        table.add_row(point.window.label, score_str, change_str, trend_str)
        prev_score = point.total_score

    console.print(table)
    console.print()

    # ASCII chart
    console.print("[bold]Score Trend Chart:[/bold]\n")
    _display_ascii_chart(console, trend_data)
    console.print()

    # Top metric changes
    if len(trend_data) >= 2:
        first_metrics = trend_data[0].metrics
        last_metrics = trend_data[-1].metrics

        # Calculate metric changes
        metric_changes = {}
        for metric in first_metrics:
            metric_name = metric.name
            first_score = metric.score

            # Find corresponding metric in last period
            last_score = None
            for last_metric in last_metrics:
                if last_metric.name == metric_name:
                    last_score = last_metric.score
                    break

            if last_score is not None:
                change = last_score - first_score
                if change != 0:
                    metric_changes[metric_name] = (first_score, last_score, change)

        if metric_changes:
            console.print("[bold]Top Metric Changes:[/bold]\n")

            # Sort by absolute change, descending
            sorted_changes = sorted(
                metric_changes.items(), key=lambda x: abs(x[1][2]), reverse=True
            )

            for metric_name, (first_score, last_score, change) in sorted_changes[:5]:
                change_str = f"+{change}" if change > 0 else str(change)
                trend_icon = "↑" if change > 0 else "↓"
                color = "green" if change > 0 else "red"
                console.print(
                    f"  {metric_name}: {first_score} → {last_score}  "
                    f"([{color}]{change_str} {trend_icon}[/{color}])"
                )


def _display_ascii_chart(console: Console, trend_data: list):
    """Display simple ASCII chart of trend scores."""

    scores = [point.total_score for point in trend_data]
    labels = [point.window.label for point in trend_data]

    if not scores:
        return

    # Determine scale
    min_score = min(scores)
    max_score = max(scores)
    score_range = max_score - min_score

    if score_range == 0:
        console.print(f"  [dim]Flat trend at score {scores[0]}[/dim]")
        return

    # Simple line chart using characters
    height = 10
    width = len(scores)

    # Normalize scores to chart height
    normalized = []
    for score in scores:
        if score_range > 0:
            norm = int((score - min_score) / score_range * (height - 1))
        else:
            norm = height // 2
        normalized.append(norm)

    # Build chart from top to bottom
    for row in range(height - 1, -1, -1):
        # Calculate score for this row
        row_score = min_score + (score_range * row / (height - 1))
        line = f"{int(row_score):3d} ┤"

        for col in range(width):
            norm_score = normalized[col]

            if norm_score == row:
                line += "●"
            elif col > 0:
                prev_norm = normalized[col - 1]
                if (prev_norm < row < norm_score) or (norm_score < row < prev_norm):
                    line += "│"
                elif prev_norm == row and norm_score == row:
                    line += "─"
                else:
                    line += " "
            else:
                line += " "

            # Add spacing
            if col < width - 1:
                line += "─"

        console.print(f"  {line}")

    # Add x-axis labels
    axis_line = "    "
    for i, label in enumerate(labels):
        if i == 0:
            axis_line += label
        elif i == len(labels) - 1:
            # Right-align last label
            axis_line = axis_line.rstrip()
            axis_line += label

    console.print(f"  {axis_line}")


if __name__ == "__main__":
    app()
