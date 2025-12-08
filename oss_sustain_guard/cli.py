"""
Command-line interface for OSS Sustain Guard.
"""

import json
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table

from oss_sustain_guard.cache import clear_cache, get_cache_stats, load_cache, save_cache
from oss_sustain_guard.config import (
    get_verify_ssl,
    is_cache_enabled,
    is_package_excluded,
    set_cache_dir,
    set_cache_ttl,
    set_verify_ssl,
)
from oss_sustain_guard.core import AnalysisResult, Metric, analyze_repository
from oss_sustain_guard.resolvers import detect_ecosystems, get_resolver
from oss_sustain_guard.resolvers.python import (
    detect_lockfiles,
    get_github_url_from_pypi,
    get_packages_from_lockfile,
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
        use_cache: If False, skip cache and load fresh data.

    Returns:
        Dictionary of package data keyed by "ecosystem:package_name".
    """
    merged = {}

    # List of ecosystems to load
    ecosystems = ["python", "javascript", "ruby", "rust", "php", "java", "csharp"]

    # Load from cache first if enabled
    if use_cache and is_cache_enabled():
        for ecosystem in ecosystems:
            cached_data = load_cache(ecosystem)
            if cached_data:
                merged.update(cached_data)
                console.print(
                    f"[dim]Loaded {len(cached_data)} entries from cache: {ecosystem}[/dim]"
                )

    # Determine which ecosystems need fresh data
    ecosystems_to_fetch = []
    if not use_cache or not is_cache_enabled():
        # Need all ecosystems if not using cache
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
                    if use_cache and is_cache_enabled():
                        save_cache(ecosystem, data)
            except Exception as e:
                # Silently skip GitHub errors for now, will try local fallback
                console.print(
                    f"[yellow]Warning: Failed to load {ecosystem} data from GitHub: {e}[/yellow]"
                )

        # If GitHub loading failed, fall back to local data/latest/
        if not github_success and LATEST_DIR.exists():
            for ecosystem in ecosystems_to_fetch:
                ecosystem_file = LATEST_DIR / f"{ecosystem}.json"
                if ecosystem_file.exists():
                    try:
                        with open(ecosystem_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            merged.update(data)
                            console.print(
                                f"Loaded {ecosystem} data from local fallback."
                            )

                            # Save to cache if enabled
                            if use_cache and is_cache_enabled():
                                save_cache(ecosystem, data)
                    except Exception as e:
                        console.print(
                            f"[yellow]Warning: Failed to load {ecosystem_file}: {e}[/yellow]"
                        )

    return merged


def display_results(results: list[AnalysisResult]):
    """Display the analysis results in a rich table."""
    table = Table(title="OSS Sustain Guard Report")
    table.add_column("Package", justify="left", style="cyan", no_wrap=True)
    table.add_column("Score", justify="center", style="magenta")
    table.add_column("Risk", justify="left", style="red")
    table.add_column("Details", justify="left")

    for result in results:
        risk_color = "green"
        if result.total_score < 50:
            risk_color = "red"
        elif result.total_score < 80:
            risk_color = "yellow"

        highest_risk = "None"
        details = []
        for metric in result.metrics:
            if metric.risk in ("High", "Critical"):
                details.append(f"[{metric.risk}] {metric.message}")
        if details:
            highest_risk = f"[{risk_color}]{' / '.join(details)}[/{risk_color}]"

        table.add_row(
            result.repo_url.replace("https://github.com/", ""),
            f"[{risk_color}]{result.total_score}/100[/{risk_color}]",
            highest_risk,
            f"Analyzed: {result.metrics[0].message}",  # Placeholder
        )

    console.print(table)


def display_results_detailed(results: list[AnalysisResult]):
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

        # Metrics table
        metrics_table = Table(show_header=True, header_style="bold magenta")
        metrics_table.add_column("Metric", style="cyan", no_wrap=True)
        metrics_table.add_column("Score", justify="center", style="magenta")
        metrics_table.add_column("Max", justify="center", style="magenta")
        metrics_table.add_column("Risk", justify="left", style="red")
        metrics_table.add_column("Message", justify="left")

        for metric in result.metrics:
            # Risk color coding
            risk_style = "green"
            if metric.risk in ("Critical", "High"):
                risk_style = "red"
            elif metric.risk == "Medium":
                risk_style = "yellow"

            metrics_table.add_row(
                metric.name,
                f"[cyan]{metric.score}[/cyan]",
                f"[cyan]{metric.max_score}[/cyan]",
                f"[{risk_style}]{metric.risk}[/{risk_style}]",
                metric.message,
            )

        console.print(metrics_table)


@app.command()
def check_legacy(
    packages: list[str] = typer.Argument(
        ...,
        help="[DEPRECATED: Use 'check' instead] List of packages to check (e.g., 'requests fastapi') or a path to a requirements.txt file.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Display detailed metrics for each package.",
    ),
    include_lock: bool = typer.Option(
        False,
        "--include-lock",
        "-l",
        help="Include packages from lockfiles (poetry.lock, uv.lock, Pipfile.lock) in the current directory.",
    ),
    insecure: bool = typer.Option(
        False,
        "--insecure",
        help="Disable SSL certificate verification for HTTPS requests.",
    ),
):
    """[DEPRECATED: Use 'check' instead] Analyze the sustainability of specified Python packages."""
    set_verify_ssl(not insecure)
    db = load_database()
    results_to_display = []
    packages_to_analyze = []

    if len(packages) == 1 and Path(packages[0]).is_file():
        console.print(f"📄 Reading packages from [bold]{packages[0]}[/bold]")
        with open(packages[0], "r", encoding="utf-8") as f:
            # Basic parsing, ignores versions and comments
            package_list = [
                line.strip().split("==")[0]
                for line in f
                if line.strip() and not line.startswith("#")
            ]
            packages_to_analyze.extend(package_list)
    else:
        packages_to_analyze.extend(packages)

    # If --include-lock is specified, detect and parse lockfiles
    if include_lock:
        lockfiles = detect_lockfiles(".")
        if lockfiles:
            console.print(
                f"🔒 Found {len(lockfiles)} lockfile(s), extracting packages..."
            )
            for lockfile in lockfiles:
                console.print(f"   -> Parsing [bold]{lockfile.name}[/bold]")
                lock_packages = get_packages_from_lockfile(lockfile)
                console.print(f"      Found {len(lock_packages)} package(s)")
                packages_to_analyze.extend(lock_packages)
        else:
            console.print(
                "   [yellow]No lockfiles detected in current directory.[/yellow]"
            )

    # Remove duplicates while preserving order
    seen = set()
    unique_packages = []
    for pkg in packages_to_analyze:
        if pkg not in seen:
            seen.add(pkg)
            unique_packages.append(pkg)
    packages_to_analyze = unique_packages

    console.print(f"🔍 Analyzing {len(packages_to_analyze)} package(s)...")

    excluded_count = 0
    for pkg_name in packages_to_analyze:
        # Check if package is excluded
        if is_package_excluded(pkg_name):
            excluded_count += 1
            console.print(
                f"  -> Skipping [bold yellow]{pkg_name}[/bold yellow] (excluded)"
            )
            continue

        if pkg_name in db:
            console.print(f"  -> Found [bold green]{pkg_name}[/bold green] in cache.")
            cached_data = db[pkg_name]
            # Reconstruct AnalysisResult from cached dict
            result = AnalysisResult(
                repo_url=cached_data["github_url"],
                total_score=cached_data["total_score"],
                metrics=[
                    Metric(
                        m["name"], m["score"], m["max_score"], m["message"], m["risk"]
                    )
                    for m in cached_data["metrics"]
                ],
            )
            results_to_display.append(result)
        else:
            console.print(
                f"  -> [bold yellow]{pkg_name}[/bold yellow] not in cache. Performing real-time analysis..."
            )
            repo_info = get_github_url_from_pypi(pkg_name)
            if repo_info:
                owner, name = repo_info
                try:
                    analysis_result = analyze_repository(owner, name)
                    results_to_display.append(analysis_result)
                except Exception as e:
                    console.print(f"    [red]Error analyzing {owner}/{name}: {e}[/red]")
            else:
                console.print(
                    f"    [red]Could not resolve GitHub repository for {pkg_name}.[/red]"
                )

    if results_to_display:
        if verbose:
            display_results_detailed(results_to_display)
        else:
            display_results(results_to_display)
        if excluded_count > 0:
            console.print(
                f"\n⏭️  Skipped {excluded_count} excluded package(s).",
                style="yellow",
            )
    else:
        console.print("No results to display.")


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
) -> AnalysisResult | None:
    """
    Analyze a single package.

    Args:
        package_name: Name of the package.
        ecosystem: Ecosystem name (python, javascript, go, rust).
        db: Cached database dictionary.

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
        # Reconstruct AnalysisResult from cached dict
        result = AnalysisResult(
            repo_url=cached_data.get("github_url", "unknown"),
            total_score=cached_data.get("total_score", 0),
            metrics=[
                Metric(
                    m["name"],
                    m["score"],
                    m["max_score"],
                    m["message"],
                    m["risk"],
                )
                for m in cached_data.get("metrics", [])
            ],
        )
        return result

    # Resolve GitHub URL using appropriate resolver
    resolver = get_resolver(ecosystem)
    if not resolver:
        console.print(f"  -> [red]Unknown ecosystem: {ecosystem}[/red]")
        return None

    repo_info = resolver.resolve_github_url(package_name)
    if not repo_info:
        console.print(
            f"  -> [red]Could not resolve GitHub repository for {db_key}.[/red]"
        )
        return None

    owner, repo_name = repo_info
    console.print(f"  -> [bold yellow]{db_key}[/bold yellow] analyzing real-time...")

    try:
        analysis_result = analyze_repository(owner, repo_name)
        return analysis_result
    except Exception as e:
        console.print(f"    [red]Error analyzing {owner}/{repo_name}: {e}[/red]")
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
        help="Display detailed metrics for each package.",
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
):
    """Analyze the sustainability of packages across multiple ecosystems (Python, JavaScript, Go, Rust, PHP, Java, C#)."""
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

    # If no packages specified, auto-detect from manifest files only
    auto_detect_mode = not packages
    if auto_detect_mode:
        console.print("🔍 No packages specified. Auto-detecting from manifest files...")
        detected_ecosystems = detect_ecosystems(".")
        if detected_ecosystems:
            console.print(f"✅ Detected ecosystems: {', '.join(detected_ecosystems)}")
            for detected_eco in detected_ecosystems:
                resolver = get_resolver(detected_eco)
                if not resolver:
                    continue

                # Check for manifest files only (ignore lockfiles in auto-detect mode)
                current_dir = Path(".")
                for manifest_name in resolver.get_manifest_files():
                    manifest_path = current_dir / manifest_name
                    if manifest_path.exists():
                        console.print(f"📋 Found manifest file: {manifest_name}")
                        # Parse manifest to extract dependencies
                        try:
                            manifest_packages = resolver.parse_manifest(
                                str(manifest_path)
                            )
                            console.print(
                                f"   Found {len(manifest_packages)} package(s) in {manifest_name}"
                            )
                            for pkg_info in manifest_packages:
                                packages_to_analyze.append(
                                    (detected_eco, pkg_info.name)
                                )
                        except Exception as e:
                            console.print(
                                f"   [yellow]Warning: Failed to parse {manifest_name}: {e}[/yellow]"
                            )
                        break
        else:
            # No manifest files found - silently exit (useful for pre-commit hooks)
            raise typer.Exit(code=0)
    else:
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
            detected_ecosystems = detect_ecosystems(".")
            if detected_ecosystems:
                console.print(
                    f"🔍 Detected ecosystems: {', '.join(detected_ecosystems)}"
                )
                for detected_eco in detected_ecosystems:
                    resolver = get_resolver(detected_eco)
                    if not resolver:
                        continue

                    lockfiles = resolver.detect_lockfiles(".")
                    if lockfiles:
                        console.print(
                            f"🔒 Found lockfile(s) for {detected_eco}: {', '.join(str(l.name) for l in lockfiles)}"
                        )
                        for lockfile in lockfiles:
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
            console.print(
                "   [yellow]No lockfiles detected in current directory.[/yellow]"
            )

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

        result = analyze_package(pkg_name, eco, db)
        if result:
            results_to_display.append(result)

    if results_to_display:
        if verbose:
            display_results_detailed(results_to_display)
        else:
            display_results(results_to_display)
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


if __name__ == "__main__":
    app()
