"""Cache helper functions for CLI commands."""

from datetime import datetime, timezone
from pathlib import Path

from oss_sustain_guard.cache import save_cache
from oss_sustain_guard.config import get_cache_ttl
from oss_sustain_guard.core import AnalysisResult, analysis_result_to_dict

from .constants import ANALYSIS_VERSION

# --- Lockfile Cache ---
# Cache parsed lockfiles to avoid re-parsing during dependency analysis
_lockfile_cache: dict[str, dict[str, list[str]]] = {}


def get_cached_lockfile_dependencies(
    lockfile_path: Path, package_name: str
) -> list[str] | None:
    """Get dependencies from cached lockfile parsing."""
    cache_key = str(lockfile_path.absolute())
    if cache_key in _lockfile_cache:
        return _lockfile_cache[cache_key].get(package_name)
    return None


def cache_lockfile_dependencies(
    lockfile_path: Path, package_deps: dict[str, list[str]]
):
    """Cache parsed lockfile dependencies."""
    cache_key = str(lockfile_path.absolute())
    _lockfile_cache[cache_key] = package_deps


def clear_lockfile_cache():
    """Clear the lockfile cache."""
    _lockfile_cache.clear()


def _cache_analysis_result(
    ecosystem: str,
    package_name: str,
    result: AnalysisResult,
    source: str = "realtime",
) -> None:
    """Persist analysis results to the local cache for reuse."""
    db_key = f"{ecosystem}:{package_name}"
    payload = analysis_result_to_dict(result)
    cache_entry = {
        db_key: {
            "ecosystem": ecosystem,
            "package_name": package_name,
            "github_url": result.repo_url,
            "metrics": payload.get("metrics", []),
            "funding_links": list(result.funding_links or []),
            "is_community_driven": result.is_community_driven,
            "models": result.models or [],
            "signals": result.signals or {},
            "sample_counts": result.sample_counts or {},
            "analysis_version": ANALYSIS_VERSION,
            "cache_metadata": {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "ttl_seconds": get_cache_ttl(),
                "source": source,
            },
        }
    }
    save_cache(ecosystem, cache_entry)
