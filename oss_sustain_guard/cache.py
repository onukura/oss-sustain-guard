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


def save_to_history(ecosystem: str, data: dict[str, Any]) -> bool:
    """
    Save current cache snapshot to history.

    Creates dated snapshot in ~/.cache/oss-sustain-guard/history/{ecosystem}/{date}.json.gz

    Args:
        ecosystem: Ecosystem name (python, javascript, etc.).
        data: Dictionary of package data to save.

    Returns:
        True if saved, False if today's snapshot already exists.
    """
    if not data:
        return False

    cache_dir = get_cache_dir()
    history_dir = cache_dir / "history" / ecosystem
    history_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    history_path = history_dir / f"{today}.json.gz"

    # Don't overwrite if today's snapshot already exists
    if history_path.exists():
        return False

    # Save compressed
    try:
        with gzip.open(history_path, "wt", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        return True
    except IOError:
        return False


def load_history(
    ecosystem: str, from_date: str | None = None, to_date: str | None = None
) -> dict[str, list[dict[str, Any]]]:
    """
    Load historical snapshots for packages.

    Args:
        ecosystem: Ecosystem name (python, javascript, etc.).
        from_date: Start date (YYYY-MM-DD format), inclusive. Optional.
        to_date: End date (YYYY-MM-DD format), inclusive. Optional.

    Returns:
        Dict mapping package keys to list of historical snapshots.
        Each snapshot contains 'date' field plus package data.
    """
    cache_dir = get_cache_dir()
    history_dir = cache_dir / "history" / ecosystem

    if not history_dir.exists():
        return {}

    # Get all snapshot files
    snapshots = sorted(history_dir.glob("*.json.gz"))

    # Filter by date range if specified
    if from_date or to_date:
        filtered_snapshots = []
        for s in snapshots:
            # Extract date from filename (2025-12-11.json.gz -> 2025-12-11)
            file_date = s.stem  # removes .gz -> 2025-12-11.json
            if file_date.endswith(".json"):
                file_date = file_date[:-5]  # remove .json -> 2025-12-11
            if (not from_date or file_date >= from_date) and (
                not to_date or file_date <= to_date
            ):
                filtered_snapshots.append(s)
        snapshots = filtered_snapshots

    # Load and merge by package
    history: dict[str, list[dict[str, Any]]] = {}
    for snapshot_path in snapshots:
        # Extract date from filename (2025-12-11.json.gz -> 2025-12-11)
        date = snapshot_path.stem  # removes .gz -> 2025-12-11.json
        if date.endswith(".json"):
            date = date[:-5]  # remove .json -> 2025-12-11
        try:
            with gzip.open(snapshot_path, "rt", encoding="utf-8") as f:
                snapshot_data = json.load(f)

            for pkg_key, pkg_data in snapshot_data.items():
                if pkg_key not in history:
                    history[pkg_key] = []
                # Add date to each snapshot entry
                snapshot_entry = {"date": date, **pkg_data}
                history[pkg_key].append(snapshot_entry)
        except (json.JSONDecodeError, IOError):
            # Skip corrupted snapshots
            continue

    return history


def list_history_dates(ecosystem: str) -> list[str]:
    """
    List all available snapshot dates for an ecosystem.

    Args:
        ecosystem: Ecosystem name (python, javascript, etc.).

    Returns:
        Sorted list of date strings in YYYY-MM-DD format.
    """
    cache_dir = get_cache_dir()
    history_dir = cache_dir / "history" / ecosystem

    if not history_dir.exists():
        return []

    # Get filenames without extensions (.json.gz -> date only)
    # Note: f.stem removes only the last extension, so 2025-12-11.json.gz -> 2025-12-11.json
    # We need to remove .json as well and validate date format
    dates = []
    for f in history_dir.glob("*.json.gz"):
        date_str = f.stem  # 2025-12-11.json
        if date_str.endswith(".json"):
            date_str = date_str[:-5]  # Remove .json -> 2025-12-11

        # Validate date format (YYYY-MM-DD)
        try:
            from datetime import datetime

            datetime.strptime(date_str, "%Y-%m-%d")
            dates.append(date_str)
        except ValueError:
            # Skip invalid date formats
            continue

    return sorted(dates)


def clear_history(ecosystem: str | None = None) -> int:
    """
    Clear history for one or all ecosystems.

    Args:
        ecosystem: Specific ecosystem to clear, or None to clear all.

    Returns:
        Number of history files cleared.
    """
    cache_dir = get_cache_dir()
    history_base_dir = cache_dir / "history"

    if not history_base_dir.exists():
        return 0

    cleared = 0

    if ecosystem:
        # Clear specific ecosystem history
        history_dir = history_base_dir / ecosystem
        if history_dir.exists():
            for history_file in history_dir.glob("*.json.gz"):
                history_file.unlink()
                cleared += 1
    else:
        # Clear all ecosystem histories
        for eco_dir in history_base_dir.iterdir():
            if eco_dir.is_dir():
                for history_file in eco_dir.glob("*.json.gz"):
                    history_file.unlink()
                    cleared += 1

    return cleared
