"""Dependency tree tracing and visualization command."""

from pathlib import Path

import typer

from oss_sustain_guard.cli_utils.constants import console
from oss_sustain_guard.cli_utils.helpers import (
    apply_scoring_profiles,
    load_database,
    syncify,
)
from oss_sustain_guard.commands.gratitude import batch_analyze_packages
from oss_sustain_guard.config import (
    is_verbose_enabled,
    set_cache_dir,
    set_cache_ttl,
    set_verify_ssl,
)
from oss_sustain_guard.core import SCORING_PROFILES
from oss_sustain_guard.dependency_graph import get_all_dependencies
from oss_sustain_guard.dependency_tree_resolver import (
    is_lockfile_path,
    resolve_dependency_tree,
)
from oss_sustain_guard.external_tools import ExternalToolName
from oss_sustain_guard.http_client import close_async_http_client
from oss_sustain_guard.visualization import (
    TerminalTreeVisualizer,
    build_networkx_graph,
)

app = typer.Typer()


@app.command("trace")
@syncify
async def trace(
    input: str = typer.Argument(
        ...,
        help="Lockfile path OR package name to trace (e.g., requirements.txt or requests)",
    ),
    ecosystem: str | None = typer.Option(
        None,
        "--ecosystem",
        "-e",
        help="Package ecosystem (python, javascript, rust, etc.) - for package mode only",
    ),
    version: str | None = typer.Option(
        None,
        "--version",
        "-V",
        help="Package version to trace (default: latest) - for package mode only",
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
    tool: ExternalToolName | None = typer.Option(
        None,
        "--tool",
        "-t",
        help="Force specific package manager tool (uv, npm, pnpm, bun). If not specified, auto-detects best available tool.",
        case_sensitive=False,
    ),
) -> None:
    """
    Trace and visualize package dependency trees in terminal.

    Supports two modes:
    1. Lockfile mode: Analyze existing lockfiles (requirements.txt, package.json, etc.)
    2. Package mode: Resolve dependencies for a specific package name

    Output:
    - Terminal tree with color-coded health scores

    Examples:
        # Basic usage
        os4g trace requests
        os4g trace uv.lock
        os4g trace requests --version 2.28.0

        # Lockfile mode
        os4g trace requirements.txt
        os4g trace package.json --max-depth=2

        # Package mode with options
        os4g trace javascript:react --max-depth=2
        os4g trace -e rust serde --profile security_first

        # Force specific tool
        os4g trace requests --tool uv
        os4g trace react --tool npm
        os4g trace lodash --tool pnpm --ecosystem javascript
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

    # Determine cache usage flags
    use_cache = not no_cache
    use_local = use_cache and not no_local_cache

    # Load database with cache configuration
    db = load_database(use_cache=use_cache, use_local_cache=use_local, verbose=verbose)

    # DUAL MODE: Detect input type and resolve dependency graph
    if is_lockfile_path(input):
        # LOCKFILE MODE
        # Warn if --tool is specified in lockfile mode (it only applies to package mode)
        if tool:
            console.print(
                "[yellow]⚠️  --tool option is ignored in lockfile mode (only applies to package mode)[/yellow]"
            )

        lockfile_path = Path(input)
        if not lockfile_path.exists():
            console.print(f"[red]Error: Lockfile not found: {lockfile_path}[/red]")
            raise typer.Exit(1)

        console.print(f"[cyan]Parsing lockfile: {lockfile_path}[/cyan]")

        # Parse dependencies from lockfile
        dep_graphs = get_all_dependencies([lockfile_path])
        if not dep_graphs:
            console.print("[red]Error: Could not parse lockfile[/red]")
            raise typer.Exit(1)

        dep_graph = dep_graphs[0]
        console.print(
            f"[cyan]Found {len(dep_graph.direct_dependencies)} direct and "
            f"{len(dep_graph.transitive_dependencies)} transitive dependencies[/cyan]"
        )
    else:
        # PACKAGE MODE
        package_name = input
        console.print(
            f"[cyan]Resolving dependency tree for package: {package_name}[/cyan]"
        )
        if version:
            console.print(f"[dim]Version: {version}[/dim]")
        if ecosystem:
            console.print(f"[dim]Ecosystem: {ecosystem}[/dim]")

        try:
            # Resolve dependency tree using external tools
            dep_graph = await resolve_dependency_tree(
                package_name=package_name,
                ecosystem=ecosystem,
                version=version,
                max_depth=max_depth,
                tool_name=tool.value if tool else None,
            )
            console.print(
                f"[cyan]Resolved {len(dep_graph.direct_dependencies)} direct and "
                f"{len(dep_graph.transitive_dependencies)} transitive dependencies[/cyan]"
            )
        except RuntimeError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1) from e
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1) from e
        except NotImplementedError as e:
            console.print(f"[yellow]⚠️  {e}[/yellow]")
            raise typer.Exit(1) from e

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

    # Collect all packages to analyze (with ecosystem prefix for correct registry lookup)
    # Use dict.fromkeys to remove duplicates while preserving order
    all_packages = list(
        dict.fromkeys(f"{dep.ecosystem}:{dep.name}" for dep in all_deps_list)
    )

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

    # Display in terminal
    terminal_viz = TerminalTreeVisualizer(nx_graph)
    terminal_viz.display()

    # Clean up HTTP clients
    await close_async_http_client()
