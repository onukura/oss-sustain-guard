"""
Tests for cache-related CLI commands.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from typer.testing import CliRunner

from oss_sustain_guard.cli import app

runner = CliRunner()


@patch("oss_sustain_guard.commands.cache.get_cache_stats")
def test_cache_stats_missing(mock_stats):
    """Cache stats show a warning when the cache directory is missing."""
    mock_stats.return_value = {
        "exists": False,
        "cache_dir": "/tmp/cache",
    }

    result = runner.invoke(app, ["cache", "stats"])

    assert result.exit_code == 0
    assert "Cache directory does not exist" in result.output


@patch("oss_sustain_guard.commands.cache.get_cache_stats")
def test_cache_stats_with_data(mock_stats):
    """Cache stats display totals and ecosystem breakdown."""
    mock_stats.return_value = {
        "exists": True,
        "cache_dir": "/tmp/cache",
        "total_entries": 5,
        "valid_entries": 3,
        "expired_entries": 2,
        "ecosystems": {
            "python": {"total": 3, "valid": 2, "expired": 1},
        },
    }

    result = runner.invoke(app, ["cache", "stats"])

    assert result.exit_code == 0
    assert "Cache Statistics" in result.output
    assert "Total entries: 5" in result.output
    assert "python" in result.output


@patch("oss_sustain_guard.commands.cache.clear_expired_cache")
def test_clear_cache_expired_only(mock_clear_expired):
    """Expired-only cache clearing reports the affected ecosystem."""
    mock_clear_expired.return_value = 2

    result = runner.invoke(app, ["cache", "clear", "python", "--expired-only"])

    assert result.exit_code == 0
    assert "Cleared 2 expired" in result.output
    assert "python" in result.output


@patch("oss_sustain_guard.commands.cache.clear_cache")
def test_clear_cache_no_files(mock_clear_cache):
    """Clearing cache reports when nothing is removed."""
    mock_clear_cache.return_value = 0

    result = runner.invoke(app, ["cache", "clear"])

    assert result.exit_code == 0
    assert "No cache files found" in result.output


@patch("oss_sustain_guard.commands.cache.get_cached_packages")
def test_list_cache_no_packages(mock_get_cached):
    """List-cache reports when no packages are available."""
    mock_get_cached.return_value = []

    result = runner.invoke(app, ["cache", "list"])

    assert result.exit_code == 0
    assert "No cached packages found" in result.output


@patch("oss_sustain_guard.commands.cache.compute_weighted_total_score")
@patch("oss_sustain_guard.commands.cache.get_cached_packages")
def test_list_cache_unknown_sort(mock_get_cached, mock_score):
    """List-cache falls back to default sorting for unknown sort keys."""
    now = datetime.now(timezone.utc).isoformat()
    mock_get_cached.return_value = [
        {
            "package_name": "alpha",
            "ecosystem": "python",
            "github_url": "https://github.com/example/alpha",
            "metrics": [
                {
                    "name": "Metric",
                    "score": 8,
                    "max_score": 10,
                    "message": "Note",
                    "risk": "Low",
                }
            ],
            "is_valid": True,
            "fetched_at": now,
        },
        {
            "package_name": "beta",
            "ecosystem": "python",
            "github_url": "https://github.com/example/beta",
            "metrics": [
                {
                    "name": "Metric",
                    "score": 4,
                    "max_score": 10,
                    "message": "Note",
                    "risk": "Low",
                }
            ],
            "is_valid": True,
            "fetched_at": now,
        },
    ]
    mock_score.side_effect = [90, 40]

    result = runner.invoke(app, ["cache", "list", "--sort", "nonsense"])

    assert result.exit_code == 0
    assert "Unknown sort option" in result.output
    assert "alpha" in result.output
    assert "beta" in result.output
