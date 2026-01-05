"""Tests for GitHub VCS provider."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from oss_sustain_guard.vcs.github import GitHubProvider


def test_github_provider_requires_token():
    """Test that GitHubProvider requires a token."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="GITHUB_TOKEN is required"):
            GitHubProvider()


def test_github_provider_accepts_token_parameter():
    """Test that GitHubProvider accepts token as parameter."""
    provider = GitHubProvider(token="test_token")
    assert provider.token == "test_token"
    assert provider.get_platform_name() == "github"


def test_github_provider_reads_token_from_env():
    """Test that GitHubProvider reads token from environment."""
    with patch.dict("os.environ", {"GITHUB_TOKEN": "env_token"}):
        provider = GitHubProvider()
        assert provider.token == "env_token"


def test_github_provider_validate_credentials():
    """Test GitHubProvider credential validation."""
    provider = GitHubProvider(token="test_token")
    assert provider.validate_credentials() is True

    # Empty token should fail validation at __init__ time
    with pytest.raises(ValueError, match="GITHUB_TOKEN is required"):
        with patch.dict("os.environ", {}, clear=True):
            GitHubProvider(token="")


def test_github_provider_get_repository_url():
    """Test GitHubProvider repository URL construction."""
    provider = GitHubProvider(token="test_token")
    url = provider.get_repository_url("owner", "repo")
    assert url == "https://github.com/owner/repo"


@patch("oss_sustain_guard.vcs.github._get_async_http_client")
async def test_github_provider_get_repository_data(mock_get_client):
    """Test GitHubProvider fetches and normalizes repository data."""
    # Mock HTTP client response
    mock_client = mock_get_client.return_value
    mock_response = MagicMock()
    mock_client.post.return_value = mock_response
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "data": {
            "repository": {
                "isArchived": False,
                "pushedAt": "2024-01-01T00:00:00Z",
                "owner": {
                    "__typename": "Organization",
                    "login": "testorg",
                    "name": "Test Organization",
                },
                "defaultBranchRef": {
                    "target": {
                        "history": {
                            "edges": [
                                {
                                    "node": {
                                        "authoredDate": "2024-01-01T00:00:00Z",
                                        "author": {
                                            "user": {"login": "user1", "company": ""},
                                            "email": "user1@example.com",
                                        },
                                    }
                                }
                            ],
                            "totalCount": 100,
                        },
                        "checkSuites": {"nodes": []},
                    }
                },
                "pullRequests": {"edges": []},
                "closedPullRequests": {"totalCount": 0, "edges": []},
                "mergedPullRequestsCount": {"totalCount": 0},
                "releases": {"edges": []},
                "issues": {"edges": []},
                "closedIssues": {"totalCount": 0, "edges": []},
                "vulnerabilityAlerts": {"edges": []},
                "isSecurityPolicyEnabled": True,
                "fundingLinks": [
                    {"platform": "github", "url": "https://github.com/sponsors/testorg"}
                ],
                "hasWikiEnabled": True,
                "hasIssuesEnabled": True,
                "hasDiscussionsEnabled": False,
                "codeOfConduct": {
                    "name": "Contributor Covenant",
                    "url": "https://example.com/coc",
                },
                "licenseInfo": {
                    "name": "MIT License",
                    "spdxId": "MIT",
                    "url": "https://example.com/license",
                },
                "stargazerCount": 100,
                "forkCount": 10,
                "watchers": {"totalCount": 50},
                "forks": {"edges": []},
                "readmeUpperCase": {"byteSize": 100, "text": "# README"},
                "readmeLowerCase": None,
                "readmeAllCaps": None,
                "contributingFile": {"byteSize": 200},
                "description": "Test repository",
                "homepageUrl": "https://example.com",
            }
        }
    }

    provider = GitHubProvider(token="test_token")
    vcs_data = await provider.get_repository_data("testorg", "testrepo")

    # Verify normalized data structure
    assert vcs_data.owner_login == "testorg"
    assert vcs_data.owner_type == "Organization"
    assert vcs_data.owner_name == "Test Organization"
    assert vcs_data.is_archived is False
    assert vcs_data.pushed_at == "2024-01-01T00:00:00Z"
    assert vcs_data.total_commits == 100
    assert len(vcs_data.commits) == 1
    assert vcs_data.has_security_policy is True
    assert len(vcs_data.funding_links) == 1
    assert vcs_data.funding_links[0]["platform"] == "github"


@patch("oss_sustain_guard.vcs.github._get_async_http_client")
async def test_github_provider_handles_missing_repository(mock_get_client):
    """Test GitHubProvider handles missing repository."""
    mock_client = mock_get_client.return_value
    mock_response = MagicMock()
    mock_client.post.return_value = mock_response
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"data": {"repository": None}}

    provider = GitHubProvider(token="test_token")

    with pytest.raises(ValueError, match="not found or is inaccessible"):
        await provider.get_repository_data("nonexistent", "repo")


@patch("oss_sustain_guard.vcs.github._get_async_http_client")
async def test_github_provider_handles_api_error(mock_get_client):
    """Test GitHubProvider handles API errors."""
    mock_client = mock_get_client.return_value
    mock_response = MagicMock()
    mock_client.post.return_value = mock_response
    mock_request = MagicMock()
    mock_response_obj = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "API Error", request=mock_request, response=mock_response_obj
    )

    provider = GitHubProvider(token="test_token")

    with pytest.raises(httpx.HTTPStatusError):
        await provider.get_repository_data("owner", "repo")


@patch("oss_sustain_guard.vcs.github._get_async_http_client")
async def test_github_provider_handles_graphql_errors(mock_get_client):
    """Test GitHubProvider handles GraphQL errors in response."""
    mock_client = mock_get_client.return_value
    mock_response = MagicMock()
    mock_client.post.return_value = mock_response
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"errors": [{"message": "Some GraphQL error"}]}
    mock_response.request = None

    provider = GitHubProvider(token="test_token")

    with pytest.raises(httpx.HTTPStatusError, match="GitHub API Errors"):
        await provider.get_repository_data("owner", "repo")
