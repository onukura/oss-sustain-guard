"""Tests for GitLab VCS provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from oss_sustain_guard.vcs.gitlab import GitLabProvider


def test_gitlab_provider_requires_token():
    """Test that GitLabProvider requires a token."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="GITLAB_TOKEN is required"):
            GitLabProvider()


def test_gitlab_provider_accepts_token_parameter():
    """Test that GitLabProvider accepts token as parameter."""
    provider = GitLabProvider(token="test_token")
    assert provider.token == "test_token"
    assert provider.get_platform_name() == "gitlab"


def test_gitlab_provider_reads_token_from_env():
    """Test that GitLabProvider reads token from environment."""
    with patch.dict("os.environ", {"GITLAB_TOKEN": "env_token"}):
        provider = GitLabProvider()
        assert provider.token == "env_token"


def test_gitlab_provider_validate_credentials():
    """Test GitLabProvider credential validation."""
    provider = GitLabProvider(token="test_token")
    assert provider.validate_credentials() is True

    # Empty token should fail validation at __init__ time
    with pytest.raises(ValueError, match="GITLAB_TOKEN is required"):
        with patch.dict("os.environ", {}, clear=True):
            GitLabProvider(token="")


def test_gitlab_provider_get_repository_url():
    """Test GitLabProvider repository URL construction."""
    provider = GitLabProvider(token="test_token")
    url = provider.get_repository_url("owner", "repo")
    assert url == "https://gitlab.com/owner/repo"


@patch("oss_sustain_guard.vcs.gitlab._get_async_http_client")
async def test_gitlab_provider_get_repository_data(mock_get_client):
    """Test GitLabProvider fetches and normalizes repository data."""
    # Mock HTTP client response
    mock_client = AsyncMock()
    mock_graphql_response = MagicMock()
    mock_graphql_response.raise_for_status = MagicMock(return_value=None)
    mock_graphql_response.json = MagicMock(
        return_value={
            "data": {
                "project": {
                    "archived": False,
                    "lastActivityAt": "2024-01-01T00:00:00Z",
                    "namespace": {
                        "fullPath": "testgroup/subgroup",
                        "name": "Test Group",
                    },
                    "repository": {"rootRef": "main"},
                    "mergeRequests": {
                        "edges": [
                            {
                                "node": {
                                    "mergedAt": "2024-01-01T00:00:00Z",
                                    "createdAt": "2023-12-31T00:00:00Z",
                                    "mergeUser": {"username": "user1"},
                                    "approvedBy": {"nodes": []},
                                }
                            }
                        ],
                        "pageInfo": {"hasNextPage": False},
                        "count": 1,
                    },
                    "closedMergeRequests": {
                        "edges": [],
                        "count": 0,
                    },
                    "releases": {
                        "edges": [
                            {
                                "node": {
                                    "releasedAt": "2024-01-01T00:00:00Z",
                                    "tagName": "v1.0.0",
                                }
                            }
                        ]
                    },
                    "issues": {
                        "edges": [
                            {
                                "node": {
                                    "createdAt": "2024-01-01T00:00:00Z",
                                    "notes": {"edges": []},
                                }
                            }
                        ]
                    },
                    "closedIssues": {
                        "edges": [],
                        "count": 0,
                    },
                    "issuesEnabled": True,
                    "wikiEnabled": True,
                    "starCount": 100,
                    "forksCount": 1,
                    "description": "Test project",
                    "webUrl": "https://gitlab.com/testgroup/testrepo",
                }
            }
        }
    )
    mock_rest_response = MagicMock()
    mock_rest_response.raise_for_status = MagicMock(return_value=None)
    mock_rest_response.json = MagicMock(return_value=[])
    mock_client.post = AsyncMock(return_value=mock_graphql_response)
    mock_client.get = AsyncMock(return_value=mock_rest_response)
    mock_get_client.return_value = mock_client

    provider = GitLabProvider(token="test_token")
    vcs_data = await provider.get_repository_data("testgroup", "testrepo")

    # Verify normalized data structure
    assert vcs_data.owner_login == "testgroup"
    assert vcs_data.owner_type == "Group"
    assert vcs_data.owner_name == "Test Group"
    assert vcs_data.is_archived is False
    assert vcs_data.pushed_at == "2024-01-01T00:00:00Z"
    assert vcs_data.total_merged_prs == 1
    assert len(vcs_data.merged_prs) == 1
    assert vcs_data.has_security_policy is False  # Not available in GraphQL
    assert vcs_data.total_forks == 1
    assert len(vcs_data.releases) == 1


@patch("oss_sustain_guard.vcs.gitlab._get_async_http_client")
async def test_gitlab_provider_handles_missing_repository(mock_get_client):
    """Test GitLabProvider handles missing repository."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(return_value=None)
    mock_response.json = MagicMock(return_value={"data": {"project": None}})
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_get_client.return_value = mock_client

    provider = GitLabProvider(token="test_token")

    with pytest.raises(ValueError, match="not found or is inaccessible"):
        await provider.get_repository_data("nonexistent", "repo")


@patch("oss_sustain_guard.vcs.gitlab._get_async_http_client")
async def test_gitlab_provider_handles_api_error(mock_get_client):
    """Test GitLabProvider handles API errors."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_request = MagicMock(spec=httpx.Request)
    mock_http_response = MagicMock(spec=httpx.Response)
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "API Error", request=mock_request, response=mock_http_response
        )
    )
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_get_client.return_value = mock_client

    provider = GitLabProvider(token="test_token")

    with pytest.raises(httpx.HTTPStatusError):
        await provider.get_repository_data("owner", "repo")


@patch("oss_sustain_guard.vcs.gitlab._get_async_http_client")
async def test_gitlab_provider_handles_graphql_errors(mock_get_client):
    """Test GitLabProvider handles GraphQL errors in response."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(return_value=None)
    mock_response.json = MagicMock(
        return_value={"errors": [{"message": "Some GraphQL error"}]}
    )
    mock_response.request = None
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_get_client.return_value = mock_client

    provider = GitLabProvider(token="test_token")

    with pytest.raises(httpx.HTTPStatusError, match="GitLab API Errors"):
        await provider.get_repository_data("owner", "repo")


def test_gitlab_provider_normalize_merge_request():
    """Test merge request normalization."""
    provider = GitLabProvider(token="test_token")
    mr_node = {
        "mergedAt": "2024-01-01T00:00:00Z",
        "createdAt": "2023-12-31T00:00:00Z",
        "state": "merged",
        "mergeUser": {"username": "user1"},
        "approvedBy": {
            "nodes": [{"createdAt": "2024-01-01T00:00:00Z"}],
        },
    }

    normalized = provider._normalize_merge_request(mr_node)

    assert normalized["mergedAt"] == "2024-01-01T00:00:00Z"
    assert normalized["createdAt"] == "2023-12-31T00:00:00Z"
    assert normalized["merged"] is True
    assert normalized["mergedBy"]["login"] == "user1"
    assert normalized["reviews"]["totalCount"] == 1


def test_gitlab_provider_normalize_release():
    """Test release normalization."""
    provider = GitLabProvider(token="test_token")
    release_node = {
        "releasedAt": "2024-01-01T00:00:00Z",
        "tagName": "v1.0.0",
    }

    normalized = provider._normalize_release(release_node)

    assert normalized["publishedAt"] == "2024-01-01T00:00:00Z"
    assert normalized["tagName"] == "v1.0.0"


def test_gitlab_provider_normalize_issue():
    """Test issue normalization."""
    provider = GitLabProvider(token="test_token")
    issue_node = {
        "createdAt": "2024-01-01T00:00:00Z",
        "closedAt": "2024-01-02T00:00:00Z",
        "updatedAt": "2024-01-03T00:00:00Z",
        "notes": {
            "edges": [
                {"node": {"createdAt": "2024-01-01T12:00:00Z"}},
            ]
        },
    }

    normalized = provider._normalize_issue(issue_node)

    assert normalized["createdAt"] == "2024-01-01T00:00:00Z"
    assert normalized["closedAt"] == "2024-01-02T00:00:00Z"
    assert normalized["updatedAt"] == "2024-01-03T00:00:00Z"
    assert len(normalized["comments"]["edges"]) == 1


def test_gitlab_provider_normalize_fork():
    """Test fork normalization."""
    provider = GitLabProvider(token="test_token")
    fork_node = {
        "createdAt": "2024-01-01T00:00:00Z",
        "lastActivityAt": "2024-01-02T00:00:00Z",
        "namespace": {"fullPath": "user/fork"},
    }

    normalized = provider._normalize_fork(fork_node)

    assert normalized["createdAt"] == "2024-01-01T00:00:00Z"
    assert normalized["pushedAt"] == "2024-01-02T00:00:00Z"
    assert normalized["owner"]["login"] == "user"
