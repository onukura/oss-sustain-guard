"""
Tests for the core analysis logic.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from oss_sustain_guard.core import (
    AnalysisResult,
    Metric,
    _query_github_graphql,
    analyze_repository,
)

# --- Mocks ---


@pytest.fixture
def mock_graphql_query():
    """Fixture to patch _query_github_graphql."""
    with patch("oss_sustain_guard.core._query_github_graphql") as mock_query:
        yield mock_query


# --- Tests ---


def test_analyze_repository_structure(mock_graphql_query):
    """
    Tests that analyze_repository returns the correct data structure.
    This test uses the placeholder logic in core.py.
    """
    # Arrange
    mock_graphql_query.return_value = {
        "repository": {
            "isArchived": False,
            "pushedAt": "2024-12-06T10:00:00Z",
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [{"node": {"author": {"user": {"login": "user1"}}}}]
                    }
                }
            },
            "pullRequests": {"edges": []},
            "fundingLinks": [],
        }
    }

    # Act
    result = analyze_repository("test-owner", "test-repo")

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


def test_total_score_is_sum_of_metric_scores(mock_graphql_query):
    """
    Tests that the total_score is calculated using category-weighted approach.
    """
    # Arrange
    mock_graphql_query.return_value = {
        "repository": {
            "isArchived": False,
            "pushedAt": "2024-12-06T10:00:00Z",
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [{"node": {"author": {"user": {"login": "user1"}}}}]
                    }
                }
            },
            "pullRequests": {"edges": []},
            "fundingLinks": [],
        }
    }

    # Act
    result = analyze_repository("test-owner", "test-repo")

    # Assert
    # Score should be normalized to 100-point scale using category weights
    assert 0 <= result.total_score <= 100  # Score should be within valid range
    # New: score is computed via compute_weighted_total_score
    # which uses category-based weighting, not simple sum normalization


@patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}, clear=True)
@patch("oss_sustain_guard.core.GITHUB_TOKEN", "fake_token")
@patch("httpx.Client.post")
def test_query_github_graphql_success(mock_post):
    """
    Tests a successful GraphQL query.
    """
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"repository": {"name": "test"}}}
    mock_post.return_value = mock_response

    # Act
    data = _query_github_graphql("query {}", {})

    # Assert
    assert data == {"repository": {"name": "test"}}
    mock_post.assert_called_once()


@patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}, clear=True)
@patch("oss_sustain_guard.core.GITHUB_TOKEN", "fake_token")
@patch("httpx.Client.post")
def test_query_github_graphql_api_error(mock_post):
    """
    Tests handling of a GitHub API error in the response.
    """
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errors": [{"message": "Bad credentials"}]}
    mock_post.return_value = mock_response

    # Act & Assert
    with pytest.raises(httpx.HTTPStatusError):
        _query_github_graphql("query {}", {})


@patch("oss_sustain_guard.core.GITHUB_TOKEN", None)
def test_query_github_graphql_no_token():
    """
    Tests that a ValueError is raised if the GITHUB_TOKEN is not set.
    """
    with pytest.raises(
        ValueError, match="GITHUB_TOKEN environment variable is required"
    ):
        _query_github_graphql("query {}", {})


# --- Tests for analyze_repository error handling ---


def test_analyze_repository_not_found(mock_graphql_query):
    """Test analyze_repository raises error for non-existent repository."""
    from oss_sustain_guard.core import analyze_repository

    mock_graphql_query.return_value = {}

    with pytest.raises(ValueError, match="not found or is inaccessible"):
        analyze_repository("nonexistent", "repo")
