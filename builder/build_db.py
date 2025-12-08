"""
Builds the static database of OSS sustainability metrics using Libraries.io.

Architecture (Token-less Experience):
  1. Build phase (CI/CD, requires LIBRARIES_IO_API_KEY):
     - Libraries.io API → Package metadata (repo URL)
     - GitHub GraphQL → Sustainability analysis
     - Save → data/latest/*.json + data/archive/YYYY-MM-DD/*.json

  2. User phase (Token-less):
     - CLI loads cached data/latest/*.json from GitHub
     - No API tokens required for users
     - Fallback to local cache if GitHub unavailable

Environment variables:
  - LIBRARIES_IO_API_KEY: API key for Libraries.io (required for building)
  - GITHUB_TOKEN: GitHub personal access token (required for analysis)
"""

import argparse
import asyncio
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from rich.console import Console

from oss_sustain_guard.config import DEFAULT_CACHE_TTL, get_verify_ssl
from oss_sustain_guard.core import analyze_repository

load_dotenv()

# Output paths
project_root = Path(__file__).resolve().parent.parent
LATEST_DIR = project_root / "data" / "latest"
ARCHIVE_DIR = project_root / "data" / "archive"
DATABASE_PATH = project_root / "data" / "database.json"

# Libraries.io API configuration
LIBRARIES_IO_API_URL = "https://libraries.io/api"
LIBRARIES_IO_API_KEY = os.getenv("LIBRARIES_IO_API_KEY")
RATE_LIMIT_DELAY = 0.5  # 0.5 seconds between requests (faster, but within 60 req/min)

# Mapping of ecosystem names (Libraries.io → project)
ECOSYSTEM_MAPPING = {
    "NPM": "javascript",
    "Pypi": "python",
    "Cargo": "rust",
    "Maven": "java",
    "Packagist": "php",
    "Rubygems": "ruby",
    "NuGet": "csharp",
    "Go": "go",
    # Popular ecosystems (commented out for now)
    # "CocoaPods": "swift",  # Objective-C/Swift
    # "Pub": "dart",  # Dart
    # "CPAN": "perl",  # Perl
    # "CRAN": "r",  # R
    # "Clojars": "clojure",  # Clojure
    # "Hex": "elixir",  # Elixir
    # "Hackage": "haskell",  # Haskell
    # "Conda": "python",  # Alternative Python package manager
}

# Reverse mapping for lookups
REVERSE_ECOSYSTEM_MAPPING = {v: k for k, v in ECOSYSTEM_MAPPING.items()}


def load_existing_data(filepath: Path) -> dict:
    """Load existing JSON data, return empty dict if not found or invalid."""
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_ecosystem_data(data: dict, ecosystem: str, is_latest: bool = True):
    """Save ecosystem data to appropriate directory."""
    if is_latest:
        output_dir = LATEST_DIR
    else:
        snapshot_date = datetime.now().strftime("%Y-%m-%d")
        output_dir = ARCHIVE_DIR / snapshot_date

    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{ecosystem}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)

    return filepath


def merge_ecosystem_files() -> dict:
    """Merge all ecosystem JSON files from latest/ into single database.json."""
    merged = {}

    if not LATEST_DIR.exists():
        return merged

    for ecosystem_file in LATEST_DIR.glob("*.json"):
        ecosystem_data = load_existing_data(ecosystem_file)
        merged.update(ecosystem_data)

    return merged


def has_changes(old_data: dict, new_data: dict) -> bool:
    """Check if ecosystem data has meaningful changes."""
    if len(old_data) != len(new_data):
        return True

    old_scores = {k: v.get("total_score") for k, v in old_data.items()}
    new_scores = {k: v.get("total_score") for k, v in new_data.items()}

    return old_scores != new_scores


async def fetch_libraries_io_packages(
    libraries_io_ecosystem: str, limit: int = 500
) -> list[dict] | None:
    """
    Fetch packages from Libraries.io API.

    Args:
        libraries_io_ecosystem: Libraries.io ecosystem name (e.g., "Pypi", "Npm")
        limit: Maximum number of packages to fetch

    Returns:
        List of package dicts with 'name' and 'repository_url' keys, or None on failure
    """
    if not LIBRARIES_IO_API_KEY:
        print("[WARNING] LIBRARIES_IO_API_KEY not set. Skipping API fetch.")
        return None

    try:
        headers = {
            "User-Agent": "oss-sustain-guard/2.0 (https://github.com/onukura/oss-sustain-guard)"
        }
        all_packages = []
        per_page = 100  # Max allowed by Libraries.io
        page = 1
        max_retries = 3
        retry_delay = 2.0  # seconds

        print(
            f"  [DEBUG] Using Libraries.io API with ecosystem: {libraries_io_ecosystem}"
        )
        print(f"  [DEBUG] API Key present: {bool(LIBRARIES_IO_API_KEY)}")

        async with httpx.AsyncClient(
            verify=get_verify_ssl(), timeout=60, headers=headers
        ) as client:
            while len(all_packages) < limit:
                url = f"{LIBRARIES_IO_API_URL}/search"
                params = {
                    "platforms": libraries_io_ecosystem,
                    "sort": "rank",  # Most popular first
                    "page": page,
                    "per_page": per_page,
                    "api_key": LIBRARIES_IO_API_KEY,
                }

                print(f"  [DEBUG] Fetching page {page}...")

                # Retry logic for transient failures
                response = None
                last_error = None
                for attempt in range(max_retries):
                    try:
                        response = await client.get(url, params=params)
                        response.raise_for_status()
                        print(f"  [DEBUG] Got response: {response.status_code}")
                        break
                    except (
                        httpx.ReadError,
                        httpx.ConnectError,
                        httpx.TimeoutException,
                    ) as e:
                        last_error = e
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (
                                2**attempt
                            )  # Exponential backoff
                            print(
                                f"  [WARNING] Attempt {attempt + 1} failed: {type(e).__name__}. Retrying in {wait_time}s..."
                            )
                            await asyncio.sleep(wait_time)
                        else:
                            print(
                                f"  [ERROR] All {max_retries} attempts failed. Stopping fetch."
                            )
                            # Return what we've collected so far
                            if all_packages:
                                print(
                                    f"  [INFO] Returning {len(all_packages)} packages collected so far"
                                )
                                return all_packages[:limit]
                            return None

                if response is None:
                    raise last_error or Exception(
                        "Failed to get response after retries"
                    )

                await asyncio.sleep(
                    RATE_LIMIT_DELAY
                )  # Rate limiting: 60 requests/minute

                data = response.json()
                if not data or not isinstance(data, list):
                    print("  [DEBUG] No more data or invalid response. Breaking.")
                    break

                print(f"  [DEBUG] Page {page}: Got {len(data)} items")

                for pkg in data:
                    if len(all_packages) >= limit:
                        break
                    # Extract repository information
                    if pkg.get("repository_url"):
                        all_packages.append(
                            {
                                "name": pkg.get("name", ""),
                                "repository_url": pkg.get("repository_url", ""),
                            }
                        )

                if len(data) < per_page:
                    print("  [DEBUG] Got fewer items than per_page. Breaking.")
                    break

                page += 1

        print(f"  [DEBUG] Total fetched: {len(all_packages)}")
        return all_packages[:limit] if all_packages else None

    except Exception as e:
        print(f"[ERROR] Failed to fetch from Libraries.io: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None


def parse_github_url(github_url: str) -> tuple[str, str] | None:
    """
    Parse GitHub URL to extract owner and repo name.

    Args:
        github_url: GitHub repository URL

    Returns:
        Tuple of (owner, repo) or None if parsing fails
    """
    if not github_url:
        return None

    # Handle various GitHub URL formats
    github_url = github_url.rstrip("/")
    if github_url.endswith(".git"):
        github_url = github_url[:-4]

    # Extract from https://github.com/owner/repo
    if "github.com/" in github_url:
        parts = github_url.split("github.com/")[1].split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]

    return None


async def process_package(
    package_name: str,
    github_url: str,
    ecosystem: str,
    console: Console,
) -> tuple[str, dict[str, Any] | None]:
    """
    Process a single package: analyze its GitHub repository.

    Args:
        package_name: Name of the package
        github_url: GitHub repository URL
        ecosystem: Ecosystem name (python, javascript, etc.)
        console: Rich console for output

    Returns:
        Tuple of (db_key, analysis_data) or (db_key, None) if failed
    """
    db_key = f"{ecosystem}:{package_name}"
    console.print(f"  Processing: [bold magenta]{package_name}[/bold magenta]")

    # Parse GitHub URL
    repo_info = parse_github_url(github_url)
    if not repo_info:
        console.print(
            f"    [red]❌ Could not parse GitHub URL: {github_url}. Skipping.[/red]"
        )
        return db_key, None

    owner, name = repo_info
    console.print(
        f"    [green]✅ Repository:[/green] https://github.com/{owner}/{name}"
    )

    # Analyze the repository
    try:
        analysis_result = analyze_repository(owner, name)

        # Store the result with cache metadata
        now = datetime.now(timezone.utc).isoformat()
        analysis_data = {
            "ecosystem": ecosystem,
            "package_name": package_name,
            "github_url": analysis_result.repo_url,
            "total_score": analysis_result.total_score,
            "metrics": [metric._asdict() for metric in analysis_result.metrics],
            "cache_metadata": {
                "fetched_at": now,
                "ttl_seconds": DEFAULT_CACHE_TTL,
                "source": "api",
            },
        }
        console.print(
            f"    [bold green]📊 Analysis complete. Score: {analysis_result.total_score}/100[/bold green]"
        )
        return db_key, analysis_data

    except Exception as e:
        console.print(
            f"    [bold red]❗️ Error analyzing {owner}/{name}: {e}[/bold red]"
        )
        return db_key, None


async def process_ecosystem_packages(
    ecosystem: str,
    packages: list[dict],
    max_concurrent: int = 5,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Process packages for an ecosystem with controlled concurrency.

    Args:
        ecosystem: Ecosystem name (python, javascript, etc.)
        packages: List of dicts with 'name' and 'repository_url' keys
        max_concurrent: Maximum number of concurrent tasks
        dry_run: If True, only collect URLs without analyzing

    Returns:
        Dictionary of ecosystem data keyed by db_key
    """
    console = Console()

    console.print(f"[bold cyan]📦 Ecosystem: {ecosystem}[/bold cyan]")
    console.print(
        f"[cyan]  Processing {len(packages)} packages {'(dry run)' if dry_run else ''}...[/cyan]"
    )

    ecosystem_data = {}

    if dry_run:
        # Just collect URLs without GitHub analysis
        for i, pkg in enumerate(packages[:10]):  # Limit to first 10 in dry run
            repo_info = parse_github_url(pkg["repository_url"])
            if repo_info:
                owner, name = repo_info
                db_key = f"{ecosystem}:{pkg['name']}"
                ecosystem_data[db_key] = {
                    "ecosystem": ecosystem,
                    "package_name": pkg["name"],
                    "github_url": f"https://github.com/{owner}/{name}",
                    "total_score": 0,  # Placeholder
                    "metrics": [],  # Placeholder
                }
                console.print(f"  [{i + 1}/10] {pkg['name']} -> {owner}/{name}")
        return ecosystem_data

    # Use a semaphore to limit concurrent tasks
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(pkg: dict) -> tuple[str, dict[str, Any] | None]:
        async with semaphore:
            return await process_package(
                pkg["name"],
                pkg["repository_url"],
                ecosystem,
                console,
            )

    # Process all packages concurrently with controlled concurrency
    tasks = [process_with_semaphore(pkg) for pkg in packages]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    for db_key, data in results:
        if data is not None:
            ecosystem_data[db_key] = data

    return ecosystem_data


async def main(
    ecosystems: list[str] | None = None,
    max_concurrent: int = 5,
    verify_ssl: bool = True,
    dry_run: bool = False,
):
    """
    Main function to build the database using Libraries.io.

    Args:
        ecosystems: List of specific ecosystems to process. If None, all are processed.
        max_concurrent: Maximum number of concurrent package processing tasks.
        verify_ssl: If True, verify SSL certificates.
        dry_run: If True, only collect package URLs without analyzing via GitHub.
    """
    console = Console()

    # Configure SSL verification
    from oss_sustain_guard import config

    config.VERIFY_SSL = verify_ssl

    # Check for required environment variables
    from oss_sustain_guard.core import GITHUB_TOKEN

    if not GITHUB_TOKEN:
        console.print(
            "[bold red]Error: GITHUB_TOKEN environment variable is not set.[/bold red]"
        )
        console.print(
            "Please set it to a valid GitHub personal access token with 'public_repo' scope."
        )
        console.print(
            "[yellow]For testing without tokens, use fallback packages instead.[/yellow]"
        )
        sys.exit(1)

    if not LIBRARIES_IO_API_KEY:
        console.print(
            "[bold yellow]Warning: LIBRARIES_IO_API_KEY environment variable is not set.[/bold yellow]"
        )
        console.print(
            "API-based fetching will not work. Attempting fallback packages if available."
        )
        # Continue anyway, but don't try to fetch from APIs

    console.print(
        "[bold yellow]🚀 Starting database build using Libraries.io...[/bold yellow]"
    )

    # Filter ecosystems if specified
    if ecosystems:
        invalid = [e for e in ecosystems if e not in REVERSE_ECOSYSTEM_MAPPING]
        if invalid:
            console.print(f"[red]❌ Invalid ecosystems: {', '.join(invalid)}[/red]")
            console.print(
                f"[cyan]Available: {', '.join(REVERSE_ECOSYSTEM_MAPPING.keys())}[/cyan]"
            )
            sys.exit(1)
        target_ecosystems = ecosystems
    else:
        target_ecosystems = list(REVERSE_ECOSYSTEM_MAPPING.keys())

    console.print(
        f"[bold cyan]🎯 Targeting ecosystems: {', '.join(target_ecosystems)}[/bold cyan]\n"
    )

    # Fetch packages from Libraries.io for each ecosystem
    packages_by_ecosystem = {}
    for ecosystem in target_ecosystems:
        libraries_io_name = REVERSE_ECOSYSTEM_MAPPING[ecosystem]
        console.print(
            f"[bold cyan]Fetching packages from Libraries.io for {ecosystem}...[/bold cyan]"
        )

        packages = await fetch_libraries_io_packages(libraries_io_name, 5000)
        if packages:
            packages_by_ecosystem[ecosystem] = packages
            console.print(f"  [cyan]✅ Fetched {len(packages)} packages[/cyan]")
        else:
            console.print(
                "  [yellow]⚠️  Could not fetch packages (check API key and rate limit)[/yellow]"
            )

    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    console.print(f"[cyan]📅 Snapshot date: {snapshot_date}[/cyan]\n")

    total_entries = 0
    updated_ecosystems = []

    # Process all ecosystems concurrently
    ecosystem_results = await asyncio.gather(
        *[
            process_ecosystem_packages(ecosystem, packages, max_concurrent, dry_run)
            for ecosystem, packages in packages_by_ecosystem.items()
        ],
        return_exceptions=False,
    )

    for ecosystem_data, ecosystem in zip(
        ecosystem_results, packages_by_ecosystem.keys(), strict=True
    ):
        if not ecosystem_data:
            console.print(f"[yellow]⚠️  No data for {ecosystem}[/yellow]")
            continue

        # Check for changes and save
        old_data = load_existing_data(LATEST_DIR / f"{ecosystem}.json")

        if has_changes(old_data, ecosystem_data):
            save_ecosystem_data(ecosystem_data, ecosystem, is_latest=True)
            save_ecosystem_data(ecosystem_data, ecosystem, is_latest=False)
            updated_ecosystems.append(ecosystem)
            console.print(
                f"  [bold green]✨ Saved {len(ecosystem_data)} entries[/bold green]"
            )
        else:
            console.print("[yellow]ℹ️  No changes detected[/yellow]")

        total_entries += len(ecosystem_data)

    # Merge all latest/ files into database.json for compatibility
    console.print(
        "\n[bold yellow]💾 Merging ecosystem files into database.json...[/bold yellow]"
    )
    merged_data = merge_ecosystem_files()

    with open(DATABASE_PATH, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, indent=2, ensure_ascii=False, sort_keys=True)

    console.print("[bold green]✨ Database build complete![/bold green]")
    console.print(f"  Total entries: {total_entries}")
    console.print(f"  Updated ecosystems: {', '.join(updated_ecosystems) or 'None'}")
    console.print("  Output:")
    console.print(f"    - Latest: {LATEST_DIR}")
    console.print(f"    - Archive: {ARCHIVE_DIR / snapshot_date}")
    console.print(f"    - Compatibility: {DATABASE_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build OSS Sustain Guard database using Libraries.io"
    )
    parser.add_argument(
        "--ecosystems",
        type=str,
        nargs="+",
        help="Specific ecosystems to process (e.g., --ecosystems python javascript). If not specified, all ecosystems are processed.",
        choices=list(REVERSE_ECOSYSTEM_MAPPING.keys()),
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum number of concurrent package processing tasks per ecosystem (default: 5)",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable SSL certificate verification (useful for environments with certificate issues)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect package URLs without GitHub analysis (useful for testing)",
    )

    args = parser.parse_args()

    asyncio.run(
        main(
            ecosystems=args.ecosystems,
            max_concurrent=args.max_concurrent,
            verify_ssl=not args.insecure,
            dry_run=args.dry_run,
        )
    )
