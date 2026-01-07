"""Main check command for analyzing packages."""

import asyncio
import json
from pathlib import Path

import typer

from oss_sustain_guard.cache import clear_cache
from oss_sustain_guard.cli_utils.cache_helpers import (
    _cache_analysis_result,
    clear_lockfile_cache,
)
from oss_sustain_guard.cli_utils.constants import ANALYSIS_VERSION, console
from oss_sustain_guard.cli_utils.display import (
    display_results,
)
from oss_sustain_guard.cli_utils.helpers import (
    _dedupe_packages,
    apply_scoring_profiles,
    load_database,
    parse_package_spec,
    syncify,
)
from oss_sustain_guard.cli_utils.loaders import _load_demo_results
from oss_sustain_guard.config import (
    get_output_style,
    is_package_excluded,
    is_verbose_enabled,
    set_cache_dir,
    set_cache_ttl,
    set_verify_ssl,
)
from oss_sustain_guard.core import (
    SCORING_PROFILES,
    AnalysisResult,
    Metric,
    analyze_repository,
    compute_weighted_total_score,
    get_metric_weights,
)
from oss_sustain_guard.http_client import close_async_http_client
from oss_sustain_guard.resolvers import (
    detect_ecosystems,
    find_lockfiles,
    find_manifest_files,
    get_resolver,
)

app = typer.Typer()


async def analyze_package(
    package_name: str,
    ecosystem: str,
    db: dict,
    profile: str = "balanced",
    verbose: bool = False,
    use_local_cache: bool = True,
    log_buffer: dict[str, list[str]] | None = None,
) -> AnalysisResult | None:
    """
    Analyze a single package.

    Args:
        package_name: Name of the package.
        ecosystem: Ecosystem name (python, javascript, go, rust).
        db: Cached database dictionary.
        profile: Scoring profile name.
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


@app.command("check")
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

    # Parallel analysis for multiple packages
    if packages_to_process:
        # Use parallel processing for better performance
        results, verbose_logs = await analyze_packages_parallel(
            packages_to_process,
            db,
            profile,
            verbose,
            use_local,
            max_workers=num_workers,
        )

        # Display verbose logs after progress bar is done
        if verbose and verbose_logs:
            for _db_key, logs in verbose_logs.items():
                for log in logs:
                    console.print(log)

        # Filter out None results
        results_to_display = [r for r in results if r is not None]

    if results_to_display:
        display_results(
            results_to_display,
            show_models=show_models,
            output_format=output_format,
            output_file=output_file,
            output_style=output_style,
            profile=profile,
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


async def analyze_packages_parallel(
    packages_data: list[tuple[str, str]],
    db: dict,
    profile: str = "balanced",
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
        verbose: If True, display cache source information.
        use_local_cache: If False, skip local cache lookup.
        max_workers: Maximum number of parallel workers (default: 5).

    Returns:
        Tuple of (List of AnalysisResult or None for each package, verbose logs dict)
    """
    _total = len(packages_data)
    verbose_logs: dict[str, list[str]] = {}  # Collect logs instead of printing directly

    # Deduplicate packages by their resolved repository to avoid analyzing the same repo multiple times
    # Map from (provider, owner, repo_name) -> list of (idx, ecosystem, package_name)
    repo_to_packages: dict[tuple[str, str, str], list[tuple[int, str, str]]] = {}

    # Semaphore to limit concurrent tasks
    semaphore = asyncio.Semaphore(max_workers)

    async def resolve_with_semaphore(idx: int, eco: str, pkg_name: str):
        """Resolve package to repository info."""
        async with semaphore:
            db_key = f"{eco}:{pkg_name}"

            # Check if package is excluded
            if is_package_excluded(pkg_name):
                return None

            # Check local cache first - if found, we already have the analysis
            if db_key in db:
                cached_data = db[db_key]
                payload_version = cached_data.get("analysis_version")
                if payload_version == ANALYSIS_VERSION:
                    # Can reconstruct from cache, return marker
                    return (idx, eco, pkg_name, None, None, None, "cached")

            # Resolve repository
            resolver = get_resolver(eco)
            if not resolver:
                return (idx, eco, pkg_name, None, None, None, "no_resolver")

            try:
                repo_info = await resolver.resolve_repository(pkg_name)
                if not repo_info:
                    return (idx, eco, pkg_name, None, None, None, "not_found")

                provider = repo_info.provider
                if provider == "gitlab":
                    path_segments = repo_info.path.split("/")
                    if len(path_segments) < 2:
                        return (idx, eco, pkg_name, None, None, None, "invalid_path")
                    owner = "/".join(path_segments[:-1])
                    repo_name = path_segments[-1]
                else:
                    owner, repo_name = repo_info.owner, repo_info.name

                return (idx, eco, pkg_name, provider, owner, repo_name, "resolved")
            except Exception:
                return (idx, eco, pkg_name, None, None, None, "error")

    # Resolve all packages in parallel
    resolution_tasks = [
        resolve_with_semaphore(idx, eco, pkg_name)
        for idx, (eco, pkg_name) in enumerate(packages_data)
    ]
    resolution_results = await asyncio.gather(*resolution_tasks, return_exceptions=True)

    # Group by resolved repository
    for res in resolution_results:
        if isinstance(res, BaseException) or res is None:
            continue

        idx, eco, pkg_name, provider, owner, repo_name, status = res

        if status == "cached":
            # Keep cached packages for direct reconstruction
            if ("cached", eco, pkg_name) not in repo_to_packages:
                repo_to_packages[("cached", eco, pkg_name)] = []
            repo_to_packages[("cached", eco, pkg_name)].append((idx, eco, pkg_name))
        elif status == "resolved":
            # Group by repository
            repo_key = (provider, owner, repo_name)
            if repo_key not in repo_to_packages:
                repo_to_packages[repo_key] = []
            repo_to_packages[repo_key].append((idx, eco, pkg_name))
        # Skip other statuses (no_resolver, not_found, error, invalid_path)

    # Analyze each unique repository once
    async def analyze_with_semaphore(repo_key, packages_list):
        async with semaphore:
            # Use the first package's info for analysis
            _, eco, pkg_name = packages_list[0]
            return await analyze_package(
                package_name=pkg_name,
                ecosystem=eco,
                db=db,
                profile=profile,
                verbose=verbose,
                use_local_cache=use_local_cache,
                log_buffer=verbose_logs,
            )

    # Create tasks for unique repositories
    repo_tasks = [
        analyze_with_semaphore(repo_key, packages_list)
        for repo_key, packages_list in repo_to_packages.items()
    ]

    # Run all tasks concurrently
    gathered_results = await asyncio.gather(*repo_tasks, return_exceptions=True)

    # Map results back to original package indices
    results: list[AnalysisResult | None] = [None] * _total

    for (_repo_key, packages_list), result in zip(
        repo_to_packages.items(), gathered_results, strict=False
    ):
        # Convert exception to None
        analysis_result = None if isinstance(result, BaseException) else result

        # Apply result to all packages that resolved to this repository
        for idx, _eco, _pkg_name in packages_list:
            results[idx] = analysis_result

    return results, verbose_logs
