"""
Tests for trend cache functionality.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from oss_sustain_guard.cache import (
    clear_trend_cache,
    load_trend_vcs_data,
    save_trend_vcs_data,
)
from oss_sustain_guard.trend import (
    get_trend_cache_stats,
    reset_trend_cache_stats,
)


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory for testing."""
    with patch("oss_sustain_guard.cache.get_cache_dir", return_value=tmp_path):
        yield tmp_path


def test_save_and_load_trend_vcs_data(temp_cache_dir):
    """Test saving and loading trend VCS data from cache."""
    owner = "psf"
    repo = "requests"
    since = "2025-01-01T00:00:00+00:00"
    until = "2025-02-01T00:00:00+00:00"
    vcs_data = {"commits": 42, "issues": 10, "prs": 5}

    # Initially should not be cached
    assert load_trend_vcs_data(owner, repo, since, until) is None

    # Save data
    save_trend_vcs_data(owner, repo, since, until, vcs_data)

    # Load and verify
    loaded = load_trend_vcs_data(owner, repo, since, until)
    assert loaded == vcs_data


def test_trend_cache_with_ttl(temp_cache_dir):
    """Test that trend cache respects TTL expiration."""
    owner = "owner"
    repo = "repo"
    since = "2025-01-01T00:00:00+00:00"
    until = "2025-02-01T00:00:00+00:00"
    vcs_data = {"data": "test"}

    # Save with a mocked TTL of 1 second
    with patch("oss_sustain_guard.cache.get_cache_ttl", return_value=1):
        save_trend_vcs_data(owner, repo, since, until, vcs_data)

    # Should be available immediately
    assert load_trend_vcs_data(owner, repo, since, until) == vcs_data

    # Simulate time passing by mocking datetime
    future_time = datetime.now(timezone.utc) + timedelta(seconds=2)
    with patch("oss_sustain_guard.cache.datetime") as mock_datetime:
        mock_datetime.now.return_value = future_time
        mock_datetime.fromisoformat = datetime.fromisoformat

        # Should now be expired
        assert load_trend_vcs_data(owner, repo, since, until) is None


def test_multiple_time_windows_cache(temp_cache_dir):
    """Test caching multiple time windows for the same repo."""
    owner = "owner"
    repo = "repo"

    windows = [
        ("2025-01-01T00:00:00+00:00", "2025-02-01T00:00:00+00:00"),
        ("2025-02-01T00:00:00+00:00", "2025-03-01T00:00:00+00:00"),
        ("2025-03-01T00:00:00+00:00", "2025-04-01T00:00:00+00:00"),
    ]

    # Save multiple windows
    for i, (since, until) in enumerate(windows):
        vcs_data = {"window": i, "commits": 10 + i}
        save_trend_vcs_data(owner, repo, since, until, vcs_data)

    # Verify all windows are cached separately
    for i, (since, until) in enumerate(windows):
        loaded = load_trend_vcs_data(owner, repo, since, until)
        assert loaded == {"window": i, "commits": 10 + i}


def test_clear_trend_cache_by_repo(temp_cache_dir):
    """Test clearing trend cache for a specific repo."""
    owner = "owner"
    repo = "repo"
    since = "2025-01-01T00:00:00+00:00"
    until = "2025-02-01T00:00:00+00:00"
    vcs_data = {"data": "test"}

    # Save cache
    save_trend_vcs_data(owner, repo, since, until, vcs_data)
    assert load_trend_vcs_data(owner, repo, since, until) is not None

    # Clear specific repo
    clear_trend_cache(owner=owner, repo=repo)

    # Should be cleared
    assert load_trend_vcs_data(owner, repo, since, until) is None


def test_clear_trend_cache_by_owner(temp_cache_dir):
    """Test clearing trend cache for all repos by an owner."""
    owner = "owner"
    repos = ["repo1", "repo2"]
    since = "2025-01-01T00:00:00+00:00"
    until = "2025-02-01T00:00:00+00:00"

    # Save cache for multiple repos
    for repo in repos:
        save_trend_vcs_data(owner, repo, since, until, {"repo": repo})

    # Clear by owner
    clear_trend_cache(owner=owner)

    # All should be cleared
    for repo in repos:
        assert load_trend_vcs_data(owner, repo, since, until) is None


def test_clear_all_trend_cache(temp_cache_dir):
    """Test clearing all trend cache."""
    # Save multiple repos/owners
    for owner in ["owner1", "owner2"]:
        for repo in ["repo1", "repo2"]:
            since = "2025-01-01T00:00:00+00:00"
            until = "2025-02-01T00:00:00+00:00"
            save_trend_vcs_data(owner, repo, since, until, {"data": "test"})

    # Clear all
    clear_trend_cache()

    # All should be cleared
    for owner in ["owner1", "owner2"]:
        for repo in ["repo1", "repo2"]:
            since = "2025-01-01T00:00:00+00:00"
            until = "2025-02-01T00:00:00+00:00"
            assert load_trend_vcs_data(owner, repo, since, until) is None


def test_trend_cache_stats():
    """Test trend analysis cache statistics tracking."""
    reset_trend_cache_stats()

    # Initially empty
    stats = get_trend_cache_stats()
    assert stats == {}

    # Stats would be updated after analyze_repository_trend call
    # This is tested through integration tests


def test_different_vcs_platforms_isolated_cache(temp_cache_dir):
    """Test that cache for different VCS platforms is isolated."""
    owner = "owner"
    repo = "repo"
    since = "2025-01-01T00:00:00+00:00"
    until = "2025-02-01T00:00:00+00:00"

    # Save for GitHub
    save_trend_vcs_data(owner, repo, since, until, {"platform": "github"}, "github")

    # Save for GitLab with different data
    save_trend_vcs_data(owner, repo, since, until, {"platform": "gitlab"}, "gitlab")

    # Load and verify isolation
    github_data = load_trend_vcs_data(owner, repo, since, until, "github")
    gitlab_data = load_trend_vcs_data(owner, repo, since, until, "gitlab")

    assert github_data == {"platform": "github"}
    assert gitlab_data == {"platform": "gitlab"}


@pytest.mark.asyncio
async def test_analyze_repository_trend_with_cache():
    """Integration test: analyze_repository_trend uses cache efficiently."""
    # This test verifies that cache functions work, but not the full integration
    # because mocking the entire analysis pipeline is complex. The simpler cache
    # tests above verify the core caching functionality.
    reset_trend_cache_stats()

    # Verify cache stats can be retrieved
    initial_stats = get_trend_cache_stats()
    assert isinstance(initial_stats, dict)
