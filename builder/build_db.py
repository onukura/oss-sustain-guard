"""
Builds the static database of OSS sustainability metrics using Libraries.io.

Architecture (Cloudflare KV-based):
  1. Build phase (CI/CD, requires LIBRARIESIO_API_KEY + GITHUB_TOKEN):
     - Libraries.io API → Package metadata (repo URL)
     - GitHub GraphQL → Sustainability analysis (21 metrics + 5 models)
     - Upload → Cloudflare KV (globally distributed cache)
     - Local save → data/latest/*.json (build artifacts, not committed)

  2. User phase (Token-less):
     - CLI loads cached data from Cloudflare KV (shared remote cache)
     - Fallback to local cache (~/.cache/oss-sustain-guard)
     - No API tokens required for users

Sustainability Metrics (21 total):
  Core Metrics (12):
    - Contributor Redundancy, Maintainer Retention, Recent Activity
    - Change Request Resolution, Build Health, Funding Signals
    - Release Rhythm, Security Signals, Issue Responsiveness
    - Contributor Attraction, Contributor Retention, Review Health

  New Metrics (9):
    - Documentation Presence, Code of Conduct, PR Acceptance Ratio
    - Issue Resolution Duration, Organizational Diversity
    - Fork Activity, Project Popularity, License Clarity, PR Responsiveness

Metric Models (5 aggregated views):
  - Risk Model, Sustainability Model, Community Engagement Model
  - Project Maturity Model, Contributor Experience Model

Environment variables:
  - LIBRARIESIO_API_KEY: API key for Libraries.io (required for building)
  - GITHUB_TOKEN: GitHub personal access token (required for analysis)
"""

import argparse
import asyncio
import gzip
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

import httpx
from dotenv import load_dotenv
from rich.console import Console

from oss_sustain_guard.config import DEFAULT_CACHE_TTL, get_verify_ssl
from oss_sustain_guard.core import analyze_repository
from oss_sustain_guard.remote_cache import CloudflareKVClient
from oss_sustain_guard.schema_migrations import CURRENT_SCHEMA_VERSION

load_dotenv()

# Output paths
project_root = Path(__file__).resolve().parent.parent
LATEST_DIR = project_root / "data" / "latest"
DATABASE_PATH = project_root / "data" / "database.json"

# Libraries.io API configuration
LIBRARIES_IO_API_URL = "https://libraries.io/api"
LIBRARIESIO_API_KEY = os.getenv("LIBRARIESIO_API_KEY")
RATE_LIMIT_DELAY = 0.5  # 0.5 seconds between requests (faster, but within 60 req/min)
LIBRARIES_IO_META_SUFFIX = ".libraries_io.meta.json"

# Cloudflare KV configuration
CLOUDFLARE_WORKER_URL = os.getenv("CLOUDFLARE_WORKER_URL", "")
CF_WRITE_SECRET = os.getenv("CF_WRITE_SECRET", "")

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


class LibrariesIoFetchResult(NamedTuple):
    """Typed container for Libraries.io fetch outcomes."""

    packages: list[dict] | None
    etag: str | None
    last_modified: str | None
    not_modified: bool


def load_libraries_io_headers(ecosystem: str) -> tuple[str | None, str | None]:
    """Load cached ETag/Last-Modified for conditional requests."""

    meta_path = LATEST_DIR / f"{ecosystem}{LIBRARIES_IO_META_SUFFIX}"
    if not meta_path.exists():
        return None, None

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("etag"), data.get("last_modified")
    except (json.JSONDecodeError, IOError):
        return None, None


def save_libraries_io_headers(
    ecosystem: str, etag: str | None, last_modified: str | None
) -> None:
    """Persist ETag/Last-Modified to reuse in the next run."""

    meta_path = LATEST_DIR / f"{ecosystem}{LIBRARIES_IO_META_SUFFIX}"
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"etag": etag, "last_modified": last_modified}
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=True)


def existing_packages_from_latest(ecosystem: str) -> list[dict] | None:
    """Build a fallback package list from the latest stored dataset."""

    existing = load_existing_data(LATEST_DIR / f"{ecosystem}.json")

    # Handle wrapped format {"packages": {...}}
    if "packages" in existing and isinstance(existing["packages"], dict):
        packages_dict = existing["packages"]
    else:
        packages_dict = existing if isinstance(existing, dict) else {}

    if not packages_dict:
        return None

    packages: list[dict] = []
    for entry in packages_dict.values():
        github_url = entry.get("github_url")
        package_name = entry.get("package_name") or entry.get("name")
        if not (github_url and package_name):
            continue
        packages.append({"name": package_name, "repository_url": github_url})

    return packages or None


def load_existing_data(filepath: Path) -> dict:
    """Load existing JSON data (gzip or uncompressed), return empty dict if not found or invalid."""
    # Try gzip version first
    gz_filepath = (
        filepath.with_suffix(".json.gz") if filepath.suffix == ".json" else filepath
    )
    json_filepath = (
        filepath.with_suffix(".json") if filepath.suffix == ".gz" else filepath
    )

    for path in [gz_filepath, json_filepath]:
        if path.exists():
            try:
                if path.suffix == ".gz":
                    with gzip.open(path, "rt", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                return data if isinstance(data, dict) else {}
            except (json.JSONDecodeError, IOError):
                continue
    return {}


def upload_to_cloudflare_kv(
    data: dict, ecosystem: str, snapshot_date: str | None = None
) -> int:
    """
    Upload ecosystem data to Cloudflare KV.

    Uploads both latest data and historical snapshots:
    - Latest data: {schema}:{ecosystem}:{package} (always updated)
    - Historical data: {schema}:{ecosystem}:{package}:{date} (for trend analysis)

    Only uploads packages that have changed (based on metrics comparison).

    Args:
        data: Dictionary of package data keyed by db_key (e.g., "python:requests").
        ecosystem: Ecosystem name.
        snapshot_date: Date string (YYYY-MM-DD) for historical snapshot. If None, uses today.

    Returns:
        Number of packages successfully uploaded (counting both latest and historical).
    """
    if not CLOUDFLARE_WORKER_URL or not CF_WRITE_SECRET:
        return 0

    console = Console()
    console.print("[cyan]☁️  Uploading to Cloudflare KV...[/cyan]")

    # Use provided date or today
    if snapshot_date is None:
        snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        # Initialize client
        client = CloudflareKVClient(
            worker_url=CLOUDFLARE_WORKER_URL,
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        # Fetch existing data from KV to detect changes
        package_list = [(ecosystem, key.split(":")[-1]) for key in data.keys()]
        existing_kv_data = client.batch_get(package_list)

        # Detect changes and prepare upload entries
        latest_entries = {}  # Latest data (no date suffix)
        historical_entries = {}  # Historical data (with date suffix)

        for _db_key, new_data in data.items():
            package_name = new_data["package_name"]
            latest_key = client._make_key(ecosystem, package_name)
            historical_key = client._make_key(ecosystem, package_name, snapshot_date)
            existing_data = existing_kv_data.get(latest_key)

            # Upload if new or changed
            if not existing_data or _has_metric_changes(existing_data, new_data):
                latest_entries[latest_key] = new_data
                historical_entries[historical_key] = new_data

        if not latest_entries:
            console.print("[yellow]  ℹ️  No changes detected, skipping upload[/yellow]")
            return 0

        # Upload latest data in batches
        uploaded_latest = client.batch_put(latest_entries, CF_WRITE_SECRET)
        console.print(
            f"[green]  ✅ Uploaded {uploaded_latest}/{len(latest_entries)} latest packages[/green]"
        )

        # Upload historical data in batches
        uploaded_historical = client.batch_put(historical_entries, CF_WRITE_SECRET)
        console.print(
            f"[green]  ✅ Uploaded {uploaded_historical}/{len(historical_entries)} historical snapshots ({snapshot_date})[/green]"
        )

        total_uploaded = uploaded_latest + uploaded_historical
        console.print(
            f"[bold green]  ✅ Total uploaded: {total_uploaded} entries to Cloudflare KV[/bold green]"
        )
        return total_uploaded

    except Exception as e:
        console.print(f"[red]  ❌ Cloudflare KV upload failed: {e}[/red]")
        traceback.print_exc()
        return 0


def _has_metric_changes(old_data: dict, new_data: dict) -> bool:
    """
    Compare metrics between two package data dictionaries.

    Returns:
        True if metrics have changed, False otherwise.
    """
    old_metrics = old_data.get("metrics", [])
    new_metrics = new_data.get("metrics", [])

    if len(old_metrics) != len(new_metrics):
        return True

    old_metric_scores = {m.get("name"): m.get("score") for m in old_metrics}
    new_metric_scores = {m.get("name"): m.get("score") for m in new_metrics}

    return old_metric_scores != new_metric_scores


def save_ecosystem_data(
    data: dict,
    ecosystem: str,
    is_latest: bool = True,
    upload_to_cloudflare: bool = False,
    snapshot_date: str | None = None,
):
    """Save ecosystem data to appropriate directory with schema metadata as gzip.

    Args:
        data: Dictionary of package data keyed by db_key (e.g., "python:requests").
        ecosystem: Ecosystem name.
        is_latest: If True, save to latest/ directory.
        upload_to_cloudflare: If True, upload to Cloudflare KV.
        snapshot_date: Date string (YYYY-MM-DD) for historical snapshot. If None, uses today.
    """
    output_dir = LATEST_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{ecosystem}.json.gz"

    # Wrap data with schema metadata
    wrapped_data = {
        "_schema_version": CURRENT_SCHEMA_VERSION,
        "_generated_at": datetime.now(timezone.utc).isoformat(),
        "_ecosystem": ecosystem,
        "packages": data,
    }

    with gzip.open(filepath, "wt", encoding="utf-8") as f:
        json.dump(wrapped_data, f, indent=2, ensure_ascii=False, sort_keys=True)

    # Upload to Cloudflare KV if enabled (with historical snapshot support)
    if upload_to_cloudflare and CLOUDFLARE_WORKER_URL and CF_WRITE_SECRET:
        try:
            upload_to_cloudflare_kv(data, ecosystem, snapshot_date)
        except Exception as e:
            print(f"[WARNING] Failed to upload to Cloudflare KV: {e}")

    return filepath


def merge_ecosystem_files() -> dict:
    """Merge all ecosystem JSON files (gzip or uncompressed) from latest/ into single database.json."""
    merged = {}

    if not LATEST_DIR.exists():
        return merged

    # Process both .json.gz and .json files
    processed_ecosystems = set()
    for ecosystem_file in list(LATEST_DIR.glob("*.json.gz")) + list(
        LATEST_DIR.glob("*.json")
    ):
        # Extract ecosystem name (handle both .json.gz and .json)
        ecosystem_name = ecosystem_file.name.replace(".json.gz", "").replace(
            ".json", ""
        )

        # Skip if already processed (prefer .json.gz)
        if ecosystem_name in processed_ecosystems:
            continue
        processed_ecosystems.add(ecosystem_name)

        ecosystem_data = load_existing_data(ecosystem_file)
        # Handle both v1.x (flat dict) and v2.0 (wrapped with metadata)
        if "_schema_version" in ecosystem_data and "packages" in ecosystem_data:
            # v2.0 format
            merged.update(ecosystem_data["packages"])
        else:
            # v1.x format (backward compatibility)
            merged.update(ecosystem_data)

    return merged


def has_changes(old_data: dict, new_data: dict) -> bool:
    """Check if ecosystem data has meaningful changes.

    Note: Since total_score is profile-dependent and not stored in v2.0+,
    we compare metrics instead.
    """
    if len(old_data) != len(new_data):
        return True

    # Compare metrics instead of total_score (which is profile-dependent)
    for key in new_data:
        if key not in old_data:
            return True

        old_metrics = old_data[key].get("metrics", [])
        new_metrics = new_data[key].get("metrics", [])

        if len(old_metrics) != len(new_metrics):
            return True

        # Compare metric scores
        old_metric_scores = {m.get("name"): m.get("score") for m in old_metrics}
        new_metric_scores = {m.get("name"): m.get("score") for m in new_metrics}

        if old_metric_scores != new_metric_scores:
            return True

    return False


async def fetch_libraries_io_packages(
    libraries_io_ecosystem: str,
    limit: int = 500,
    etag: str | None = None,
    last_modified: str | None = None,
    fallback_packages: list[dict] | None = None,
) -> LibrariesIoFetchResult:
    """
    Fetch packages from Libraries.io API.

    Args:
        libraries_io_ecosystem: Libraries.io ecosystem name (e.g., "Pypi", "Npm")
        limit: Maximum number of packages to fetch

    Returns:
        List of package dicts with 'name' and 'repository_url' keys, or None on failure
    """
    if not LIBRARIESIO_API_KEY:
        print("[WARNING] LIBRARIESIO_API_KEY not set. Skipping API fetch.")
        return LibrariesIoFetchResult(None, etag, last_modified, False)

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
        print(f"  [DEBUG] API Key present: {bool(LIBRARIESIO_API_KEY)}")

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
                    "api_key": LIBRARIESIO_API_KEY,
                }

                print(f"  [DEBUG] Fetching page {page}...")

                # Retry logic for transient failures
                response = None
                last_error = None
                for attempt in range(max_retries):
                    try:
                        conditional_headers = {}
                        if etag:
                            conditional_headers["If-None-Match"] = etag
                        if last_modified:
                            conditional_headers["If-Modified-Since"] = last_modified

                        response = await client.get(
                            url, params=params, headers=conditional_headers or None
                        )

                        if response.status_code == httpx.codes.NOT_MODIFIED:
                            print(
                                "  [INFO] Libraries.io responded 304 Not Modified; using cached packages"
                            )
                            return LibrariesIoFetchResult(
                                fallback_packages, etag, last_modified, True
                            )

                        response.raise_for_status()
                        etag = response.headers.get("etag", etag)
                        last_modified = response.headers.get(
                            "last-modified", last_modified
                        )
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
                                return LibrariesIoFetchResult(
                                    all_packages[:limit], etag, last_modified, False
                                )
                            return LibrariesIoFetchResult(
                                None, etag, last_modified, False
                            )

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
        return LibrariesIoFetchResult(
            all_packages[:limit] if all_packages else None,
            etag,
            last_modified,
            False,
        )

    except Exception as e:
        print(f"[ERROR] Failed to fetch from Libraries.io: {type(e).__name__}: {e}")
        traceback.print_exc()
        return LibrariesIoFetchResult(None, etag, last_modified, False)


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
        # NOTE: total_score is NOT stored because it depends on the scoring profile.
        # It will be calculated at runtime based on the user's selected profile.
        now = datetime.now(timezone.utc).isoformat()
        analysis_data = {
            "ecosystem": ecosystem,
            "package_name": package_name,
            "github_url": analysis_result.repo_url,
            "metrics": [metric._asdict() for metric in analysis_result.metrics],
            "models": [model._asdict() for model in analysis_result.models],
            "signals": analysis_result.signals,
            "funding_links": analysis_result.funding_links,
            "is_community_driven": analysis_result.is_community_driven,
            "cache_metadata": {
                "fetched_at": now,
                "ttl_seconds": DEFAULT_CACHE_TTL,
                "source": "api",
            },
        }
        console.print(
            f"    [bold green]📊 Analysis complete. "
            f"({len(analysis_result.metrics)} metrics, {len(analysis_result.models)} models)[/bold green]"
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
    max_concurrent: int = 1,
    dry_run: bool = False,
    upload_to_cloudflare: bool = False,
) -> dict[str, Any]:
    """
    Process packages for an ecosystem with controlled concurrency.

    Args:
        ecosystem: Ecosystem name (python, javascript, etc.)
        packages: List of dicts with 'name' and 'repository_url' keys
        max_concurrent: Maximum number of concurrent tasks
        dry_run: If True, only collect URLs without analyzing
        upload_to_cloudflare: If True, upload to Cloudflare KV

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

    # Save progressively to ensure data persists even on timeout
    # Batch size: save every 100 packages
    batch_size = 100
    for i, (db_key, data) in enumerate(results):
        if data is not None:
            ecosystem_data[db_key] = data

        # Save periodically to ensure data persists even on timeout
        if (i + 1) % batch_size == 0 or (i + 1) == len(results):
            console.print(
                f"[cyan]  📊 Intermediate save: {i + 1}/{len(results)} packages processed[/cyan]"
            )
            save_ecosystem_data(
                ecosystem_data,
                ecosystem,
                is_latest=True,
                upload_to_cloudflare=upload_to_cloudflare,
            )

    return ecosystem_data


async def main(
    ecosystems: list[str] | None = None,
    max_concurrent: int = 1,
    limit: int = 5000,
    verify_ssl: bool = True,
    dry_run: bool = False,
    upload_to_cloudflare: bool = False,
):
    """
    Main function to build the database using Libraries.io.

    Args:
        ecosystems: List of specific ecosystems to process. If None, all are processed.
        max_concurrent: Maximum number of concurrent package processing tasks.
        limit: Maximum number of packages to fetch per ecosystem from Libraries.io.
        verify_ssl: If True, verify SSL certificates.
        dry_run: If True, only collect package URLs without analyzing via GitHub.
        upload_to_cloudflare: If True, upload results to Cloudflare KV.
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

    if not LIBRARIESIO_API_KEY:
        console.print(
            "[bold yellow]Warning: LIBRARIESIO_API_KEY environment variable is not set.[/bold yellow]"
        )
        console.print(
            "API-based fetching will not work. Attempting fallback packages if available."
        )
        # Continue anyway, but don't try to fetch from APIs

    # Check Cloudflare KV configuration if upload is requested
    if upload_to_cloudflare:
        if not CLOUDFLARE_WORKER_URL:
            console.print(
                "[bold red]Error: CLOUDFLARE_WORKER_URL environment variable is not set.[/bold red]"
            )
            console.print(
                "Please set it to your Cloudflare Worker URL (e.g., https://your-worker.workers.dev)"
            )
            sys.exit(1)
        if not CF_WRITE_SECRET:
            console.print(
                "[bold red]Error: CF_WRITE_SECRET environment variable is not set.[/bold red]"
            )
            console.print("Please set it to your Cloudflare Worker write secret.")
            sys.exit(1)
        console.print(
            f"[bold cyan]☁️  Cloudflare KV upload enabled: {CLOUDFLARE_WORKER_URL}[/bold cyan]"
        )

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

        cached_etag, cached_last_modified = load_libraries_io_headers(ecosystem)
        fallback_packages = existing_packages_from_latest(ecosystem)

        fetch_result = await fetch_libraries_io_packages(
            libraries_io_ecosystem=libraries_io_name,
            limit=limit,
            etag=cached_etag,
            last_modified=cached_last_modified,
            fallback_packages=fallback_packages,
        )

        if fetch_result.packages:
            packages_by_ecosystem[ecosystem] = fetch_result.packages
            console.print(
                f"  [cyan]✅ Using {len(fetch_result.packages)} packages"
                + (" (cached)" if fetch_result.not_modified else "")
            )
            save_libraries_io_headers(
                ecosystem, fetch_result.etag, fetch_result.last_modified
            )
        else:
            console.print(
                "  [yellow]⚠️  Could not fetch packages (check API key and rate limit)[/yellow]"
            )

    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    console.print(f"[cyan]📅 Snapshot date: {snapshot_date}[/cyan]\n")

    total_entries = 0
    updated_ecosystems = []

    # Process ecosystems sequentially (ensures each completed ecosystem is saved before timeout)
    for ecosystem, packages in packages_by_ecosystem.items():
        console.print(f"[bold cyan]📦 Processing {ecosystem}...[/bold cyan]")

        ecosystem_data = await process_ecosystem_packages(
            ecosystem, packages, max_concurrent, dry_run, upload_to_cloudflare
        )

        if not ecosystem_data:
            console.print(f"[yellow]⚠️  No data for {ecosystem}[/yellow]")
            continue

        # Check for changes and save immediately (before processing next ecosystem)
        old_data = load_existing_data(LATEST_DIR / f"{ecosystem}.json")

        if has_changes(old_data, ecosystem_data):
            save_ecosystem_data(
                ecosystem_data,
                ecosystem,
                is_latest=True,
                upload_to_cloudflare=upload_to_cloudflare,
            )
            save_ecosystem_data(
                ecosystem_data, ecosystem, is_latest=False, upload_to_cloudflare=False
            )
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

    # Calculate metrics summary from first entry (for display)
    sample_entry = next(iter(merged_data.values())) if merged_data else None
    metrics_count = len(sample_entry.get("metrics", [])) if sample_entry else 0
    models_count = len(sample_entry.get("models", [])) if sample_entry else 0

    console.print("[bold green]✨ Database build complete![/bold green]")
    console.print(f"  Total entries: {total_entries}")
    console.print(f"  Updated ecosystems: {', '.join(updated_ecosystems) or 'None'}")
    if metrics_count > 0:
        console.print(
            f"  Metrics per package: {metrics_count} sustainability indicators"
        )
        console.print(f"  Models per package: {models_count} aggregated views")
    console.print("  Output:")
    console.print(f"    - Latest: {LATEST_DIR}")
    console.print("    - Historical: Cloudflare KV")
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
        help="Maximum number of concurrent package processing tasks per ecosystem (default: 5 for GitHub Actions, use 1-2 for local development)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum number of packages to fetch per ecosystem from Libraries.io (default: 1000 for faster builds, use 5000 for comprehensive analysis)",
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
    parser.add_argument(
        "--upload-to-cloudflare",
        action="store_true",
        help="Upload results to Cloudflare KV (requires CLOUDFLARE_WORKER_URL and CF_WRITE_SECRET)",
    )

    args = parser.parse_args()

    asyncio.run(
        main(
            ecosystems=args.ecosystems,
            max_concurrent=args.max_concurrent,
            limit=args.limit,
            verify_ssl=not args.insecure,
            dry_run=args.dry_run,
            upload_to_cloudflare=args.upload_to_cloudflare,
        )
    )
