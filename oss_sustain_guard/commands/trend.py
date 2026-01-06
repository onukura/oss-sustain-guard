"""Trend analysis command."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from oss_sustain_guard.cli_utils.constants import console
from oss_sustain_guard.cli_utils.helpers import (
    apply_scoring_profiles,
    parse_package_spec,
)
from oss_sustain_guard.config import (
    is_verbose_enabled,
    set_cache_dir,
    set_cache_ttl,
    set_verify_ssl,
)
from oss_sustain_guard.core import SCORING_PROFILES
from oss_sustain_guard.http_client import close_async_http_client

app = typer.Typer()


@app.command("trend")
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
        get_trend_cache_stats,
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
        console.print("[yellow]⚠️  Ignoring --ca-cert when --insecure is set[/yellow]")
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

        # Perform trend analysis with caching enabled
        trend_data: list[TrendDataPoint] = await analyze_repository_trend(
            owner=owner,
            name=repo_name,
            interval=trend_interval,
            periods=periods,
            window_days=window_days,
            profile=profile,
            vcs_platform=vcs_platform,
            scan_depth=scan_depth,
            use_cache=use_cache,
        )

        # Display cache statistics if verbose
        if verbose and use_cache:
            cache_stats = get_trend_cache_stats()
            if cache_stats:
                cached = cache_stats.get("cached", 0)
                api = cache_stats.get("api", 0)
                console.print(
                    f"[dim]💾 Cache: {cached} windows from cache, {api} fresh API calls[/dim]"
                )

        # Display results
        _display_trend_results(console, trend_data, repo_url, profile)

    except KeyboardInterrupt as e:
        console.print("[yellow]⏸️  Interrupted by user[/yellow]")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error during trend analysis: {e}[/red]")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1) from e
    finally:
        # Ensure async resources are cleaned up
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
