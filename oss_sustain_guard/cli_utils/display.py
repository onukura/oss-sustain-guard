"""Display functions for CLI results output."""

from pathlib import Path

import typer
from rich.table import Table

from oss_sustain_guard.cli_utils.output import _write_html_results, _write_json_results
from oss_sustain_guard.config import get_lfx_config
from oss_sustain_guard.core import (
    AnalysisResult,
    get_metric_weights,
)
from oss_sustain_guard.integrations.lfx import get_lfx_info

from .constants import console
from .helpers import _summarize_observations


def display_results_compact(
    results: list[AnalysisResult],
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


def display_results_table(
    results: list[AnalysisResult],
    show_models: bool = False,
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
    output_format: str = "terminal",
    output_file: Path | None = None,
    output_style: str = "normal",
    profile: str = "balanced",
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
                    demo_notice=demo_notice,
                )
            else:
                _write_html_results(
                    results,
                    profile,
                    output_file,
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
        )
    elif output_style == "detail":
        display_results_detailed(
            results,
            show_signals=True,
            show_models=show_models,
            profile=profile,
        )
    else:
        display_results_table(
            results,
            show_models=show_models,
        )


def display_results_detailed(
    results: list[AnalysisResult],
    show_signals: bool = False,
    show_models: bool = False,
    profile: str = "balanced",
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
