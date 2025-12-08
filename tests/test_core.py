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
    check_funding,
    is_corporate_backed,
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
    Tests that the total_score is normalized to 100-point scale.
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
    # Score should be normalized to 100-point scale
    raw_score = sum(m.score for m in result.metrics)
    max_possible = sum(m.max_score for m in result.metrics)
    expected_normalized = int((raw_score / max_possible) * 100)
    assert result.total_score == expected_normalized
    assert 0 <= result.total_score <= 100  # Score should be within valid range


@patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}, clear=True)
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
        ValueError, match="GITHUB_TOKEN environment variable is not set"
    ):
        _query_github_graphql("query {}", {})


def test_is_corporate_backed_organization():
    """
    Tests is_corporate_backed returns True for organization-owned repos.
    """
    repo_data = {
        "owner": {
            "__typename": "Organization",
            "login": "astral-sh",
        }
    }
    assert is_corporate_backed(repo_data) is True


def test_is_corporate_backed_user():
    """
    Tests is_corporate_backed returns False for user-owned repos.
    """
    repo_data = {
        "owner": {
            "__typename": "User",
            "login": "individual",
        }
    }
    assert is_corporate_backed(repo_data) is False


def test_check_funding_corporate_backed_with_funding():
    """
    Tests funding metric for corporate-backed repo with funding links.
    Corporate backing makes max_score 5 (not critical).
    """
    repo_data = {
        "owner": {
            "__typename": "Organization",
            "login": "astral-sh",
        },
        "fundingLinks": [
            {"platform": "GITHUB_SPONSORS", "url": "https://github.com/sponsors/astral"}
        ],
    }
    metric = check_funding(repo_data)
    assert metric.name == "Funding"
    assert metric.score == 5
    assert metric.max_score == 5
    assert metric.risk == "None"
    assert "Corporate backing sufficient" in metric.message


def test_check_funding_corporate_backed_no_funding():
    """
    Tests funding metric for corporate-backed repo without funding links.
    Corporate backing alone provides max points (5/5).
    """
    repo_data = {
        "owner": {
            "__typename": "Organization",
            "login": "astral-sh",
        },
        "fundingLinks": [],
    }
    metric = check_funding(repo_data)
    assert metric.name == "Funding"
    assert metric.score == 5
    assert metric.max_score == 5
    assert metric.risk == "None"
    assert "Corporate backing" in metric.message


def test_check_funding_community_with_funding():
    """
    Tests funding metric for community-driven repo with funding links.
    Community funding is important (max_score 10).
    """
    repo_data = {
        "owner": {
            "__typename": "User",
            "login": "maintainer",
        },
        "fundingLinks": [
            {
                "platform": "GITHUB_SPONSORS",
                "url": "https://github.com/sponsors/maintainer",
            }
        ],
    }
    metric = check_funding(repo_data)
    assert metric.name == "Funding"
    assert metric.score == 8
    assert metric.max_score == 10
    assert metric.risk == "None"
    assert "Community-funded" in metric.message


def test_check_funding_community_no_funding():
    """
    Tests funding metric for community-driven repo without funding.
    No funding is risky for community projects.
    """
    repo_data = {
        "owner": {
            "__typename": "User",
            "login": "maintainer",
        },
        "fundingLinks": [],
    }
    metric = check_funding(repo_data)
    assert metric.name == "Funding"
    assert metric.score == 0
    assert metric.max_score == 10
    assert metric.risk == "Low"
    assert "No funding sources detected" in metric.message
