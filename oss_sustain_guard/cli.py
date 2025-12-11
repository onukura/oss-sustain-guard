"""
Command-line interface for OSS Sustain Guard.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table

from oss_sustain_guard.cache import clear_cache, get_cache_stats, load_cache, save_cache
from oss_sustain_guard.config import (
    DEFAULT_CACHE_TTL,
    get_verify_ssl,
    is_cache_enabled,
    is_package_excluded,
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
)
from oss_sustain_guard.resolvers import (
    detect_ecosystems,
    find_lockfiles,
    find_manifest_files,
    get_resolver,
)

# project_root is the parent directory of oss_sustain_guard/
project_root = Path(__file__).resolve().parent.parent

# --- Constants ---
GITHUB_REPO_URL = "https://media.githubusercontent.com/media/onukura/oss-sustain-guard/refs/heads/main"
LATEST_DIR = project_root / "data" / "latest"

# --- Typer App ---
app = typer.Typer()
console = Console()

# --- Helper Functions ---


def load_database(use_cache: bool = True) -> dict:
    """Load the sustainability database with caching support.

    Loads data with the following priority:
    1. User cache (~/.cache/oss-sustain-guard/*.json) if enabled and valid
    2. GitHub repository (remote)
    3. Local data/latest/ directory (fallback)

    Args:
        use_cache: If False, skip all cached data sources (user cache, GitHub, local files)
                   and perform real-time analysis only.

    Returns:
        Dictionary of package data keyed by "ecosystem:package_name".
    """
    merged = {}

    # If use_cache is False, return empty dict to force real-time analysis for all packages
    if not use_cache:
        return merged

    # List of ecosystems to load
    ecosystems = ["python", "javascript", "ruby", "rust", "php", "java", "csharp", "go"]

    # Load from cache first if enabled
    if is_cache_enabled():
        for ecosystem in ecosystems:
            cached_data = load_cache(ecosystem)
            if cached_data:
                merged.update(cached_data)
                console.print(
                    f"[dim]Loaded {len(cached_data)} entries from cache: {ecosystem}[/dim]"
                )

    # Determine which ecosystems need fresh data
    ecosystems_to_fetch = []
    if not is_cache_enabled():
        # Need all ecosystems if cache is disabled
        ecosystems_to_fetch = ecosystems
    else:
        # Only fetch ecosystems that have no cache data
        for ecosystem in ecosystems:
            ecosystem_keys = [k for k in merged.keys() if k.startswith(f"{ecosystem}:")]
            if not ecosystem_keys:
                ecosystems_to_fetch.append(ecosystem)

    # Try loading missing ecosystems from GitHub
    if ecosystems_to_fetch:
        github_success = False
        for ecosystem in ecosystems_to_fetch:
            url = f"{GITHUB_REPO_URL}/data/latest/{ecosystem}.json"
            try:
                with httpx.Client(
                    verify=get_verify_ssl(), follow_redirects=True
                ) as client:
                    response = client.get(url, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    merged.update(data)
                    github_success = True
                    console.print(f"Loaded {ecosystem} data from GitHub.")

                    # Save to cache if enabled
                    if is_cache_enabled():
                        save_cache(ecosystem, data)
            except Exception:
                # Silently skip GitHub errors for now, will try local fallback
                console.print(
                    f"[dim]Note: Using local data for {ecosystem} (GitHub unavailable)[/dim]"
                )

        # If GitHub loading failed, fall back to local data/latest/
        if not github_success and LATEST_DIR.exists():
            for ecosystem in ecosystems_to_fetch:
                ecosystem_file = LATEST_DIR / f"{ecosystem}.json"
                if ecosystem_file.exists():
                    try:
                        with open(ecosystem_file, "r", encoding="utf-8") as f:
                            raw_data = json.load(f)

                            # Handle schema versions
                            if (
                                isinstance(raw_data, dict)
                                and "_schema_version" in raw_data
                            ):
                                # v2.0+ format with metadata
                                data = raw_data.get("packages", {})
                            else:
                                # v1.x format (flat dict) - backward compatibility
                                data = raw_data

                            merged.update(data)
                            console.print(
                                f"Loaded {ecosystem} data from local fallback."
                            )

                            # Save to cache if enabled
                            if is_cache_enabled():
                                save_cache(ecosystem, data)
                    except Exception:
                        console.print(
                            f"[dim]Note: Could not load {ecosystem_file.name}[/dim]"
                        )

    return merged


def display_results(results: list[AnalysisResult], show_models: bool = False):
    """Display the analysis results in a rich table."""
    table = Table(title="OSS Sustain Guard Report")
    table.add_column("Package", justify="left", style="cyan", no_wrap=True)
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
            health_status = "[yellow]Needs attention[/yellow]"
        else:
            health_status = "[red]Needs support[/red]"

        # Gather key observations (areas needing attention)
        observations = []
        for metric in result.metrics:
            if metric.risk in ("High", "Critical"):
                observations.append(metric.message)

        # Create friendly observation text
        if observations:
            observation_text = " • ".join(observations[:2])  # Show top 2 observations
            if len(observations) > 2:
                observation_text += f" (+{len(observations) - 2} more)"
        else:
            observation_text = "No significant concerns detected"

        table.add_row(
            result.repo_url.replace("https://github.com/", ""),
            f"[{score_color}]{result.total_score}/100[/{score_color}]",
            health_status,
            observation_text,
        )

    console.print(table)

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
                console.print(
                    f"\n📊 [bold cyan]{result.repo_url.replace('https://github.com/', '')}[/bold cyan] "
                    f"- CHAOSS Metric Models:"
                )
                for model in result.models:
                    # Color code based on model score
                    model_color = "green"
                    if model.score < 50:
                        model_color = "red"
                    elif model.score < 80:
                        model_color = "yellow"

                    console.print(
                        f"   • {model.name}: [{model_color}]{model.score}/{model.max_score}[/{model_color}] - {model.observation}"
                    )


def display_results_detailed(
    results: list[AnalysisResult], show_signals: bool = False, show_models: bool = False
):
    """Display detailed analysis results with all metrics for each package."""
    for result in results:
        # Determine overall color
        risk_color = "green"
        if result.total_score < 50:
            risk_color = "red"
        elif result.total_score < 80:
            risk_color = "yellow"

        # Header
        console.print(
            f"\n📦 [bold cyan]{result.repo_url.replace('https://github.com/', '')}[/bold cyan]"
        )
        console.print(
            f"   Total Score: [{risk_color}]{result.total_score}/100[/{risk_color}]"
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

        # Metrics table
        metrics_table = Table(show_header=True, header_style="bold magenta")
        metrics_table.add_column("Metric", style="cyan", no_wrap=True)
        metrics_table.add_column("Score", justify="center", style="magenta")
        metrics_table.add_column("Max", justify="center", style="magenta")
        metrics_table.add_column("Status", justify="left")
        metrics_table.add_column("Observation", justify="left")

        for metric in result.metrics:
            # Status color coding with supportive language
            status_style = "green"
            status_text = "Good"
            if metric.risk in ("Critical", "High"):
                status_style = "red"
                status_text = "Needs attention"
            elif metric.risk == "Medium":
                status_style = "yellow"
                status_text = "Monitor"
            elif metric.risk == "Low":
                status_style = "yellow"
                status_text = "Consider improving"
            else:  # None
                status_style = "green"
                status_text = "Healthy"

            metrics_table.add_row(
                metric.name,
                f"[cyan]{metric.score}[/cyan]",
                f"[cyan]{metric.max_score}[/cyan]",
                f"[{status_style}]{status_text}[/{status_style}]",
                metric.message,
            )

        console.print(metrics_table)

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


def analyze_package(
    package_name: str,
    ecosystem: str,
    db: dict,
    profile: str = "balanced",
) -> AnalysisResult | None:
    """
    Analyze a single package.

    Args:
        package_name: Name of the package.
        ecosystem: Ecosystem name (python, javascript, go, rust).
        db: Cached database dictionary.
        profile: Scoring profile to use for score calculation.

    Returns:
        AnalysisResult if successful, None otherwise.
    """
    # Check if package is excluded
    if is_package_excluded(package_name):
        return None

    # Create database key
    db_key = f"{ecosystem}:{package_name}"

    # Check cache first
    if db_key in db:
        console.print(f"  -> Found [bold green]{db_key}[/bold green] in cache.")
        cached_data = db[db_key]
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
        # Recalculate total score with selected profile
        recalculated_score = compute_weighted_total_score(metrics, profile)
        # Reconstruct AnalysisResult
        result = AnalysisResult(
            repo_url=cached_data.get("github_url", "unknown"),
            total_score=recalculated_score,
            metrics=metrics,
            funding_links=cached_data.get("funding_links", []),
            is_community_driven=cached_data.get("is_community_driven", False),
            models=cached_data.get("models", []),
            signals=cached_data.get("signals", {}),
        )
        return result

    # Resolve GitHub URL using appropriate resolver
    resolver = get_resolver(ecosystem)
    if not resolver:
        console.print(
            f"  -> [yellow]ℹ️  Ecosystem '{ecosystem}' is not yet supported[/yellow]"
        )
        return None

    repo_info = resolver.resolve_github_url(package_name)
    if not repo_info:
        console.print(
            f"  -> [yellow]ℹ️  GitHub repository not found for {db_key}. Package may not have public source code.[/yellow]"
        )
        return None

    owner, repo_name = repo_info
    console.print(f"  -> [bold yellow]{db_key}[/bold yellow] analyzing real-time...")

    try:
        analysis_result = analyze_repository(owner, repo_name)

        # Save to cache for future use
        cache_entry = {
            db_key: {
                "ecosystem": ecosystem,
                "package_name": package_name,
                "github_url": analysis_result.repo_url,
                "total_score": analysis_result.total_score,
                "metrics": [metric._asdict() for metric in analysis_result.metrics],
                "funding_links": analysis_result.funding_links,
                "is_community_driven": analysis_result.is_community_driven,
                "cache_metadata": {
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "ttl_seconds": DEFAULT_CACHE_TTL,
                    "source": "realtime",
                },
            }
        }

        if is_cache_enabled():
            save_cache(ecosystem, cache_entry)
            console.print("    [dim]💾 Cached for future use[/dim]")

        return analysis_result
    except Exception as e:
        console.print(
            f"    [yellow]⚠️  Unable to complete analysis for {owner}/{repo_name}: {e}[/yellow]"
        )
        return None


@app.command()
def check(
    packages: list[str] = typer.Argument(
        None,
        help="Packages to analyze (format: 'package', 'ecosystem:package', or file path). Examples: 'requests', 'npm:react', 'go:gin', 'php:symfony/console', 'java:com.google.guava:guava', 'csharp:Newtonsoft.Json'. If omitted, auto-detects from manifest files.",
    ),
    ecosystem: str = typer.Option(
        "auto",
        "--ecosystem",
        "-e",
        help="Default ecosystem for unqualified packages (python, javascript, go, rust, php, java, kotlin, scala, csharp, dotnet). Use 'auto' to detect.",
    ),
    include_lock: bool = typer.Option(
        False,
        "--include-lock",
        "-l",
        help="Include packages from lockfiles in the current directory.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Display detailed metrics for each package, including raw signals.",
    ),
    show_models: bool = typer.Option(
        False,
        "--show-models",
        "-M",
        help="Display CHAOSS-aligned metric models (Risk Model, Sustainability Model).",
    ),
    profile: str = typer.Option(
        "balanced",
        "--profile",
        "-p",
        help="Scoring profile: balanced (default), security_first, contributor_experience, long_term_stability.",
    ),
    insecure: bool = typer.Option(
        False,
        "--insecure",
        help="Disable SSL certificate verification for HTTPS requests.",
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
        help="Disable cache and load fresh data.",
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
):
    """Analyze the sustainability of packages across multiple ecosystems (Python, JavaScript, Go, Rust, PHP, Java, C#)."""
    # Validate profile
    if profile not in SCORING_PROFILES:
        console.print(
            f"[red]❌ Unknown profile '{profile}'.[/red]",
        )
        console.print(
            f"[dim]Available profiles: {', '.join(SCORING_PROFILES.keys())}[/dim]"
        )
        raise typer.Exit(code=1)

    # Handle --clear-cache option
    if clear_cache_flag:
        cleared = clear_cache()
        console.print(f"[green]✨ Cleared {cleared} cache file(s).[/green]")
        raise typer.Exit(code=0)

    # Apply cache configuration
    if cache_dir:
        set_cache_dir(cache_dir)
    if cache_ttl:
        set_cache_ttl(cache_ttl)

    set_verify_ssl(not insecure)
    db = load_database(use_cache=not no_cache)
    results_to_display = []
    packages_to_analyze: list[tuple[str, str]] = []  # (ecosystem, package_name)

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
            "rust",
            "go",
            "php",
            "java",
            "ruby",
            "csharp",
        ]:
            resolver = get_resolver(eco)
            if resolver and manifest_name in resolver.get_manifest_files():
                detected_eco = eco
                break

        if not detected_eco:
            console.print(
                f"[yellow]⚠️  Could not detect ecosystem from manifest file: {manifest_name}[/yellow]"
            )
            console.print(
                "[dim]Supported manifest files:[/dim] package.json, requirements.txt, pyproject.toml, Cargo.toml, go.mod, composer.json, pom.xml, Gemfile, packages.config"
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
            manifest_packages = resolver.parse_manifest(str(manifest))
            console.print(
                f"   Found {len(manifest_packages)} package(s) in {manifest_name}"
            )
            for pkg_info in manifest_packages:
                packages_to_analyze.append((detected_eco, pkg_info.name))
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

        detected_ecosystems = detect_ecosystems(
            str(root_dir), recursive=recursive, max_depth=depth
        )
        if detected_ecosystems:
            console.print(f"✅ Detected ecosystems: {', '.join(detected_ecosystems)}")

            # Find all manifest files (recursively if requested)
            manifest_files_dict = find_manifest_files(
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
                        manifest_packages = resolver.parse_manifest(str(manifest_path))
                        console.print(
                            f"   Found {len(manifest_packages)} package(s) in {manifest_path.name}"
                        )
                        for pkg_info in manifest_packages:
                            packages_to_analyze.append((detected_eco, pkg_info.name))
                    except Exception as e:
                        console.print(
                            f"   [dim]Warning: Unable to parse {manifest_path.name} - {e}[/dim]"
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
        else:
            # Parse command-line package specifications
            for pkg_spec in packages:
                eco, pkg_name = parse_package_spec(pkg_spec)
                # Override ecosystem if specified
                if ecosystem != "auto" and ":" not in pkg_spec:
                    eco = ecosystem
                packages_to_analyze.append((eco, pkg_name))

        # If --include-lock is explicitly specified, detect and add packages from lockfiles
        if include_lock:
            if recursive:
                depth_msg = (
                    f" (depth: {depth})" if depth is not None else " (unlimited depth)"
                )
                console.print(f"🔒 Recursively scanning for lockfiles{depth_msg}...")

            detected_ecosystems = detect_ecosystems(
                str(root_dir), recursive=recursive, max_depth=depth
            )
            if detected_ecosystems:
                console.print(
                    f"🔍 Detected ecosystems: {', '.join(detected_ecosystems)}"
                )

                # Find all lockfiles (recursively if requested)
                lockfiles_dict = find_lockfiles(
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
                                lock_packages = resolver.parse_lockfile(str(lockfile))
                                console.print(
                                    f"   Found {len(lock_packages)} package(s) in {lockfile.name}"
                                )
                                for pkg_info in lock_packages:
                                    packages_to_analyze.append(
                                        (detected_eco, pkg_info.name)
                                    )
                            except Exception as e:
                                console.print(
                                    f"   [yellow]Warning: Failed to parse {lockfile.name}: {e}[/yellow]"
                                )
            else:
                console.print(f"   [dim]No lockfiles found in {root_dir}.[/dim]")

    # Remove duplicates while preserving order
    seen = set()
    unique_packages = []
    for eco, pkg in packages_to_analyze:
        key = f"{eco}:{pkg}"
        if key not in seen:
            seen.add(key)
            unique_packages.append((eco, pkg))
    packages_to_analyze = unique_packages

    console.print(f"🔍 Analyzing {len(packages_to_analyze)} package(s)...")

    excluded_count = 0
    for eco, pkg_name in packages_to_analyze:
        # Skip excluded packages
        if is_package_excluded(pkg_name):
            excluded_count += 1
            console.print(
                f"  -> Skipping [bold yellow]{pkg_name}[/bold yellow] (excluded)"
            )
            continue

        result = analyze_package(pkg_name, eco, db, profile)
        if result:
            results_to_display.append(result)

    if results_to_display:
        if verbose:
            display_results_detailed(
                results_to_display, show_signals=verbose, show_models=show_models
            )
        else:
            display_results(results_to_display, show_models=show_models)
        if excluded_count > 0:
            console.print(
                f"\n⏭️  Skipped {excluded_count} excluded package(s).",
                style="yellow",
            )
    else:
        console.print("No results to display.")


@app.command()
def cache_stats(
    ecosystem: str | None = typer.Argument(
        None,
        help="Specific ecosystem to check (python, javascript, rust, etc.), or omit for all ecosystems.",
    ),
):
    """Display cache statistics."""
    stats = get_cache_stats(ecosystem)

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

        # Calculate support priority score
        total_score = data.get("total_score", 0)
        metrics = data.get("metrics", [])

        # Find specific metrics that indicate need for support
        bus_factor_score = 20  # Default max
        maintainer_drain_score = 15  # Default max

        for metric in metrics:
            metric_name = metric.get("name", "")
            if "Bus Factor" in metric_name or "Contributor Redundancy" in metric_name:
                bus_factor_score = metric.get("score", 20)
            elif "Maintainer" in metric_name and "Drain" in metric_name:
                maintainer_drain_score = metric.get("score", 15)

        # Priority = (100 - total_score) + (20 - bus_factor) + (15 - maintainer_drain)
        # Higher priority = needs more support
        priority = (
            (100 - total_score)
            + (20 - bus_factor_score)
            + (15 - maintainer_drain_score)
        )

        support_candidates.append(
            {
                "key": key,
                "repo_url": data.get("github_url", data.get("repo_url", "")),
                "total_score": total_score,
                "priority": priority,
                "funding_links": funding_links,
                "bus_factor_score": bus_factor_score,
                "maintainer_drain_score": maintainer_drain_score,
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
            status_text = "Needs attention"

        console.print(f"[bold cyan]{i}. {package_name}[/bold cyan] ({ecosystem})")
        console.print(f"   Repository: {repo_url}")
        console.print(
            f"   Health Score: [{status_color}]{total_score}/100[/{status_color}] ({status_text})"
        )
        console.print(f"   Contributor Redundancy: {project['bus_factor_score']}/20")
        console.print(f"   Maintainer Drain: {project['maintainer_drain_score']}/15")

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


if __name__ == "__main__":
    app()
