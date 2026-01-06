"""Cache management commands."""

from datetime import datetime
from pathlib import Path

import typer
from rich.table import Table

from oss_sustain_guard.cache import (
    clear_cache,
    clear_expired_cache,
    get_cache_stats,
    get_cached_packages,
)
from oss_sustain_guard.cli_utils.constants import ANALYSIS_VERSION, console
from oss_sustain_guard.cli_utils.helpers import apply_scoring_profiles
from oss_sustain_guard.config import set_cache_dir
from oss_sustain_guard.core import (
    SCORING_PROFILES,
    Metric,
    compute_weighted_total_score,
)

app = typer.Typer()


@app.command("stats")
def stats(
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


@app.command("clear")
def clear(
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


@app.command("list")
def list_packages(
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
