"""
Command-line interface for OSS Sustain Guard.
"""

import gzip
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
from oss_sustain_guard.trend import ComparisonReport, TrendAnalyzer

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
    ecosystems = [
        "python",
        "javascript",
        "ruby",
        "rust",
        "php",
        "java",
        "kotlin",
        "csharp",
        "go",
    ]

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
            # Try gzip first, then fallback to uncompressed
            urls = [
                f"{GITHUB_REPO_URL}/data/latest/{ecosystem}.json.gz",
                f"{GITHUB_REPO_URL}/data/latest/{ecosystem}.json",
            ]
            loaded = False
            for url in urls:
                try:
                    with httpx.Client(
                        verify=get_verify_ssl(), follow_redirects=True
                    ) as client:
                        response = client.get(url, timeout=10)
                        response.raise_for_status()

                        # Decompress if gzip
                        if url.endswith(".gz"):
                            data = json.loads(
                                gzip.decompress(response.content).decode("utf-8")
                            )
                        else:
                            data = response.json()

                        merged.update(data)
                        github_success = True
                        loaded = True
                        console.print(f"Loaded {ecosystem} data from GitHub.")

                        # Save to cache if enabled
                        if is_cache_enabled():
                            save_cache(ecosystem, data)
                        break
                except Exception:
                    continue

            if not loaded:
                # Silently skip GitHub errors for now, will try local fallback
                console.print(
                    f"[dim]Note: Using local data for {ecosystem} (GitHub unavailable)[/dim]"
                )

        # If GitHub loading failed, fall back to local data/latest/
        if not github_success and LATEST_DIR.exists():
            for ecosystem in ecosystems_to_fetch:
                # Try gzip first, then fallback to uncompressed
                ecosystem_files = [
                    LATEST_DIR / f"{ecosystem}.json.gz",
                    LATEST_DIR / f"{ecosystem}.json",
                ]

                for ecosystem_file in ecosystem_files:
                    if ecosystem_file.exists():
                        try:
                            if ecosystem_file.suffix == ".gz":
                                with gzip.open(
                                    ecosystem_file, "rt", encoding="utf-8"
                                ) as f:
                                    raw_data = json.load(f)
                            else:
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
                            break
                        except Exception:
                            continue

    return merged


def display_results_compact(results: list[AnalysisResult]):
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
            status = "Needs attention"
        else:
            icon = "✗"
            score_color = "red"
            status = "Needs support"

        # Extract package name from repo URL
        package_name = result.repo_url.replace("https://github.com/", "")

        # One-line output: icon package (score) - status
        console.print(
            f"[{score_color}]{icon}[/{score_color}] "
            f"[cyan]{package_name}[/cyan] "
            f"[{score_color}]({result.total_score}/100)[/{score_color}] - "
            f"{status}"
        )


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
    enable_dependents: bool = False,
) -> AnalysisResult | None:
    """
    Analyze a single package.

    Args:
        package_name: Name of the package.
        ecosystem: Ecosystem name (python, javascript, go, rust).
        db: Cached database dictionary.
        profile: Scoring profile to use for score calculation.
        enable_dependents: Enable downstream dependents analysis via Libraries.io API.

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

    # Only enable dependents analysis if explicitly requested
    platform = None
    pkg_name = None
    if enable_dependents:
        # Map ecosystem to Libraries.io platform for dependents analysis
        platform_map = {
            "python": "Pypi",
            "javascript": "NPM",
            "rust": "Cargo",
            "java": "Maven",
            "php": "Packagist",
            "ruby": "Rubygems",
            "csharp": "Nuget",
            "dotnet": "Nuget",
            "go": "Go",
        }
        platform = platform_map.get(ecosystem.lower())
        pkg_name = package_name

    try:
        analysis_result = analyze_repository(
            owner, repo_name, platform=platform, package_name=pkg_name
        )

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
    compact: bool = typer.Option(
        False,
        "--compact",
        "-c",
        help="Display results in compact format (one line per package, ideal for CI/CD).",
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
    enable_dependents: bool = typer.Option(
        False,
        "--enable-dependents",
        "-D",
        help="Enable downstream dependents analysis via Libraries.io API (requires LIBRARIESIO_API_KEY).",
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

        result = analyze_package(pkg_name, eco, db, profile, enable_dependents)
        if result:
            results_to_display.append(result)

    if results_to_display:
        if compact:
            display_results_compact(results_to_display)
        elif verbose:
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


@app.command()
def trend(
    package_name: str = typer.Argument(..., help="Package name to analyze trends for"),
    ecosystem: str = typer.Option(
        "python",
        "--ecosystem",
        "-e",
        help="Package ecosystem (python, javascript, rust, etc.)",
    ),
    metric: str | None = typer.Option(
        None,
        "--metric",
        "-m",
        help="Focus on specific metric (optional)",
    ),
    archive_dir: Path = typer.Option(
        project_root / "data" / "archive",
        "--archive-dir",
        help="Path to archive directory",
    ),
    include_latest: bool = typer.Option(
        False,
        "--include-latest",
        help="Include real-time analysis if package not in archive",
    ),
) -> None:
    """Display trend analysis for a package across historical snapshots.

    This command shows how a package's health score and metrics have changed
    over time by analyzing data from archived snapshots.

    If --include-latest is specified and the package is not found in the archive,
    a real-time analysis will be performed to get the current snapshot.

    Examples:
        oss-sustain-guard trend requests
        oss-sustain-guard trend express --ecosystem javascript
        oss-sustain-guard trend flask --metric "Bus Factor"
        oss-sustain-guard trend newpackage --include-latest
    """
    console.print("\n[bold cyan]📊 Package Health Trend Analysis[/bold cyan]\n")

    analyzer = TrendAnalyzer(archive_dir=archive_dir)

    # Check if archive directory exists
    if not archive_dir.exists():
        console.print(f"[red]Archive directory not found: {archive_dir}[/red]")
        console.print(
            "[dim]Tip: Historical data is stored in data/archive/ directory.[/dim]"
        )
        return

    # List available dates
    available_dates = analyzer.list_available_dates()
    if not available_dates:
        console.print(
            f"[yellow]No historical snapshots found in {archive_dir}[/yellow]"
        )
        return

    console.print(
        f"[dim]Found {len(available_dates)} snapshots: {', '.join(available_dates)}[/dim]\n"
    )

    # Load package history
    history = analyzer.load_package_history(package_name, ecosystem)

    if not history:
        console.print(
            f"[yellow]ℹ️  No historical data found for package: {ecosystem}:{package_name}[/yellow]"
        )

        if include_latest:
            console.print(
                "[dim]📡 Attempting real-time analysis to get current snapshot...[/dim]\n"
            )

            # Try to resolve package to GitHub repository
            resolver = get_resolver(ecosystem)
            if resolver:
                repo_info = resolver.resolve_github_url(package_name)
                if repo_info:
                    owner, repo = repo_info
                    try:
                        # Perform real-time analysis
                        import os

                        if not os.getenv("GITHUB_TOKEN"):
                            console.print(
                                "[red]❌ GITHUB_TOKEN environment variable is required for real-time analysis[/red]"
                            )
                            console.print(
                                "[dim]Set GITHUB_TOKEN or use archived data only.[/dim]"
                            )
                            return

                        result = analyze_repository(owner, repo)

                        # Create a current snapshot entry
                        from oss_sustain_guard.trend import TrendData

                        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                        history = [
                            TrendData(
                                date=current_date,
                                package_name=package_name,
                                total_score=result.total_score,
                                metrics=[m._asdict() for m in result.metrics],
                                github_url=result.repo_url,
                            )
                        ]

                        console.print(
                            f"[green]✓ Real-time analysis complete for {result.repo_url}[/green]\n"
                        )
                        console.print(
                            "[dim]Note: This is a single snapshot. Historical comparison requires archived data.[/dim]\n"
                        )

                    except Exception as e:
                        console.print(f"[red]❌ Real-time analysis failed: {e}[/red]")
                        console.print(
                            "[dim]Package may not have a GitHub repository or API rate limit exceeded.[/dim]"
                        )
                        return
                else:
                    console.print(
                        f"[red]❌ Could not resolve package '{package_name}' to GitHub repository[/red]"
                    )
                    console.print(
                        "[dim]Package may not exist or doesn't have GitHub repository metadata.[/dim]"
                    )
                    return
            else:
                console.print(
                    f"[red]❌ No resolver available for ecosystem: {ecosystem}[/red]"
                )
                return
        else:
            console.print(
                "[dim]Package may not exist in snapshots or hasn't been analyzed yet.[/dim]"
            )
            console.print(
                "[dim]💡 Tip: Use --include-latest flag to perform real-time analysis[/dim]"
            )
            return

    # Display trend summary
    analyzer.display_trend_table(package_name, history)

    # Display metric-specific trends if requested
    if metric:
        console.print("\n")
        analyzer.display_metric_comparison(package_name, history, metric)
    else:
        # Show all metrics in summary view
        console.print("\n")
        console.print(
            "[dim]💡 Tip: Use --metric flag to see detailed trend for specific metric[/dim]"
        )
        console.print(
            '[dim]   Example: oss-sustain-guard trend {} --metric "Bus Factor"[/dim]\n'.format(
                package_name
            )
        )


@app.command()
def compare(
    package_name: str = typer.Argument(..., help="Package name to compare"),
    date1: str = typer.Argument(..., help="Earlier date (YYYY-MM-DD)"),
    date2: str = typer.Argument(..., help="Later date (YYYY-MM-DD)"),
    ecosystem: str = typer.Option(
        "python",
        "--ecosystem",
        "-e",
        help="Package ecosystem (python, javascript, rust, etc.)",
    ),
    archive_dir: Path = typer.Option(
        project_root / "data" / "archive",
        "--archive-dir",
        help="Path to archive directory",
    ),
) -> None:
    """Compare package health between two specific dates.

    This command generates a detailed comparison report showing how a package's
    metrics have changed between two snapshots.

    Examples:
        oss-sustain-guard compare requests 2025-12-11 2025-12-12
        oss-sustain-guard compare express 2025-11-01 2025-12-01 --ecosystem javascript
    """
    console.print("\n[bold cyan]📊 Package Health Comparison Report[/bold cyan]\n")

    analyzer = TrendAnalyzer(archive_dir=archive_dir)
    reporter = ComparisonReport(analyzer)

    # Validate dates
    available_dates = analyzer.list_available_dates()
    if not available_dates:
        console.print(
            f"[yellow]No historical snapshots found in {archive_dir}[/yellow]"
        )
        return

    if date1 not in available_dates:
        console.print(f"[red]Date {date1} not found in archive.[/red]")
        console.print(f"Available dates: {', '.join(available_dates)}")
        return

    if date2 not in available_dates:
        console.print(f"[red]Date {date2} not found in archive.[/red]")
        console.print(f"Available dates: {', '.join(available_dates)}")
        return

    # Generate comparison
    reporter.compare_dates(package_name, date1, date2, ecosystem)
    console.print()


@app.command()
def list_snapshots(
    archive_dir: Path = typer.Option(
        project_root / "data" / "archive",
        "--archive-dir",
        help="Path to archive directory",
    ),
) -> None:
    """List all available snapshot dates in the archive.

    This command shows all dates for which historical data is available,
    useful for determining valid date ranges for trend analysis.

    Example:
        oss-sustain-guard list-snapshots
    """
    console.print("\n[bold cyan]📅 Available Snapshot Dates[/bold cyan]\n")

    analyzer = TrendAnalyzer(archive_dir=archive_dir)
    available_dates = analyzer.list_available_dates()

    if not available_dates:
        console.print(
            f"[yellow]No historical snapshots found in {archive_dir}[/yellow]"
        )
        console.print(
            "[dim]Snapshots are automatically created by the build process.[/dim]"
        )
        return

    # Display in a table
    table = Table(title="Available Snapshots")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Date", style="white")
    table.add_column("Files", justify="right", style="dim")

    for idx, date in enumerate(available_dates, 1):
        date_dir = archive_dir / date
        # Count JSON files in the date directory
        json_files = list(date_dir.glob("*.json"))
        file_count = len(json_files)

        table.add_row(str(idx), date, str(file_count))

    console.print(table)
    console.print(f"\n[dim]Total snapshots: {len(available_dates)}[/dim]")
    console.print(
        f"[dim]Date range: {available_dates[0]} to {available_dates[-1]}[/dim]\n"
    )


if __name__ == "__main__":
    app()
