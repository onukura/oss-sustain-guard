"""
Tests for the core analysis logic.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from oss_sustain_guard.core import (
    AnalysisResult,
    Metric,
    analyze_repository,
)

# --- Mocks ---


@pytest.fixture
def mock_vcs_provider():
    """Fixture to patch VCS provider."""
    with patch("oss_sustain_guard.core.get_vcs_provider") as mock_provider:
        yield mock_provider


# --- Tests ---


async def test_analyze_repository_structure(mock_vcs_provider):
    """
    Tests that analyze_repository returns the correct data structure.
    This test uses the VCS abstraction layer.
    """
    # Arrange - Mock VCS provider
    mock_provider_instance = MagicMock()
    mock_vcs_provider.return_value = mock_provider_instance

    # Mock VCSRepositoryData
    from oss_sustain_guard.vcs.base import VCSRepositoryData

    mock_vcs_data = VCSRepositoryData(
        is_archived=False,
        pushed_at="2024-12-06T10:00:00Z",
        owner_type="User",
        owner_login="testuser",
        owner_name=None,
        star_count=0,
        description=None,
        homepage_url=None,
        topics=[],
        readme_size=None,
        contributing_file_size=None,
        default_branch=None,
        watchers_count=0,
        open_issues_count=0,
        language=None,
        commits=[{"author": {"user": {"login": "user1"}}}],
        total_commits=1,
        merged_prs=[],
        closed_prs=[],
        total_merged_prs=0,
        releases=[],
        open_issues=[],
        closed_issues=[],
        total_closed_issues=0,
        vulnerability_alerts=None,
        has_security_policy=False,
        code_of_conduct=None,
        license_info=None,
        has_wiki=False,
        has_issues=True,
        has_discussions=False,
        funding_links=[],
        forks=[],
        total_forks=0,
        ci_status=None,
        sample_counts={},
        raw_data={
            "isArchived": False,
            "pushedAt": "2024-12-06T10:00:00Z",
            "owner": {"__typename": "User", "login": "testuser"},
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [{"node": {"author": {"user": {"login": "user1"}}}}]
                    }
                }
            },
            "pullRequests": {"edges": []},
            "fundingLinks": [],
        },
    )
    mock_provider_instance.get_repository_data = AsyncMock(return_value=mock_vcs_data)
    mock_provider_instance.get_repository_url.return_value = (
        "https://github.com/test-owner/test-repo"
    )

    # Act
    result = await analyze_repository("test-owner", "test-repo")

    # Assert
    assert isinstance(result, AnalysisResult)
    assert result.repo_url == "https://github.com/test-owner/test-repo"
    assert isinstance(result.total_score, int)
    assert isinstance(result.metrics, list)
    assert len(result.metrics) > 0

    first_metric = result.metrics[0]
    assert isinstance(first_metric, Metric)
    assert isinstance(first_metric.name, str)
    assert isinstance(first_metric.score, int)
    assert isinstance(first_metric.risk, str)


async def test_total_score_is_sum_of_metric_scores(mock_vcs_provider):
    """
    Tests that the total_score is calculated using category-weighted approach.
    """
    # Arrange
    from oss_sustain_guard.vcs.base import VCSRepositoryData

    mock_provider_instance = MagicMock()
    mock_vcs_provider.return_value = mock_provider_instance

    mock_vcs_data = VCSRepositoryData(
        is_archived=False,
        pushed_at="2024-12-06T10:00:00Z",
        owner_type="User",
        owner_login="test-owner",
        owner_name=None,
        star_count=0,
        description=None,
        homepage_url=None,
        topics=[],
        readme_size=None,
        contributing_file_size=None,
        default_branch=None,
        watchers_count=0,
        open_issues_count=0,
        language=None,
        commits=[{"author": {"user": {"login": "user1"}}}],
        total_commits=1,
        merged_prs=[],
        closed_prs=[],
        total_merged_prs=0,
        releases=[],
        open_issues=[],
        closed_issues=[],
        total_closed_issues=0,
        vulnerability_alerts=None,
        has_security_policy=False,
        code_of_conduct=None,
        license_info=None,
        has_wiki=False,
        has_issues=True,
        has_discussions=False,
        funding_links=[],
        forks=[],
        total_forks=0,
        ci_status=None,
        sample_counts={},
        raw_data={
            "isArchived": False,
            "pushedAt": "2024-12-06T10:00:00Z",
            "owner": {"__typename": "User", "login": "test-owner"},
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [{"node": {"author": {"user": {"login": "user1"}}}}]
                    }
                }
            },
            "pullRequests": {"edges": []},
            "fundingLinks": [],
        },
    )
    mock_provider_instance.get_repository_data = AsyncMock(return_value=mock_vcs_data)
    mock_provider_instance.get_repository_url.return_value = (
        "https://github.com/test-owner/test-repo"
    )

    # Act
    result = await analyze_repository("test-owner", "test-repo")

    # Assert
    # Score should be normalized to 100-point scale using category weights
    assert 0 <= result.total_score <= 100  # Score should be within valid range
    # New: score is computed via compute_weighted_total_score
    # which uses category-based weighting, not simple sum normalization


@patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}, clear=True)
async def test_analyze_repository_with_vcs_provider(mock_vcs_provider):
    """Test analyze_repository using VCS provider."""
    # Arrange
    from oss_sustain_guard.vcs.base import VCSRepositoryData

    mock_provider_instance = MagicMock()
    mock_vcs_provider.return_value = mock_provider_instance

    mock_vcs_data = VCSRepositoryData(
        is_archived=False,
        pushed_at="2024-12-06T10:00:00Z",
        owner_type="User",
        owner_login="test-owner",
        owner_name=None,
        star_count=0,
        description=None,
        homepage_url=None,
        topics=[],
        readme_size=None,
        contributing_file_size=None,
        default_branch=None,
        watchers_count=0,
        open_issues_count=0,
        language=None,
        commits=[],
        total_commits=0,
        merged_prs=[],
        closed_prs=[],
        total_merged_prs=0,
        releases=[],
        open_issues=[],
        closed_issues=[],
        total_closed_issues=0,
        vulnerability_alerts=None,
        has_security_policy=False,
        code_of_conduct=None,
        license_info=None,
        has_wiki=False,
        has_issues=True,
        has_discussions=False,
        funding_links=[],
        forks=[],
        total_forks=0,
        ci_status=None,
        sample_counts={},
        raw_data={
            "isArchived": False,
            "pushedAt": "2024-12-06T10:00:00Z",
            "owner": {"__typename": "User", "login": "test-owner"},
            "defaultBranchRef": None,
            "pullRequests": {"edges": []},
            "fundingLinks": [],
        },
    )
    mock_provider_instance.get_repository_data = AsyncMock(return_value=mock_vcs_data)
    mock_provider_instance.get_repository_url.return_value = (
        "https://github.com/test-owner/test-repo"
    )

    # Act
    result = await analyze_repository("test-owner", "test-repo")

    # Assert
    assert isinstance(result, AnalysisResult)
    assert result.repo_url == "https://github.com/test-owner/test-repo"


async def test_analyze_repository_vcs_error(mock_vcs_provider):
    """Test analyze_repository handles VCS provider errors."""
    mock_provider_instance = MagicMock()
    mock_vcs_provider.return_value = mock_provider_instance
    mock_provider_instance.get_repository_data.side_effect = httpx.HTTPStatusError(
        "API Error",
        request=MagicMock(),
        response=MagicMock(),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await analyze_repository("owner", "repo")


# --- Tests for analyze_repository error handling ---


async def test_analyze_repository_not_found(mock_vcs_provider):
    """Test analyze_repository raises error for non-existent repository."""
    mock_provider_instance = MagicMock()
    mock_vcs_provider.return_value = mock_provider_instance
    mock_provider_instance.get_repository_data.side_effect = ValueError(
        "Repository nonexistent/repo not found or is inaccessible."
    )

    with pytest.raises(ValueError, match="not found or is inaccessible"):
        await analyze_repository("nonexistent", "repo")
