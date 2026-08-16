"""
Cache management for OSS Sustain Guard.

Provides local caching of package analysis data to reduce network requests,
including specialized trend analysis caching.
"""

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oss_sustain_guard.config import get_cache_dir, get_cache_ttl

# Trend cache subdirectory
TREND_CACHE_SUBDIR = "trends"


def _get_cache_path(ecosystem: str) -> Path:
    """Get the cache file path for a specific ecosystem.

    Returns gzip path (.json.gz) by default, but checks for legacy .json files.
    """
    cache_dir = get_cache_dir()
    gz_path = cache_dir / f"{ecosystem}.json.gz"
    json_path = cache_dir / f"{ecosystem}.json"

    # Prefer gzip, but return json path if it exists and gz doesn't
    if json_path.exists() and not gz_path.exists():
        return json_path
    return gz_path


def is_cache_valid(
    entry: dict[str, Any],
    expected_version: str | None = "1.0",
    check_ttl: bool = True,
) -> bool:
    """
    Check if a cache entry is still valid based on TTL and data version.

    Args:
        entry: Cache entry dict with cache_metadata and analysis_version.
        expected_version: Expected analysis_version string (default: "1.0").
            If None, version check is skipped.
        check_ttl: Whether to check TTL expiration (default: True).

    Returns:
        True if cache is valid (within TTL and version matches), False otherwise.
    """
    # Check analysis version if specified
    if expected_version is not None:
        entry_version = entry.get("analysis_version")
        if entry_version != expected_version:
            # Version mismatch - consider invalid
            return False

    metadata = entry.get("cache_metadata")
    if not metadata or "fetched_at" not in metadata:
        # Old format without metadata - consider invalid
        return False

    if not check_ttl:
        # Skip TTL check if requested
        return True

    try:
        fetched_at = datetime.fromisoformat(metadata["fetched_at"])
        ttl_seconds = metadata.get("ttl_seconds", get_cache_ttl())

        # Make fetched_at timezone-aware if it isn't
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age_seconds = (now - fetched_at).total_seconds()

        return age_seconds < ttl_seconds
    except (ValueError, TypeError):
        # Invalid datetime format
        return False


def load_cache(ecosystem: str, expected_version: str = "1.0") -> dict[str, Any]:
    """
    Load cache for a specific ecosystem.

    Handles both v1.x (flat dict) and v2.0 (wrapped with schema metadata) formats.

    Args:
        ecosystem: Ecosystem name (python, javascript, rust, etc.).
        expected_version: Expected analysis_version for cache entries (default: "1.0").

    Returns:
        Dictionary of cached entries (only valid entries based on TTL and version).
    """
    cache_path = _get_cache_path(ecosystem)

    if not cache_path.exists():
        return {}

    try:
        # Try gzip first, then fallback to uncompressed
        if cache_path.suffix == ".gz":
            with gzip.open(cache_path, "rt", encoding="utf-8") as f:
                raw_data = json.load(f)
        else:
            with open(cache_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

        # Handle schema versions
        if isinstance(raw_data, dict) and "_schema_version" in raw_data:
            # v2.0+ format with metadata
            all_data = raw_data.get("packages", {})
        else:
            # v1.x format (flat dict) - backward compatibility
            all_data = raw_data

        # Filter valid entries only (TTL + version check)
        valid_data = {}
        for key, entry in all_data.items():
            if is_cache_valid(entry, expected_version):
                valid_data[key] = entry

        return valid_data
    except (json.JSONDecodeError, IOError):
        # Corrupted cache - return empty dict
        return {}


def save_cache(ecosystem: str, data: dict[str, Any], merge: bool = True) -> None:
    """
    Save data to cache for a specific ecosystem.

    Args:
        ecosystem: Ecosystem name (python, javascript, rust, etc.).
        data: Dictionary of entries to cache.
        merge: If True, merge with existing cache. If False, replace entirely.
    """
    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_path = _get_cache_path(ecosystem)

    # Load existing cache if merging
    existing_data = {}
    if merge and cache_path.exists():
        try:
            if cache_path.suffix == ".gz":
                with gzip.open(cache_path, "rt", encoding="utf-8") as f:
                    existing_data = json.load(f)
            else:
                with open(cache_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing_data = {}

    # Add cache_metadata to new entries if not present
    now = datetime.now(timezone.utc).isoformat()
    ttl = get_cache_ttl()

    for entry in data.values():
        if "cache_metadata" not in entry:
            entry["cache_metadata"] = {
                "fetched_at": now,
                "ttl_seconds": ttl,
                "source": "github",
            }

    # Merge and save
    merged_data = {**existing_data, **data}

    # Always save as gzip
    cache_path = (
        cache_path.with_suffix(".json.gz")
        if cache_path.suffix == ".json"
        else cache_path
    )
    with gzip.open(cache_path, "wt", encoding="utf-8") as f:
        json.dump(merged_data, f, indent=2, ensure_ascii=False, sort_keys=True)


def clear_cache(ecosystem: str | None = None) -> int:
    """
    Clear cache for one or all ecosystems.

    Args:
        ecosystem: Specific ecosystem to clear, or None to clear all.

    Returns:
        Number of cache files cleared.
    """
    cache_dir = get_cache_dir()

    if not cache_dir.exists():
        return 0

    cleared = 0

    if ecosystem:
        # Clear specific ecosystem (both .json.gz and .json)
        for suffix in [".json.gz", ".json"]:
            cache_path = get_cache_dir() / f"{ecosystem}{suffix}"
            if cache_path.exists():
                cache_path.unlink()
                cleared += 1
    else:
        # Clear all ecosystems (both .json.gz and .json)
        for cache_file in list(cache_dir.glob("*.json.gz")) + list(
            cache_dir.glob("*.json")
        ):
            cache_file.unlink()
            cleared += 1

    return cleared


def clear_expired_cache(
    ecosystem: str | None = None, expected_version: str = "1.0"
) -> int:
    """
    Clear only expired cache entries for one or all ecosystems.

    Removes expired entries while preserving valid ones.

    Args:
        ecosystem: Specific ecosystem to clear, or None to clear all.
        expected_version: Expected analysis_version to check validity.

    Returns:
        Number of expired entries removed.
    """
    cache_dir = get_cache_dir()

    if not cache_dir.exists():
        return 0

    ecosystems_to_check = []
    if ecosystem:
        ecosystems_to_check = [ecosystem]
    else:
        # Check both .json.gz and .json files
        processed = set()
        for f in list(cache_dir.glob("*.json.gz")) + list(cache_dir.glob("*.json")):
            eco_name = f.name.replace(".json.gz", "").replace(".json", "")
            if eco_name not in processed:
                ecosystems_to_check.append(eco_name)
                processed.add(eco_name)

    total_cleared = 0

    for eco in ecosystems_to_check:
        cache_path = _get_cache_path(eco)
        if not cache_path.exists():
            continue

        try:
            # Load cache
            if cache_path.suffix == ".gz":
                with gzip.open(cache_path, "rt", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            # Handle schema versions
            if isinstance(data, dict) and "_schema_version" in data:
                # v2.0+ format
                all_data = data.get("packages", {})
            else:
                # v1.x format
                all_data = data

            # Filter out expired entries
            valid_data = {}
            expired_count = 0
            for key, entry in all_data.items():
                if is_cache_valid(entry, expected_version):
                    valid_data[key] = entry
                else:
                    expired_count += 1

            total_cleared += expired_count

            # Save filtered cache if we removed anything
            if expired_count > 0:
                # Always save as gzip
                cache_path = (
                    cache_path.with_suffix(".json.gz")
                    if cache_path.suffix == ".json"
                    else cache_path
                )
                with gzip.open(cache_path, "wt", encoding="utf-8") as f:
                    json.dump(
                        valid_data, f, indent=2, ensure_ascii=False, sort_keys=True
                    )

        except (json.JSONDecodeError, IOError):
            # Corrupted cache - skip
            continue

    return total_cleared


def get_cached_packages(
    ecosystem: str | None = None, expected_version: str = "1.0"
) -> list[dict[str, Any]]:
    """
    Get list of all cached packages with their details.

    Args:
        ecosystem: Specific ecosystem to check, or None for all ecosystems.
        expected_version: Expected analysis_version for cache entries.

    Returns:
        List of package dictionaries with keys:
        - ecosystem: str
        - package_name: str
        - github_url: str
        - metrics: list[dict] (raw metric data for score recalculation)
        - is_valid: bool (TTL check)
        - fetched_at: str (ISO format)
        - analysis_version: str
    """
    cache_dir = get_cache_dir()

    if not cache_dir.exists():
        return []

    ecosystems_to_check = []
    if ecosystem:
        ecosystems_to_check = [ecosystem]
    else:
        # Check both .json.gz and .json files
        processed = set()
        for f in list(cache_dir.glob("*.json.gz")) + list(cache_dir.glob("*.json")):
            eco_name = f.name.replace(".json.gz", "").replace(".json", "")
            if eco_name not in processed:
                ecosystems_to_check.append(eco_name)
                processed.add(eco_name)

    packages = []

    for eco in ecosystems_to_check:
        cache_path = _get_cache_path(eco)
        if not cache_path.exists():
            continue

        try:
            if cache_path.suffix == ".gz":
                with gzip.open(cache_path, "rt", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            # Handle schema versions
            if isinstance(data, dict) and "_schema_version" in data:
                # v2.0+ format
                all_data = data.get("packages", {})
            else:
                # v1.x format
                all_data = data

            for key, entry in all_data.items():
                # Parse key format: "ecosystem:package_name"
                if ":" in key:
                    entry_eco, pkg_name = key.split(":", 1)
                else:
                    entry_eco = eco
                    pkg_name = entry.get("package_name", key)

                metadata = entry.get("cache_metadata", {})

                # Store metrics for score recalculation by caller
                packages.append(
                    {
                        "ecosystem": entry_eco,
                        "package_name": pkg_name,
                        "github_url": entry.get("github_url", "unknown"),
                        "metrics": entry.get("metrics", []),
                        "is_valid": is_cache_valid(entry, expected_version),
                        "fetched_at": metadata.get("fetched_at", "unknown"),
                        "analysis_version": entry.get("analysis_version", "unknown"),
                    }
                )
        except (json.JSONDecodeError, IOError):
            continue

    return packages


def get_cache_stats(
    ecosystem: str | None = None, expected_version: str | None = None
) -> dict[str, Any]:
    """
    Get cache statistics.

    Args:
        ecosystem: Specific ecosystem to check, or None for all.
        expected_version: Expected analysis_version to check validity.
            If None, entries are considered valid regardless of version.

    Returns:
        Dictionary with cache statistics.
    """
    cache_dir = get_cache_dir()

    if not cache_dir.exists():
        return {
            "cache_dir": str(cache_dir),
            "exists": False,
            "total_entries": 0,
            "valid_entries": 0,
            "expired_entries": 0,
            "ecosystems": {},
        }

    ecosystems_to_check = []
    if ecosystem:
        ecosystems_to_check = [ecosystem]
    else:
        # Check both .json.gz and .json files
        processed = set()
        for f in list(cache_dir.glob("*.json.gz")) + list(cache_dir.glob("*.json")):
            eco_name = f.name.replace(".json.gz", "").replace(".json", "")
            if eco_name not in processed:
                ecosystems_to_check.append(eco_name)
                processed.add(eco_name)

    total_entries = 0
    valid_entries = 0
    expired_entries = 0
    ecosystem_stats = {}

    for eco in ecosystems_to_check:
        cache_path = _get_cache_path(eco)
        if not cache_path.exists():
            continue

        try:
            if cache_path.suffix == ".gz":
                with gzip.open(cache_path, "rt", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            # Handle schema versions
            if isinstance(data, dict) and "_schema_version" in data:
                # v2.0+ format
                all_data = data.get("packages", {})
            else:
                # v1.x format
                all_data = data

            eco_total = len(all_data)
            eco_valid = sum(
                1
                for entry in all_data.values()
                if is_cache_valid(entry, expected_version=expected_version)
            )
            eco_expired = eco_total - eco_valid

            total_entries += eco_total
            valid_entries += eco_valid
            expired_entries += eco_expired

            ecosystem_stats[eco] = {
                "total": eco_total,
                "valid": eco_valid,
                "expired": eco_expired,
            }
        except (json.JSONDecodeError, IOError):
            pass

    return {
        "cache_dir": str(cache_dir),
        "exists": True,
        "total_entries": total_entries,
        "valid_entries": valid_entries,
        "expired_entries": expired_entries,
        "ecosystems": ecosystem_stats,
    }


# --- Trend Data Caching ---


def _get_trend_cache_path(
    owner: str,
    repo: str,
    vcs_platform: str = "github",
) -> Path:
    """Get the cache file path for trend VCS data.

    Trend data is cached separately with time window information to enable
    efficient incremental analysis.

    Args:
        owner: Repository owner
        repo: Repository name
        vcs_platform: VCS platform identifier (github, gitlab, etc.)

    Returns:
        Path to trend cache file (gzip compressed JSON)
    """
    cache_dir = get_cache_dir() / TREND_CACHE_SUBDIR / vcs_platform
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize owner/repo for filesystem-safe naming
    safe_owner = owner.replace("/", "_").replace("\\", "_")
    safe_repo = repo.replace("/", "_").replace("\\", "_")
    filename = f"{safe_owner}_{safe_repo}.json.gz"

    return cache_dir / filename


def _get_trend_window_cache_key(
    since: str,
    until: str,
) -> str:
    """Generate a cache key for a time window.

    Args:
        since: Start timestamp (ISO format)
        until: End timestamp (ISO format)

    Returns:
        Cache key string combining both timestamps
    """
    return f"{since}::{until}"


def load_trend_vcs_data(
    owner: str,
    repo: str,
    since: str,
    until: str,
    vcs_platform: str = "github",
) -> dict[str, Any] | None:
    """Load cached VCS data for a specific time window.

    Args:
        owner: Repository owner
        repo: Repository name
        since: Start timestamp (ISO format)
        until: End timestamp (ISO format)
        vcs_platform: VCS platform identifier

    Returns:
        Cached VCS data dict, or None if not found/invalid
    """
    cache_path = _get_trend_cache_path(owner, repo, vcs_platform)

    if not cache_path.exists():
        return None

    try:
        with gzip.open(cache_path, "rt", encoding="utf-8") as f:
            all_data = json.load(f)

        window_key = _get_trend_window_cache_key(since, until)
        window_data = all_data.get(window_key)

        if not window_data:
            return None

        # Check if cache is still valid
        metadata = window_data.get("cache_metadata", {})
        if not metadata:
            return None

        # Verify cache hasn't expired
        try:
            fetched_at = datetime.fromisoformat(metadata["fetched_at"])
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)

            ttl_seconds = metadata.get("ttl_seconds", get_cache_ttl())
            now = datetime.now(timezone.utc)
            age_seconds = (now - fetched_at).total_seconds()

            if age_seconds >= ttl_seconds:
                # Cache expired
                return None

        except (ValueError, TypeError):
            return None

        return window_data.get("vcs_data")

    except (gzip.BadGzipFile, json.JSONDecodeError, IOError):
        return None


def save_trend_vcs_data(
    owner: str,
    repo: str,
    since: str,
    until: str,
    vcs_data: dict[str, Any],
    vcs_platform: str = "github",
) -> None:
    """Cache VCS data for a specific time window.

    Trends are cached separately from regular package analysis to enable
    efficient windowing and incremental updates.

    Args:
        owner: Repository owner
        repo: Repository name
        since: Start timestamp (ISO format)
        until: End timestamp (ISO format)
        vcs_data: VCS data dict to cache
        vcs_platform: VCS platform identifier
    """
    cache_path = _get_trend_cache_path(owner, repo, vcs_platform)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    window_key = _get_trend_window_cache_key(since, until)

    # Load existing cache if present
    all_data = {}
    if cache_path.exists():
        try:
            with gzip.open(cache_path, "rt", encoding="utf-8") as f:
                all_data = json.load(f)
        except (gzip.BadGzipFile, json.JSONDecodeError):
            all_data = {}

    # Update with new window data
    all_data[window_key] = {
        "vcs_data": vcs_data,
        "cache_metadata": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": get_cache_ttl(),
            "since": since,
            "until": until,
        },
    }

    # Write cache
    with gzip.open(cache_path, "wt", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)


def clear_trend_cache(
    owner: str | None = None,
    repo: str | None = None,
    vcs_platform: str | None = None,
) -> None:
    """Clear trend cache entries.

    Args:
        owner: If specified, only clear for this owner
        repo: If specified (with owner), only clear for this repo
        vcs_platform: If specified, only clear for this platform
    """
    cache_dir = get_cache_dir() / TREND_CACHE_SUBDIR

    if not cache_dir.exists():
        return

    if vcs_platform:
        platform_dir = cache_dir / vcs_platform
        if owner and repo:
            # Clear specific repo
            safe_owner = owner.replace("/", "_").replace("\\", "_")
            safe_repo = repo.replace("/", "_").replace("\\", "_")
            cache_file = platform_dir / f"{safe_owner}_{safe_repo}.json.gz"
            if cache_file.exists():
                cache_file.unlink()
        elif owner:
            # Clear all repos for this owner (wildcard match)
            safe_owner = owner.replace("/", "_").replace("\\", "_")
            if platform_dir.exists():
                for cache_file in platform_dir.glob(f"{safe_owner}_*.json.gz"):
                    cache_file.unlink()
        else:
            # Clear all for this platform
            import shutil

            if platform_dir.exists():
                shutil.rmtree(platform_dir)
    elif owner:
        # Clear across all platforms for this owner
        if cache_dir.exists():
            safe_owner = owner.replace("/", "_").replace("\\", "_")
            for platform_dir in cache_dir.iterdir():
                if platform_dir.is_dir():
                    for cache_file in platform_dir.glob(f"{safe_owner}_*.json.gz"):
                        cache_file.unlink()
    else:
        # Clear all trend cache
        import shutil

        if cache_dir.exists():
            shutil.rmtree(cache_dir)
