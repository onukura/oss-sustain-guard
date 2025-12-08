"""
Builds the static database of OSS sustainability metrics (v2: LFS-optimized).

This script fetches data for popular packages across multiple ecosystems,
analyzes their GitHub repositories, and stores results in date-partitioned
JSON files for efficient Git LFS management.

Database structure:
  data/latest/
    python.json, javascript.json, ...      (current week's data)
  data/archive/
    YYYY-MM-DD/python.json, ...            (historical snapshots)
  data/database.json                       (compatibility layer: merged latest/)
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from fallback_packages import PACKAGES_BY_ECOSYSTEM, get_fallback_packages
from rich.console import Console

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.core import analyze_repository
from oss_sustain_guard.resolvers import get_resolver

project_root = Path(__file__).resolve().parent.parent

# Output paths
LATEST_DIR = project_root / "data" / "latest"
ARCHIVE_DIR = project_root / "data" / "archive"
DATABASE_PATH = project_root / "data" / "database.json"


def load_existing_data(filepath: Path) -> dict:
    """Load existing JSON data, return empty dict if not found or invalid."""
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, IOError):
            # If file is corrupted or empty, return empty dict
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


async def fetch_top_packages(ecosystem: str, limit: int = 5000) -> list[str] | None:
    """
    Fetch top packages from the ecosystem registry using multiple strategies.
    Falls back to predefined popular packages if API fetch fails.

    Args:
        ecosystem: The ecosystem name (python, javascript, etc.)
        limit: Maximum number of packages to fetch (default 5000)

    Returns:
        List of package names or None if not available
    """
    console = Console()

    try:
        if ecosystem == "python":
            # Strategy 1: Codeload via API or fallback to popular
            packages = await _fetch_pypi_packages(limit)
            if not packages:
                packages = get_fallback_packages("python")[:limit]
                console.print(
                    "  [yellow]📚 Using popular packages for PyPI (API unavailable)[/yellow]"
                )
            else:
                console.print(
                    f"  [cyan]📥 Fetched {len(packages)} top packages from PyPI[/cyan]"
                )
            return packages

        elif ecosystem == "javascript":
            # npm registry API
            packages = await _fetch_javascript_packages(limit)
            if not packages:
                packages = get_fallback_packages("javascript")[:limit]
                console.print(
                    "  [yellow]📚 Using popular packages for npm (API unavailable)[/yellow]"
                )
            else:
                console.print(
                    f"  [cyan]📥 Fetched {len(packages)} top packages from npm[/cyan]"
                )
            return packages

        elif ecosystem == "ruby":
            # RubyGems API
            packages = await _fetch_rubygems_packages(limit)
            if not packages:
                packages = get_fallback_packages("ruby")[:limit]
                console.print(
                    "  [yellow]📚 Using popular packages for RubyGems (API unavailable)[/yellow]"
                )
            else:
                console.print(
                    f"  [cyan]📥 Fetched {len(packages)} top packages from RubyGems[/cyan]"
                )
            return packages

        elif ecosystem == "rust":
            # Crates.io API with pagination
            packages = await _fetch_crates_io_packages(limit)
            if not packages:
                packages = get_fallback_packages("rust")[:limit]
                console.print(
                    "  [yellow]📚 Using popular packages for Rust (Crates.io unavailable)[/yellow]"
                )
            else:
                console.print(
                    f"  [cyan]📥 Fetched {len(packages)} top packages from Crates.io[/cyan]"
                )
            return packages

        elif ecosystem == "php":
            # Packagist list
            packages = await _fetch_packagist_packages(limit)
            if not packages:
                packages = get_fallback_packages("php")[:limit]
                console.print(
                    "  [yellow]📚 Using popular packages for Packagist (API unavailable)[/yellow]"
                )
            else:
                console.print(
                    f"  [cyan]📥 Fetched {len(packages)} top packages from Packagist[/cyan]"
                )
            return packages

        elif ecosystem == "java":
            # Maven Central
            packages = await _fetch_maven_packages(limit)
            if not packages:
                packages = get_fallback_packages("java")[:limit]
                console.print(
                    "  [yellow]📚 Using popular packages for Maven Central (API unavailable)[/yellow]"
                )
            else:
                console.print(
                    f"  [cyan]📥 Fetched {len(packages)} top packages from Maven Central[/cyan]"
                )
            return packages

        elif ecosystem == "csharp":
            # NuGet API
            packages = await _fetch_csharp_packages(limit)
            if not packages:
                packages = get_fallback_packages("csharp")[:limit]
                console.print(
                    "  [yellow]📚 Using popular packages for NuGet (API unavailable)[/yellow]"
                )
            else:
                console.print(
                    f"  [cyan]📥 Fetched {len(packages)} top packages from NuGet[/cyan]"
                )
            return packages

        elif ecosystem == "go":
            # Go modules - fetch from Awesome Go list
            packages = await _fetch_go_packages(limit)
            if not packages:
                packages = get_fallback_packages("go")[:limit]
                console.print(
                    "  [yellow]📚 Using popular packages for Go modules (Awesome Go unavailable)[/yellow]"
                )
            else:
                console.print(
                    f"  [cyan]📥 Fetched {len(packages)} popular packages from Awesome Go[/cyan]"
                )
            return packages

        else:
            console.print(
                f"  [yellow]⚠️  No registry available for ecosystem: {ecosystem}[/yellow]"
            )
            return None

    except httpx.RequestError as e:
        console.print(
            f"  [red]❌ Failed to fetch packages from {ecosystem} registry: {e}[/red]"
        )
        # Return popular packages as fallback
        return get_fallback_packages(ecosystem)[:limit]
    except Exception as e:
        console.print(f"  [red]❌ Error: {e}[/red]")
        return get_fallback_packages(ecosystem)[:limit]


async def _fetch_pypi_packages(limit: int) -> list[str] | None:
    """Fetch packages from PyPI using simple index.

    Note: Returns packages in alphabetical order, not by popularity/downloads.
    For top packages by downloads, use another source (API was deprecated).
    """
    import re

    try:
        headers = {
            "User-Agent": "oss-sustain-guard/1.0 (https://github.com/onukura/oss-sustain-guard)"
        }
        async with httpx.AsyncClient(
            verify=get_verify_ssl(), timeout=30, headers=headers
        ) as client:
            response = await client.get(
                "https://pypi.org/simple/", follow_redirects=True
            )
            response.raise_for_status()
            # Parse links from simple index - fixed regex for /simple/ path format
            matches = re.findall(r'href="/simple/([^/]+)/"', response.text)
            return matches[:limit] if matches else None
    except Exception:
        return None


async def _fetch_javascript_packages(limit: int) -> list[str] | None:
    """Fetch packages from npm registry API with pagination.

    Uses npm's search API to fetch packages sorted by popularity (downloads).

    Strategy:
    1. Query npm search API with pagination (size=250 per page)
    2. Follow pagination tokens for up to 5000 packages

    Args:
        limit: Maximum number of packages to fetch
    """
    try:
        headers = {
            "User-Agent": "oss-sustain-guard/1.0 (https://github.com/onukura/oss-sustain-guard)"
        }
        all_packages = []
        from_index = 0
        size = 250  # npm search API allows up to 250 per page

        async with httpx.AsyncClient(
            verify=get_verify_ssl(), timeout=30, headers=headers
        ) as client:
            while len(all_packages) < limit:
                # npm search API returns packages sorted by popularity
                url = f"https://registry.npmjs.org/-/v1/search?text=*&size={size}&from={from_index}"
                response = await client.get(url)
                response.raise_for_status()
                await asyncio.sleep(0.05)  # Rate limiting
                data = response.json()
                objects = data.get("objects", [])

                if not objects:
                    break

                # Extract package names
                for obj in objects:
                    package_data = obj.get("package", {})
                    package_name = package_data.get("name")
                    if package_name:
                        all_packages.append(package_name)

                    if len(all_packages) >= limit:
                        break

                # Check if there are more results
                if len(objects) < size:
                    break

                from_index += size

        return all_packages[:limit] if all_packages else None
    except Exception:
        return None


async def _fetch_csharp_packages(limit: int) -> list[str] | None:
    """Fetch packages from NuGet API with pagination.

    Uses NuGet's official search API to fetch packages sorted by relevance/downloads.

    Strategy:
    1. Query NuGet search API with pagination (take=250 per page)
    2. Follow skip offset for up to 5000 packages

    Args:
        limit: Maximum number of packages to fetch
    """
    try:
        headers = {
            "User-Agent": "oss-sustain-guard/1.0 (https://github.com/onukura/oss-sustain-guard)"
        }
        all_packages = []
        skip = 0
        take = 250  # NuGet search API max per request

        async with httpx.AsyncClient(
            verify=get_verify_ssl(), timeout=30, headers=headers
        ) as client:
            while len(all_packages) < limit:
                url = f"https://azuresearch-usnc.nuget.org/query?q=&skip={skip}&take={take}&prerelease=false&semVerLevel=2.0.0"
                response = await client.get(url)
                response.raise_for_status()
                await asyncio.sleep(0.05)  # Rate limiting
                data = response.json()
                packages_data = data.get("data", [])

                if not packages_data:
                    break

                # Extract package IDs
                for pkg in packages_data:
                    package_id = pkg.get("id")
                    if package_id:
                        all_packages.append(package_id)

                    if len(all_packages) >= limit:
                        break

                # Check if there are more results
                if len(packages_data) < take:
                    break

                skip += take

        return all_packages[:limit] if all_packages else None
    except Exception:
        return None


async def _fetch_rubygems_packages(limit: int) -> list[str] | None:
    """Fetch packages from RubyGems search page (sorted by downloads).

    Scrapes the /search page which lists all gems sorted by download count.
    Uses alphabet filtering (query=a, query=b, ...) to bypass 3000-gem limit per query.

    Strategy:
    1. Fetch without filter (query=) up to 3000 gems
    2. Fetch with each alphabet filter (query=a~z) up to 3000 gems each
    3. Deduplicate results

    Each page contains 30 gems. RubyGems limits pagination to 100 pages (3000 gems max) per query.

    Args:
        limit: Maximum number of packages to fetch
    """
    import re
    import string

    try:
        headers = {
            "User-Agent": "oss-sustain-guard/1.0 (https://github.com/onukura/oss-sustain-guard)"
        }
        all_packages = []
        max_pages_per_query = 100  # RubyGems redirects with 302 after page 100

        async with httpx.AsyncClient(
            verify=get_verify_ssl(), timeout=30, headers=headers
        ) as client:
            # Step 1: Fetch without filter first (most popular gems)
            for page in range(1, max_pages_per_query + 1):
                url = f"https://rubygems.org/search?query=&page={page}"
                response = await client.get(url, follow_redirects=False)

                # Stop if redirected (reached limit)
                if response.status_code == 302:
                    break

                response.raise_for_status()

                # Extract gem names from HTML: <a class="gems__gem" href="/gems/gem-name">
                gem_names = re.findall(
                    r'<a class="gems__gem" href="/gems/([^"]+)">', response.text
                )
                if not gem_names:
                    break

                all_packages.extend(gem_names)

                if len(all_packages) >= limit:
                    break

                # Rate limiting
                await asyncio.sleep(0.05)

            # Step 2: Fetch with alphabet filters if we need more
            if len(all_packages) < limit:
                for letter in string.ascii_lowercase:
                    for page in range(1, max_pages_per_query + 1):
                        url = f"https://rubygems.org/search?query={letter}&page={page}"
                        response = await client.get(url, follow_redirects=False)

                        # Rate limiting
                        await asyncio.sleep(0.05)

                        # Stop if redirected (reached limit for this letter)
                        if response.status_code == 302:
                            break

                        response.raise_for_status()

                        gem_names = re.findall(
                            r'<a class="gems__gem" href="/gems/([^"]+)">', response.text
                        )
                        if not gem_names:
                            break

                        all_packages.extend(gem_names)

                        if len(all_packages) >= limit:
                            break

                    # Stop if we have enough packages
                    if len(all_packages) >= limit:
                        break

            # Step 3: Deduplicate while preserving order (most popular first)
            seen = set()
            unique_packages = []
            for pkg in all_packages:
                if pkg not in seen:
                    seen.add(pkg)
                    unique_packages.append(pkg)

            return unique_packages[:limit] if unique_packages else None
    except Exception:
        return None


async def _fetch_packagist_packages(limit: int) -> list[str] | None:
    """Fetch packages from Packagist search API.

    Uses keyword filtering (symfony, laravel, etc.) to bypass 1000-package limit per query.

    Strategy:
    1. Fetch with wildcard query (q=*) up to 1000 packages
    2. Fetch with popular keyword queries (symfony, laravel, etc.) up to 1000 each
    3. Deduplicate results

    Each page contains 50 packages. Packagist limits pagination to 20 pages (1000 packages max) per query.

    Args:
        limit: Maximum number of packages to fetch
    """
    try:
        headers = {
            "User-Agent": "oss-sustain-guard/1.0 (https://github.com/onukura/oss-sustain-guard)"
        }
        all_packages = []
        per_page = 50  # Packagist has limits on per_page parameter
        max_pages_per_query = 20  # Packagist returns empty after page 20

        # Popular PHP keywords to fetch diverse packages
        keywords = [
            "*",  # Wildcard (most popular)
            "symfony",
            "laravel",
            "wordpress",
            "doctrine",
            "phpunit",
            "monolog",
            "guzzle",
            "twig",
            "psr",
        ]

        async with httpx.AsyncClient(
            verify=get_verify_ssl(), timeout=30, headers=headers
        ) as client:
            for keyword in keywords:
                for page in range(1, max_pages_per_query + 1):
                    url = f"https://packagist.org/search.json?q={keyword}&sort=downloads&per_page={per_page}&page={page}"
                    response = await client.get(url)
                    response.raise_for_status()
                    await asyncio.sleep(0.05)  # Rate limiting
                    data = response.json()
                    results = data.get("results", [])

                    if not results:
                        break

                    all_packages.extend([pkg["name"] for pkg in results])

                    if len(all_packages) >= limit:
                        break

                # Stop if we have enough packages
                if len(all_packages) >= limit:
                    break

            # Deduplicate while preserving order (most popular first)
            seen = set()
            unique_packages = []
            for pkg in all_packages:
                if pkg not in seen:
                    seen.add(pkg)
                    unique_packages.append(pkg)

            return unique_packages[:limit] if unique_packages else None
    except Exception:
        return None


async def _fetch_maven_packages(limit: int) -> list[str] | None:
    """Fetch packages from Maven Central using Solr search API.

    Uses popular group ID prefixes to fetch diverse artifacts.
    Maven Central doesn't provide download stats, so we query by known popular groups.

    Strategy:
    1. Query popular group IDs (org.springframework, com.google, org.apache, etc.)
    2. Collect artifacts from each group
    3. Deduplicate results

    Args:
        limit: Maximum number of packages to fetch
    """
    try:
        headers = {
            "User-Agent": "oss-sustain-guard/1.0 (https://github.com/onukura/oss-sustain-guard)"
        }
        all_artifacts = []
        rows_per_query = 100  # Maximum results per query

        # Popular Java group IDs (ordered by ecosystem importance)
        # This list covers major frameworks, libraries, and tools in the Java ecosystem
        popular_groups = [
            # Spring ecosystem
            "org.springframework",
            "org.springframework.boot",
            "org.springframework.cloud",
            "org.springframework.security",
            "org.springframework.data",
            "org.springframework.integration",
            # Google libraries
            "com.google.guava",
            "com.google.code.gson",
            "com.google.inject",
            "com.google.cloud",
            # Apache Commons & Core
            "org.apache.commons",
            "org.apache.logging.log4j",
            "org.apache.maven",
            "org.apache.httpcomponents",
            "org.apache.tomcat",
            "org.apache.camel",
            "org.apache.poi",
            "org.apache.spark",
            "org.apache.hadoop",
            "org.apache.lucene",
            "org.apache.solr",
            "org.apache.kafka",
            "org.apache.shiro",
            # Testing frameworks
            "junit",
            "org.mockito",
            "org.testng",
            # Persistence & ORM
            "org.hibernate",
            "org.mybatis",
            "org.jooq",
            "org.flywaydb",
            "org.liquibase",
            # Logging
            "org.slf4j",
            # JSON/Serialization
            "com.fasterxml.jackson",
            # Modern frameworks
            "io.micronaut",
            "io.quarkus",
            "io.vertx",
            "io.dropwizard",
            # Networking
            "io.netty",
            "com.squareup",
            # Database drivers
            "com.h2database",
            "mysql",
            "org.postgresql",
            "com.zaxxer",
            # Cloud & AWS
            "com.amazonaws",
            "com.netflix",
            # Utilities
            "org.projectlombok",
            "org.eclipse",
            "org.jetbrains",
            # Security & Auth
            "com.auth0",
            "org.keycloak",
            # Search & Data
            "org.elasticsearch",
            "redis.clients",
            # GraphQL & API
            "com.graphql-java",
            "io.springfox",
            # Resilience
            "io.github.resilience4j",
        ]

        async with httpx.AsyncClient(
            verify=get_verify_ssl(),
            timeout=httpx.Timeout(10.0, read=120.0),
            headers=headers,
        ) as client:
            for group in popular_groups:
                # Search for artifacts in this group
                url = f"https://search.maven.org/solrsearch/select?q=g:{group}*&rows={rows_per_query}&wt=json"
                response = await client.get(url)
                response.raise_for_status()
                await asyncio.sleep(1.0)  # Rate limiting (increased from 0.5)
                data = response.json()
                docs = data.get("response", {}).get("docs", [])

                if not docs:
                    continue

                # Format as groupId:artifactId
                for doc in docs:
                    artifact_id = f"{doc['g']}:{doc['a']}"
                    all_artifacts.append(artifact_id)

                if len(all_artifacts) >= limit:
                    break

            # Deduplicate while preserving order
            seen = set()
            unique_artifacts = []
            for artifact in all_artifacts:
                if artifact not in seen:
                    seen.add(artifact)
                    unique_artifacts.append(artifact)

            return unique_artifacts[:limit] if unique_artifacts else None
    except Exception as e:
        import traceback

        print(f"[ERROR] Failed to fetch Maven packages: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None


async def _fetch_go_packages(limit: int) -> list[str] | None:
    """Fetch popular Go packages from Awesome Go list.

    Scrapes the Awesome Go GitHub repository to get curated list of popular Go packages.
    This provides better coverage than the Go module index which doesn't have popularity metrics.

    Args:
        limit: Maximum number of packages to fetch
    """
    import re

    try:
        headers = {
            "User-Agent": "oss-sustain-guard/1.0 (https://github.com/onukura/oss-sustain-guard)"
        }

        async with httpx.AsyncClient(
            verify=get_verify_ssl(), timeout=30, headers=headers
        ) as client:
            # Fetch Awesome Go list from GitHub
            url = "https://raw.githubusercontent.com/avelino/awesome-go/main/README.md"
            response = await client.get(url)
            response.raise_for_status()
            await asyncio.sleep(0.05)  # Rate limiting
            content = response.text

            # Extract github.com repository links
            pattern = r"github\.com/([^/]+/[^/\)\s]+)"
            matches = re.findall(pattern, content)

            # Deduplicate while preserving order
            seen = set()
            unique_repos = []
            for repo in matches:
                # Clean up repo name (remove trailing characters)
                repo = repo.rstrip(".,;:")
                if repo not in seen and "/" in repo:
                    seen.add(repo)
                    # Format as github.com/owner/repo for Go modules
                    unique_repos.append(f"github.com/{repo}")

            return unique_repos[:limit] if unique_repos else None
    except Exception:
        return None


async def _fetch_crates_io_packages(limit: int) -> list[str] | None:
    """Fetch packages from Crates.io API with pagination.

    Uses the Crates.io API to fetch the most downloaded crates.
    The API returns 10-100 crates per page, so we paginate to get the desired limit.

    Args:
        limit: Maximum number of packages to fetch
    """
    try:
        headers = {
            "User-Agent": "oss-sustain-guard/1.0 (https://github.com/onukura/oss-sustain-guard)"
        }

        all_crates = []
        per_page = 100  # Maximum allowed by Crates.io API
        url = f"https://crates.io/api/v1/crates?sort=downloads&per_page={per_page}"

        async with httpx.AsyncClient(
            verify=get_verify_ssl(), timeout=30, headers=headers
        ) as client:
            while len(all_crates) < limit:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                crates = data.get("crates", [])
                if not crates:
                    break

                all_crates.extend([crate["name"] for crate in crates])

                # Check if we have enough
                if len(all_crates) >= limit:
                    break

                # Get next page URL
                meta = data.get("meta", {})
                next_page = meta.get("next_page")
                if not next_page:
                    break

                url = f"https://crates.io/api/v1/crates{next_page}"

                # Rate limiting - Crates.io requires respectful API usage
                await asyncio.sleep(0.1)

            return all_crates[:limit] if all_crates else None
    except Exception:
        return None


async def process_package(
    package_name: str,
    ecosystem: str,
    resolver: Any,
    console: Console,
) -> tuple[str, dict[str, Any] | None]:
    """
    Process a single package: resolve GitHub URL and analyze repository.

    Returns:
        Tuple of (db_key, analysis_data) or (db_key, None) if failed
    """
    db_key = f"{ecosystem}:{package_name}"

    console.print(f"  Processing: [bold magenta]{package_name}[/bold magenta]")

    # Step 1: Resolve package name to GitHub URL
    repo_info = resolver.resolve_github_url(package_name)

    if not repo_info:
        console.print(
            f"    [red]❌ Could not resolve GitHub repository for {package_name}. Skipping.[/red]"
        )
        return db_key, None

    owner, name = repo_info
    console.print(
        f"    [green]✅ Found repository:[/green] https://github.com/{owner}/{name}"
    )

    # Step 2: Analyze the repository
    try:
        analysis_result = analyze_repository(owner, name)

        # Step 3: Store the result
        analysis_data = {
            "ecosystem": ecosystem,
            "package_name": package_name,
            "github_url": analysis_result.repo_url,
            "total_score": analysis_result.total_score,
            "metrics": [metric._asdict() for metric in analysis_result.metrics],
        }
        console.print(
            f"    [bold green]📊 Analysis complete. Score: {analysis_result.total_score}/100[/bold green]"
        )
        return db_key, analysis_data

    except Exception as e:
        console.print(
            f"    [bold red]❗️ An error occurred during analysis for {owner}/{name}: {e}[/bold red]"
        )
        return db_key, None


async def process_ecosystem_packages(
    ecosystem: str,
    packages: list[str],
    max_concurrent: int = 5,
) -> dict[str, Any]:
    """
    Process packages for an ecosystem with controlled concurrency.

    Args:
        ecosystem: The ecosystem name
        packages: List of package names to process
        max_concurrent: Maximum number of concurrent tasks (default: 5)

    Returns:
        Dictionary of ecosystem data keyed by db_key
    """

    console = Console()

    console.print(f"[bold cyan]📦 Ecosystem: {ecosystem}[/bold cyan]")
    console.print(f"[cyan]  Processing {len(packages)} packages...[/cyan]")

    resolver = get_resolver(ecosystem)
    if not resolver:
        console.print(f"  [red]❌ Unknown ecosystem: {ecosystem}[/red]")
        return {}

    ecosystem_data = {}

    # Use a semaphore to limit concurrent tasks
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(
        package_name: str,
    ) -> tuple[str, dict[str, Any] | None]:
        async with semaphore:
            return await process_package(package_name, ecosystem, resolver, console)

    # Process all packages concurrently with controlled concurrency
    tasks = [process_with_semaphore(pkg) for pkg in packages]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    for db_key, data in results:
        if data is not None:
            ecosystem_data[db_key] = data

    return ecosystem_data


async def main(
    use_top_packages: bool = False,
    packages_limit: int = 5000,
    ecosystems: list[str] | None = None,
    merge_only: bool = False,
    max_concurrent: int = 5,
    verify_ssl: bool = True,
):
    """
    Main function to build the v2 database.

    Args:
        use_top_packages: If True, fetch top packages from registries. Otherwise, use predefined list.
        packages_limit: Maximum number of packages to fetch per ecosystem (only used with use_top_packages).
        ecosystems: List of specific ecosystems to process. If None, process all ecosystems.
        merge_only: If True, only merge ecosystem files into database.json (no analysis).
        max_concurrent: Maximum number of concurrent package processing tasks per ecosystem.
        verify_ssl: If True, verify SSL certificates. If False, disable SSL verification (default: True).
    """
    console = Console()

    # Configure SSL verification (can be disabled with --insecure flag)
    from oss_sustain_guard import config

    config.VERIFY_SSL = verify_ssl

    # Check for GitHub token first
    from oss_sustain_guard.core import GITHUB_TOKEN

    if not GITHUB_TOKEN:
        console.print(
            "[bold red]Error: GITHUB_TOKEN environment variable is not set.[/bold red]"
        )
        console.print(
            "Please set it to a valid GitHub personal access token with 'public_repo' scope."
        )
        sys.exit(1)

    console.print(
        "[bold yellow]🚀 Starting multi-ecosystem database build (v2 - LFS optimized)...[/bold yellow]"
    )

    # If merge-only mode, skip analysis
    if merge_only:
        console.print("[bold cyan]💾 Mode: Merge only (no analysis)[/bold cyan]\n")
        merged_data = merge_ecosystem_files()
        with open(DATABASE_PATH, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, indent=2, ensure_ascii=False, sort_keys=True)
        console.print("[bold green]✨ Merge complete![/bold green]")
        console.print(f"  Output: {DATABASE_PATH}")
        return

    # Filter ecosystems if specified
    if ecosystems:
        invalid_ecosystems = [e for e in ecosystems if e not in PACKAGES_BY_ECOSYSTEM]
        if invalid_ecosystems:
            console.print(
                f"[red]❌ Invalid ecosystems: {', '.join(invalid_ecosystems)}[/red]"
            )
            console.print(
                f"[cyan]Available: {', '.join(PACKAGES_BY_ECOSYSTEM.keys())}[/cyan]"
            )
            sys.exit(1)
        console.print(
            f"[bold cyan]🎯 Targeting ecosystems: {', '.join(ecosystems)}[/bold cyan]\n"
        )
    else:
        ecosystems = list(PACKAGES_BY_ECOSYSTEM.keys())

    # Determine package source
    if use_top_packages:
        console.print(
            "[bold cyan]📊 Mode: Fetching top packages from registries[/bold cyan]"
        )
        console.print(f"[cyan]Limit: {packages_limit} packages per ecosystem[/cyan]\n")
        packages_by_ecosystem = {}
        for ecosystem in ecosystems:
            console.print(
                f"[bold cyan]Fetching packages for {ecosystem}...[/bold cyan]"
            )
            packages = await fetch_top_packages(ecosystem, packages_limit)
            if packages:
                packages_by_ecosystem[ecosystem] = packages
            else:
                console.print(
                    f"  [yellow]⚠️  Using predefined packages for {ecosystem}[/yellow]"
                )
                packages_by_ecosystem[ecosystem] = PACKAGES_BY_ECOSYSTEM[ecosystem]
    else:
        console.print("[bold cyan]📊 Mode: Using predefined packages[/bold cyan]\n")
        packages_by_ecosystem = {e: PACKAGES_BY_ECOSYSTEM[e] for e in ecosystems}

    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    console.print(f"[cyan]📅 Snapshot date: {snapshot_date}[/cyan]\n")

    total_entries = 0
    updated_ecosystems = []

    # Process all ecosystems concurrently
    ecosystem_results = await asyncio.gather(
        *[
            process_ecosystem_packages(ecosystem, packages, max_concurrent)
            for ecosystem, packages in packages_by_ecosystem.items()
        ],
        return_exceptions=False,
    )

    for ecosystem_data in ecosystem_results:
        if not ecosystem_data:
            continue

        # Extract ecosystem name from the first key
        first_key = next(iter(ecosystem_data.keys()), None)
        if not first_key:
            continue

        ecosystem = first_key.split(":")[0]

        # Step 4: Check for changes and save
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

    # Step 5: Merge all latest/ files into database.json for compatibility
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
    # Before running, ensure the GITHUB_TOKEN is set in your environment:
    # export GITHUB_TOKEN="your_personal_access_token"

    parser = argparse.ArgumentParser(
        description="Build OSS Sustain Guard database with multi-ecosystem analysis"
    )
    parser.add_argument(
        "--top-packages",
        action="store_true",
        help="Fetch top packages from each ecosystem registry instead of using predefined list (for production CI)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum number of packages to fetch per ecosystem (only with --top-packages, default: 5000)",
    )
    parser.add_argument(
        "--ecosystems",
        type=str,
        nargs="+",
        help="Specific ecosystems to process (e.g., --ecosystems python javascript). If not specified, all ecosystems are processed.",
        choices=list(PACKAGES_BY_ECOSYSTEM.keys()),
    )
    parser.add_argument(
        "--merge-only",
        action="store_true",
        help="Only merge ecosystem files from latest/ into database.json (no analysis)",
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

    args = parser.parse_args()

    asyncio.run(
        main(
            use_top_packages=args.top_packages,
            packages_limit=args.limit,
            ecosystems=args.ecosystems,
            merge_only=args.merge_only,
            max_concurrent=args.max_concurrent,
            verify_ssl=not args.insecure,
        )
    )
