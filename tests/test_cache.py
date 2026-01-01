"""
Tests for cache module.
"""

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from oss_sustain_guard import cache, config


@pytest.fixture
def mock_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    with patch.object(config, "_CACHE_DIR", cache_dir):
        yield cache_dir


@pytest.fixture
def sample_cache_data():
    """Sample cache data with metadata."""
    now = datetime.now(timezone.utc)
    return {
        "python:requests": {
            "ecosystem": "python",
            "package_name": "requests",
            "github_url": "https://github.com/psf/requests",
            "total_score": 85,
            "metrics": [],
            "analysis_version": "1.0",
            "cache_metadata": {
                "fetched_at": now.isoformat(),
                "ttl_seconds": 604800,
                "source": "github",
            },
        },
        "python:django": {
            "ecosystem": "python",
            "package_name": "django",
            "github_url": "https://github.com/django/django",
            "total_score": 90,
            "metrics": [],
            "analysis_version": "1.0",
            "cache_metadata": {
                "fetched_at": (now - timedelta(days=8)).isoformat(),
                "ttl_seconds": 604800,
                "source": "github",
            },
        },
    }


def test_is_cache_valid_fresh_entry():
    """Test that fresh cache entries are valid."""
    now = datetime.now(timezone.utc)
    entry = {
        "analysis_version": "1.0",
        "cache_metadata": {
            "fetched_at": now.isoformat(),
            "ttl_seconds": 604800,
        },
    }
    assert cache.is_cache_valid(entry, expected_version="1.0") is True


def test_is_cache_valid_expired_entry():
    """Test that expired cache entries are invalid."""
    expired_time = datetime.now(timezone.utc) - timedelta(days=8)
    entry = {
        "analysis_version": "1.0",
        "cache_metadata": {
            "fetched_at": expired_time.isoformat(),
            "ttl_seconds": 604800,  # 7 days
        },
    }
    assert cache.is_cache_valid(entry, expected_version="1.0") is False


def test_is_cache_valid_no_metadata():
    """Test that entries without metadata are invalid."""
    entry = {
        "ecosystem": "python",
        "package_name": "requests",
        "analysis_version": "1.0",
    }
    assert cache.is_cache_valid(entry, expected_version="1.0") is False


def test_is_cache_valid_invalid_datetime():
    """Test that entries with invalid datetime are invalid."""
    entry = {
        "analysis_version": "1.0",
        "cache_metadata": {
            "fetched_at": "invalid-datetime",
            "ttl_seconds": 604800,
        },
    }
    assert cache.is_cache_valid(entry, expected_version="1.0") is False


def test_is_cache_valid_version_mismatch():
    """Test that entries with mismatched analysis_version are invalid."""
    now = datetime.now(timezone.utc)
    entry = {
        "analysis_version": "0.9",  # Old version
        "cache_metadata": {
            "fetched_at": now.isoformat(),
            "ttl_seconds": 604800,
        },
    }
    assert cache.is_cache_valid(entry, expected_version="1.0") is False


def test_is_cache_valid_missing_version():
    """Test that entries without analysis_version are invalid."""
    now = datetime.now(timezone.utc)
    entry = {
        # Missing analysis_version field
        "cache_metadata": {
            "fetched_at": now.isoformat(),
            "ttl_seconds": 604800,
        }
    }
    assert cache.is_cache_valid(entry, expected_version="1.0") is False


def test_load_cache_nonexistent(mock_cache_dir):
    """Test loading cache when file doesn't exist."""
    result = cache.load_cache("python")
    assert result == {}


def test_load_cache_valid_entries(mock_cache_dir, sample_cache_data):
    """Test loading cache with valid entries."""
    cache_file = mock_cache_dir / "python.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(sample_cache_data, f)

    result = cache.load_cache("python", expected_version="1.0")
    # Only the fresh entry should be loaded (requests)
    assert "python:requests" in result
    assert "python:django" not in result  # Expired


def test_load_cache_corrupted_file(mock_cache_dir):
    """Test loading corrupted cache file."""
    cache_file = mock_cache_dir / "python.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write("invalid json{]")

    result = cache.load_cache("python")
    assert result == {}


def test_save_cache_new_file(mock_cache_dir):
    """Test saving cache to new file."""
    data = {
        "python:flask": {
            "ecosystem": "python",
            "package_name": "flask",
            "github_url": "https://github.com/pallets/flask",
            "total_score": 88,
            "metrics": [],
        }
    }

    cache.save_cache("python", data, merge=False)

    cache_file = mock_cache_dir / "python.json.gz"
    assert cache_file.exists()

    with gzip.open(cache_file, "rt", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert "python:flask" in saved_data
    assert "cache_metadata" in saved_data["python:flask"]
    assert "fetched_at" in saved_data["python:flask"]["cache_metadata"]


def test_save_cache_merge(mock_cache_dir, sample_cache_data):
    """Test merging new data with existing cache."""
    cache_file = mock_cache_dir / "python.json.gz"
    with gzip.open(cache_file, "wt", encoding="utf-8") as f:
        json.dump(sample_cache_data, f)

    new_data = {
        "python:flask": {
            "ecosystem": "python",
            "package_name": "flask",
            "github_url": "https://github.com/pallets/flask",
            "total_score": 88,
            "metrics": [],
        }
    }

    cache.save_cache("python", new_data, merge=True)

    with gzip.open(cache_file, "rt", encoding="utf-8") as f:
        saved_data = json.load(f)

    # Should have all three packages
    assert "python:requests" in saved_data
    assert "python:django" in saved_data
    assert "python:flask" in saved_data


def test_save_cache_no_merge(mock_cache_dir, sample_cache_data):
    """Test replacing cache without merge."""
    cache_file = mock_cache_dir / "python.json.gz"
    with gzip.open(cache_file, "wt", encoding="utf-8") as f:
        json.dump(sample_cache_data, f)

    new_data = {
        "python:flask": {
            "ecosystem": "python",
            "package_name": "flask",
            "github_url": "https://github.com/pallets/flask",
            "total_score": 88,
            "metrics": [],
        }
    }

    cache.save_cache("python", new_data, merge=False)

    with gzip.open(cache_file, "rt", encoding="utf-8") as f:
        saved_data = json.load(f)

    # Should only have flask
    assert "python:requests" not in saved_data
    assert "python:django" not in saved_data
    assert "python:flask" in saved_data


def test_clear_cache_specific_ecosystem(mock_cache_dir):
    """Test clearing cache for specific ecosystem."""
    # Create multiple cache files
    for ecosystem in ["python", "javascript", "rust"]:
        cache_file = mock_cache_dir / f"{ecosystem}.json.gz"
        with gzip.open(cache_file, "wt", encoding="utf-8") as f:
            json.dump({}, f)

    cleared = cache.clear_cache("python")
    assert cleared == 1
    assert not (mock_cache_dir / "python.json.gz").exists()
    assert (mock_cache_dir / "javascript.json.gz").exists()
    assert (mock_cache_dir / "rust.json.gz").exists()


def test_clear_cache_all_ecosystems(mock_cache_dir):
    """Test clearing cache for all ecosystems."""
    # Create multiple cache files
    for ecosystem in ["python", "javascript", "rust"]:
        cache_file = mock_cache_dir / f"{ecosystem}.json.gz"
        with gzip.open(cache_file, "wt", encoding="utf-8") as f:
            json.dump({}, f)

    cleared = cache.clear_cache(None)
    assert cleared == 3
    assert not (mock_cache_dir / "python.json.gz").exists()
    assert not (mock_cache_dir / "javascript.json.gz").exists()
    assert not (mock_cache_dir / "rust.json.gz").exists()


def test_clear_cache_nonexistent_dir():
    """Test clearing cache when directory doesn't exist."""
    with patch.object(config, "_CACHE_DIR", Path("/nonexistent")):
        cleared = cache.clear_cache()
        assert cleared == 0


def test_get_cache_stats_nonexistent_dir():
    """Test getting stats when cache doesn't exist."""
    with patch.object(config, "_CACHE_DIR", Path("/nonexistent")):
        stats = cache.get_cache_stats()
        assert stats["exists"] is False
        assert stats["total_entries"] == 0


def test_get_cache_stats_with_data(mock_cache_dir, sample_cache_data):
    """Test getting cache statistics."""
    cache_file = mock_cache_dir / "python.json.gz"
    with gzip.open(cache_file, "wt", encoding="utf-8") as f:
        json.dump(sample_cache_data, f)

    stats = cache.get_cache_stats()
    assert stats["exists"] is True
    assert stats["total_entries"] == 2
    assert stats["valid_entries"] == 1  # Only requests is valid
    assert stats["expired_entries"] == 1  # Django is expired


def test_get_cache_stats_specific_ecosystem(mock_cache_dir, sample_cache_data):
    """Test getting stats for specific ecosystem."""
    cache_file = mock_cache_dir / "python.json.gz"
    with gzip.open(cache_file, "wt", encoding="utf-8") as f:
        json.dump(sample_cache_data, f)

    stats = cache.get_cache_stats("python")
    assert stats["exists"] is True
    assert "python" in stats["ecosystems"]
    assert stats["ecosystems"]["python"]["total"] == 2
    assert stats["ecosystems"]["python"]["valid"] == 1
    assert stats["ecosystems"]["python"]["expired"] == 1


def test_cache_metadata_auto_added(mock_cache_dir):
    """Test that cache_metadata is automatically added when saving."""
    data = {
        "python:requests": {
            "ecosystem": "python",
            "package_name": "requests",
            "github_url": "https://github.com/psf/requests",
            "total_score": 85,
            "metrics": [],
            # No cache_metadata
        }
    }

    cache.save_cache("python", data)

    cache_file = mock_cache_dir / "python.json.gz"
    with gzip.open(cache_file, "rt", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert "cache_metadata" in saved_data["python:requests"]
    assert "fetched_at" in saved_data["python:requests"]["cache_metadata"]
    assert "ttl_seconds" in saved_data["python:requests"]["cache_metadata"]
    assert "source" in saved_data["python:requests"]["cache_metadata"]


def test_is_cache_valid_skip_ttl():
    """Test skipping TTL checks."""
    expired_time = datetime.now(timezone.utc) - timedelta(days=365)
    entry = {
        "analysis_version": "1.0",
        "cache_metadata": {
            "fetched_at": expired_time.isoformat(),
            "ttl_seconds": 1,
        },
    }
    assert cache.is_cache_valid(entry, expected_version="1.0", check_ttl=False) is True


def test_is_cache_valid_naive_timestamp():
    """Test naive timestamps are treated as UTC."""
    naive_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    entry = {
        "analysis_version": "1.0",
        "cache_metadata": {
            "fetched_at": naive_utc.isoformat(),
            "ttl_seconds": 60,
        },
    }
    assert cache.is_cache_valid(entry, expected_version="1.0") is True


def test_load_cache_gzip_v2_format(mock_cache_dir, sample_cache_data):
    """Test loading gzip cache with v2 schema."""
    cache_file = mock_cache_dir / "python.json.gz"
    with gzip.open(cache_file, "wt", encoding="utf-8") as f:
        json.dump({"_schema_version": "2.0", "packages": sample_cache_data}, f)

    result = cache.load_cache("python", expected_version="1.0")
    assert "python:requests" in result
    assert "python:django" not in result


def test_save_cache_merge_legacy_json(mock_cache_dir, sample_cache_data):
    """Test merging when existing cache is a legacy .json file."""
    cache_file = mock_cache_dir / "python.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(sample_cache_data, f)

    new_data = {
        "python:flask": {
            "ecosystem": "python",
            "package_name": "flask",
            "github_url": "https://github.com/pallets/flask",
            "total_score": 88,
            "metrics": [],
        }
    }

    cache.save_cache("python", new_data, merge=True)

    gz_cache = mock_cache_dir / "python.json.gz"
    assert gz_cache.exists()
    with gzip.open(gz_cache, "rt", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert "python:requests" in saved_data
    assert "python:django" in saved_data
    assert "python:flask" in saved_data


def test_save_cache_merge_with_corrupted_legacy_json(mock_cache_dir):
    """Test corrupted legacy cache does not break merge."""
    cache_file = mock_cache_dir / "python.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write("invalid json")

    new_data = {
        "python:flask": {
            "ecosystem": "python",
            "package_name": "flask",
            "github_url": "https://github.com/pallets/flask",
            "total_score": 88,
            "metrics": [],
        }
    }

    cache.save_cache("python", new_data, merge=True)

    gz_cache = mock_cache_dir / "python.json.gz"
    assert gz_cache.exists()
    with gzip.open(gz_cache, "rt", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert list(saved_data) == ["python:flask"]


def test_clear_expired_cache_specific_ecosystem(mock_cache_dir, sample_cache_data):
    """Test clearing expired entries for a specific ecosystem."""
    cache_file = mock_cache_dir / "python.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(sample_cache_data, f)

    cleared = cache.clear_expired_cache("python", expected_version="1.0")
    assert cleared == 1

    gz_cache = mock_cache_dir / "python.json.gz"
    assert gz_cache.exists()
    with gzip.open(gz_cache, "rt", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert list(saved_data) == ["python:requests"]


def test_clear_expired_cache_all_ecosystems_skips_corrupt(
    mock_cache_dir, sample_cache_data
):
    """Test expired cache cleanup skips corrupted files."""
    cache_file = mock_cache_dir / "python.json.gz"
    with gzip.open(cache_file, "wt", encoding="utf-8") as f:
        json.dump(sample_cache_data, f)

    corrupted = mock_cache_dir / "ruby.json.gz"
    with gzip.open(corrupted, "wt", encoding="utf-8") as f:
        f.write("invalid json")

    cleared = cache.clear_expired_cache()
    assert cleared == 1


def test_get_cached_packages_v2_format_and_key_parsing(mock_cache_dir):
    """Test cached package listing with v2 schema and key parsing."""
    now = datetime.now(timezone.utc)
    data = {
        "_schema_version": "2.0",
        "packages": {
            "python:requests": {
                "ecosystem": "python",
                "package_name": "requests",
                "github_url": "https://github.com/psf/requests",
                "metrics": [],
                "analysis_version": "1.0",
                "cache_metadata": {
                    "fetched_at": now.isoformat(),
                    "ttl_seconds": 604800,
                },
            },
            "django": {
                "ecosystem": "python",
                "package_name": "django",
                "github_url": "https://github.com/django/django",
                "metrics": [],
                "analysis_version": "1.0",
                "cache_metadata": {
                    "fetched_at": now.isoformat(),
                    "ttl_seconds": 604800,
                },
            },
        },
    }

    cache_file = mock_cache_dir / "python.json.gz"
    with gzip.open(cache_file, "wt", encoding="utf-8") as f:
        json.dump(data, f)

    packages = cache.get_cached_packages()
    assert {pkg["package_name"] for pkg in packages} == {"requests", "django"}
    django = next(pkg for pkg in packages if pkg["package_name"] == "django")
    assert django["ecosystem"] == "python"
    assert django["github_url"] == "https://github.com/django/django"


def test_get_cached_packages_missing_file(mock_cache_dir):
    """Test listing cached packages when cache file is missing."""
    packages = cache.get_cached_packages("python")
    assert packages == []


def test_get_cache_stats_missing_file(mock_cache_dir):
    """Test stats skip missing cache files."""
    stats = cache.get_cache_stats("python")
    assert stats["exists"] is True
    assert stats["total_entries"] == 0


def test_get_cache_stats_v2_json_format(mock_cache_dir):
    """Test stats for v2 schema stored in legacy .json file."""
    now = datetime.now(timezone.utc)
    data = {
        "_schema_version": "2.0",
        "packages": {
            "python:requests": {
                "analysis_version": "1.0",
                "cache_metadata": {
                    "fetched_at": now.isoformat(),
                    "ttl_seconds": 604800,
                },
            }
        },
    }
    cache_file = mock_cache_dir / "python.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    stats = cache.get_cache_stats("python", expected_version="1.0")
    assert stats["total_entries"] == 1
    assert stats["valid_entries"] == 1
    assert stats["expired_entries"] == 0


def test_get_cache_stats_skips_corrupted_cache(mock_cache_dir):
    """Test stats ignore corrupted cache files."""
    cache_file = mock_cache_dir / "python.json.gz"
    with gzip.open(cache_file, "wt", encoding="utf-8") as f:
        f.write("invalid json")

    stats = cache.get_cache_stats()
    assert stats["exists"] is True
    assert stats["total_entries"] == 0
