"""
Cache management for OSS Sustain Guard.

Provides local caching of package analysis data to reduce network requests.
"""

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oss_sustain_guard.config import get_cache_dir, get_cache_ttl


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


def is_cache_valid(entry: dict[str, Any]) -> bool:
    """
    Check if a cache entry is still valid based on TTL.

    Args:
        entry: Cache entry dict with cache_metadata.

    Returns:
        True if cache is valid, False if expired or missing metadata.
    """
    metadata = entry.get("cache_metadata")
    if not metadata or "fetched_at" not in metadata:
        # Old format without metadata - consider invalid
        return False

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


def load_cache(ecosystem: str) -> dict[str, Any]:
    """
    Load cache for a specific ecosystem.

    Handles both v1.x (flat dict) and v2.0 (wrapped with schema metadata) formats.

    Args:
        ecosystem: Ecosystem name (python, javascript, rust, etc.).

    Returns:
        Dictionary of cached entries (only valid entries based on TTL).
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

        # Filter valid entries only
        valid_data = {}
        for key, entry in all_data.items():
            if is_cache_valid(entry):
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


def get_cache_stats(ecosystem: str | None = None) -> dict[str, Any]:
    """
    Get cache statistics.

    Args:
        ecosystem: Specific ecosystem to check, or None for all.

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

            eco_total = len(data)
            eco_valid = sum(1 for entry in data.values() if is_cache_valid(entry))
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
