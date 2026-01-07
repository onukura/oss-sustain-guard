"""Gratitude and acknowledgments command."""

import typer

from oss_sustain_guard.cli_utils.constants import console
from oss_sustain_guard.cli_utils.helpers import load_database, parse_package_spec
from oss_sustain_guard.commands.check import analyze_packages_parallel
from oss_sustain_guard.config import set_verify_ssl
from oss_sustain_guard.core import (
    AnalysisResult,
    Metric,
    compute_weighted_total_score,
)

app = typer.Typer()


@app.command("gratitude")
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
    # Use dict to deduplicate while preserving order
    packages_dict: dict[tuple[str, str], str] = {}
    for pkg_name in packages:
        # Parse package specification to get ecosystem
        ecosystem, package = parse_package_spec(pkg_name)
        packages_dict[(ecosystem, package)] = pkg_name

    # Extract unique package tuples
    packages_data: list[tuple[str, str]] = list(packages_dict.keys())

    # Use the parallel analysis function from check command
    analyzed_results, _ = await analyze_packages_parallel(
        packages_data,
        db,
        profile=profile,
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
