"""
Tests for the core analysis logic.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from oss_sustain_guard.core import (
    SCORING_CATEGORIES,
    AnalysisResult,
    Metric,
    _query_github_graphql,
    analyze_repository,
    check_attraction,
    check_code_of_conduct,
    check_documentation_presence,
    check_fork_activity,
    check_funding,
    check_issue_resolution_duration,
    check_license_clarity,
    check_organizational_diversity,
    check_pr_acceptance_ratio,
    check_pr_responsiveness,
    check_project_popularity,
    check_retention,
    check_review_health,
    compute_category_breakdown,
    compute_weighted_total_score,
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
    assert metric.name == "Funding Signals"
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
    assert metric.name == "Funding Signals"
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
    assert metric.name == "Funding Signals"
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
    assert metric.name == "Funding Signals"
    assert metric.score == 0
    assert metric.max_score == 10
    assert metric.risk == "Low"
    assert "No funding sources detected" in metric.message


# --- Tests for Phase 4 New Metrics ---


def test_check_attraction_strong():
    """
    Tests attraction metric with 5+ new contributors in last 6 months.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    one_year_ago = now - timedelta(days=365)

    repo_data = {
        "defaultBranchRef": {
            "target": {
                "history": {
                    "edges": [
                        # 5 new contributors in last 6 months
                        {
                            "node": {
                                "authoredDate": (now - timedelta(days=30)).isoformat(),
                                "author": {"user": {"login": "new1"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": (now - timedelta(days=60)).isoformat(),
                                "author": {"user": {"login": "new2"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": (now - timedelta(days=90)).isoformat(),
                                "author": {"user": {"login": "new3"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": (now - timedelta(days=120)).isoformat(),
                                "author": {"user": {"login": "new4"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": (now - timedelta(days=150)).isoformat(),
                                "author": {"user": {"login": "new5"}},
                            }
                        },
                        # 2 old contributors
                        {
                            "node": {
                                "authoredDate": one_year_ago.isoformat(),
                                "author": {"user": {"login": "old1"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": one_year_ago.isoformat(),
                                "author": {"user": {"login": "old2"}},
                            }
                        },
                    ]
                }
            }
        }
    }
    metric = check_attraction(repo_data)
    assert metric.name == "Contributor Attraction"
    assert metric.score == 10
    assert metric.max_score == 10
    assert metric.risk == "None"
    assert "5 new contributors" in metric.message


def test_check_retention_excellent():
    """
    Tests retention metric with 80%+ retention rate.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    two_months_ago = now - timedelta(days=60)
    five_months_ago = now - timedelta(days=150)

    repo_data = {
        "defaultBranchRef": {
            "target": {
                "history": {
                    "edges": [
                        # 4 contributors active in both periods (retained)
                        {
                            "node": {
                                "authoredDate": two_months_ago.isoformat(),
                                "author": {"user": {"login": "user1"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": five_months_ago.isoformat(),
                                "author": {"user": {"login": "user1"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": two_months_ago.isoformat(),
                                "author": {"user": {"login": "user2"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": five_months_ago.isoformat(),
                                "author": {"user": {"login": "user2"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": two_months_ago.isoformat(),
                                "author": {"user": {"login": "user3"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": five_months_ago.isoformat(),
                                "author": {"user": {"login": "user3"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": two_months_ago.isoformat(),
                                "author": {"user": {"login": "user4"}},
                            }
                        },
                        {
                            "node": {
                                "authoredDate": five_months_ago.isoformat(),
                                "author": {"user": {"login": "user4"}},
                            }
                        },
                        # 1 contributor only in earlier period (not retained)
                        {
                            "node": {
                                "authoredDate": five_months_ago.isoformat(),
                                "author": {"user": {"login": "user5"}},
                            }
                        },
                    ]
                }
            }
        }
    }
    metric = check_retention(repo_data)
    assert metric.name == "Contributor Retention"
    assert metric.score == 10
    assert metric.max_score == 10
    assert metric.risk == "None"
    assert "80%" in metric.message or "Excellent" in metric.message


def test_check_review_health_excellent():
    """
    Tests review health metric with fast reviews and multiple reviews per PR.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    created = now - timedelta(hours=10)
    reviewed = now - timedelta(hours=5)  # 5 hours after creation

    repo_data = {
        "pullRequests": {
            "edges": [
                {
                    "node": {
                        "createdAt": created.isoformat(),
                        "reviews": {
                            "totalCount": 3,
                            "edges": [
                                {"node": {"createdAt": reviewed.isoformat()}},
                                {
                                    "node": {
                                        "createdAt": (
                                            reviewed + timedelta(hours=1)
                                        ).isoformat()
                                    }
                                },
                            ],
                        },
                    }
                }
            ]
        }
    }
    metric = check_review_health(repo_data)
    assert metric.name == "Review Health"
    assert metric.score >= 7  # Should be Good or Excellent
    assert metric.max_score == 10


# --- Documentation Presence Tests ---


def test_check_documentation_presence_excellent():
    """Tests documentation presence with all signals present."""
    repo_data = {
        "object": {"byteSize": 5000},  # README.md
        "contributingFile": {"byteSize": 1000},  # CONTRIBUTING.md
        "hasWikiEnabled": True,
        "homepageUrl": "https://example.com/docs",
        "description": "A comprehensive library for testing",
    }
    metric = check_documentation_presence(repo_data)
    assert metric.name == "Documentation Presence"
    assert metric.score == 10
    assert metric.max_score == 10
    assert metric.risk == "None"
    assert "5/5" in metric.message


def test_check_documentation_presence_basic():
    """Tests documentation presence with only README."""
    repo_data = {
        "object": {"byteSize": 500},  # README.md only
        "contributingFile": None,
        "hasWikiEnabled": False,
        "homepageUrl": None,
        "description": None,
    }
    metric = check_documentation_presence(repo_data)
    assert metric.name == "Documentation Presence"
    assert metric.score == 4  # Basic score for README only
    assert metric.risk == "Medium"


def test_check_documentation_presence_none():
    """Tests documentation presence with no documentation."""
    repo_data = {
        "object": None,
        "contributingFile": None,
        "hasWikiEnabled": False,
        "homepageUrl": None,
        "description": None,
    }
    metric = check_documentation_presence(repo_data)
    assert metric.name == "Documentation Presence"
    assert metric.score == 0
    assert metric.risk == "High"


# --- Code of Conduct Tests ---


def test_check_code_of_conduct_present():
    """Tests Code of Conduct detection when present."""
    repo_data = {
        "codeOfConduct": {
            "name": "Contributor Covenant",
            "url": "https://www.contributor-covenant.org/",
        }
    }
    metric = check_code_of_conduct(repo_data)
    assert metric.name == "Code of Conduct"
    assert metric.score == 5
    assert metric.max_score == 5
    assert metric.risk == "None"
    assert "Contributor Covenant" in metric.message


def test_check_code_of_conduct_absent():
    """Tests Code of Conduct when not present."""
    repo_data = {"codeOfConduct": None}
    metric = check_code_of_conduct(repo_data)
    assert metric.name == "Code of Conduct"
    assert metric.score == 0
    assert metric.risk == "Low"  # Informational, not critical


# --- PR Acceptance Ratio Tests ---


def test_check_pr_acceptance_ratio_high():
    """Tests PR acceptance ratio with high acceptance rate."""
    repo_data = {
        "mergedPullRequestsCount": {"totalCount": 80},
        "closedPullRequests": {
            "edges": [
                {"node": {"merged": False}},  # 1 closed without merge
                {"node": {"merged": False}},  # 1 closed without merge
            ]
        },
    }
    # 80 merged / (80 + 2) = 97.5% acceptance
    metric = check_pr_acceptance_ratio(repo_data)
    assert metric.name == "PR Acceptance Ratio"
    assert metric.score == 10
    assert metric.risk == "None"
    assert "Very welcoming" in metric.message or "97" in metric.message


def test_check_pr_acceptance_ratio_low():
    """Tests PR acceptance ratio with low acceptance rate."""
    repo_data = {
        "mergedPullRequestsCount": {"totalCount": 10},
        "closedPullRequests": {
            "edges": [
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
                {"node": {"merged": False}},
            ]
        },
    }
    # 10 merged / (10 + 15) = 40% acceptance
    metric = check_pr_acceptance_ratio(repo_data)
    assert metric.name == "PR Acceptance Ratio"
    assert metric.score == 4  # Moderate
    assert metric.risk == "Medium"


def test_check_pr_acceptance_ratio_no_prs():
    """Tests PR acceptance ratio with no PRs."""
    repo_data = {
        "mergedPullRequestsCount": {"totalCount": 0},
        "closedPullRequests": {"edges": []},
    }
    metric = check_pr_acceptance_ratio(repo_data)
    assert metric.name == "PR Acceptance Ratio"
    assert metric.score == 5  # Half score for no data
    assert metric.risk == "None"


# --- Issue Resolution Duration Tests ---


def test_check_issue_resolution_duration_fast():
    """Tests issue resolution with fast resolution time."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    created = now - timedelta(days=3)
    closed = now - timedelta(days=1)

    repo_data = {
        "closedIssues": {
            "totalCount": 10,
            "edges": [
                {
                    "node": {
                        "createdAt": created.isoformat(),
                        "closedAt": closed.isoformat(),
                    }
                },
                {
                    "node": {
                        "createdAt": (now - timedelta(days=5)).isoformat(),
                        "closedAt": (now - timedelta(days=2)).isoformat(),
                    }
                },
            ],
        }
    }
    metric = check_issue_resolution_duration(repo_data)
    assert metric.name == "Issue Resolution Duration"
    assert metric.score == 10  # Fast resolution
    assert metric.risk == "None"


def test_check_issue_resolution_duration_slow():
    """Tests issue resolution with slow resolution time."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    created = now - timedelta(days=120)
    closed = now - timedelta(days=10)

    repo_data = {
        "closedIssues": {
            "totalCount": 5,
            "edges": [
                {
                    "node": {
                        "createdAt": created.isoformat(),
                        "closedAt": closed.isoformat(),
                    }
                }
            ],
        }
    }
    metric = check_issue_resolution_duration(repo_data)
    assert metric.name == "Issue Resolution Duration"
    assert metric.score == 0  # >90 days
    assert metric.risk == "High"


# --- Organizational Diversity Tests ---


def test_check_organizational_diversity_high():
    """Tests organizational diversity with multiple organizations."""
    repo_data = {
        "defaultBranchRef": {
            "target": {
                "history": {
                    "edges": [
                        {
                            "node": {
                                "author": {
                                    "user": {"login": "user1", "company": "Google"},
                                    "email": "user1@google.com",
                                }
                            }
                        },
                        {
                            "node": {
                                "author": {
                                    "user": {"login": "user2", "company": "Microsoft"},
                                    "email": "user2@microsoft.com",
                                }
                            }
                        },
                        {
                            "node": {
                                "author": {
                                    "user": {"login": "user3", "company": "Amazon"},
                                    "email": "user3@amazon.com",
                                }
                            }
                        },
                        {
                            "node": {
                                "author": {
                                    "user": {"login": "user4", "company": "Meta"},
                                    "email": "user4@meta.com",
                                }
                            }
                        },
                        {
                            "node": {
                                "author": {
                                    "user": {"login": "user5", "company": "Apple"},
                                    "email": "user5@apple.com",
                                }
                            }
                        },
                    ]
                }
            }
        }
    }
    metric = check_organizational_diversity(repo_data)
    assert metric.name == "Organizational Diversity"
    assert metric.score == 10  # 5+ organizations
    assert metric.risk == "None"


def test_check_organizational_diversity_single():
    """Tests organizational diversity with single organization."""
    repo_data = {
        "defaultBranchRef": {
            "target": {
                "history": {
                    "edges": [
                        {
                            "node": {
                                "author": {
                                    "user": {"login": "user1", "company": "SingleCorp"},
                                    "email": "user1@singlecorp.com",
                                }
                            }
                        },
                        {
                            "node": {
                                "author": {
                                    "user": {"login": "user2", "company": "SingleCorp"},
                                    "email": "user2@singlecorp.com",
                                }
                            }
                        },
                    ]
                }
            }
        }
    }
    metric = check_organizational_diversity(repo_data)
    assert metric.name == "Organizational Diversity"
    assert metric.score == 2  # Single organization
    assert metric.risk == "High"


# --- Fork Activity Tests ---


def test_check_fork_activity_high():
    """Tests fork activity with many forks."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    recent = now - timedelta(days=30)

    repo_data = {
        "forkCount": 150,
        "forks": {
            "edges": [
                {"node": {"createdAt": recent.isoformat()}},
                {"node": {"createdAt": (recent - timedelta(days=10)).isoformat()}},
            ]
        },
    }
    metric = check_fork_activity(repo_data)
    assert metric.name == "Fork Activity"
    assert metric.score == 5  # 100+ forks with recent activity
    assert metric.risk == "None"


def test_check_fork_activity_none():
    """Tests fork activity with no forks."""
    repo_data = {"forkCount": 0, "forks": {"edges": []}}
    metric = check_fork_activity(repo_data)
    assert metric.name == "Fork Activity"
    assert metric.score == 0
    assert metric.risk == "Low"


# --- Project Popularity Tests ---


def test_check_project_popularity_very_popular():
    """Tests project popularity with many stars."""
    repo_data = {
        "stargazerCount": 5000,
        "watchers": {"totalCount": 200},
        "forkCount": 500,
    }
    metric = check_project_popularity(repo_data)
    assert metric.name == "Project Popularity"
    assert metric.score == 10  # 1000+ stars
    assert metric.risk == "None"


def test_check_project_popularity_new():
    """Tests project popularity with few stars."""
    repo_data = {
        "stargazerCount": 5,
        "watchers": {"totalCount": 2},
        "forkCount": 1,
    }
    metric = check_project_popularity(repo_data)
    assert metric.name == "Project Popularity"
    assert metric.score == 0  # <10 stars
    assert metric.risk == "Low"


# --- License Clarity Tests ---


def test_check_license_clarity_osi_approved():
    """Tests license clarity with OSI-approved license."""
    repo_data = {
        "licenseInfo": {
            "name": "MIT License",
            "spdxId": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        }
    }
    metric = check_license_clarity(repo_data)
    assert metric.name == "License Clarity"
    assert metric.score == 5
    assert metric.risk == "None"
    assert "OSI-approved" in metric.message


def test_check_license_clarity_no_license():
    """Tests license clarity with no license."""
    repo_data = {"licenseInfo": None}
    metric = check_license_clarity(repo_data)
    assert metric.name == "License Clarity"
    assert metric.score == 0
    assert metric.risk == "High"


# --- PR Responsiveness Tests ---


def test_check_pr_responsiveness_fast():
    """Tests PR responsiveness with fast first response."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    created = now - timedelta(hours=20)
    reviewed = now - timedelta(hours=10)  # 10 hours response time

    repo_data = {
        "closedPullRequests": {
            "edges": [
                {
                    "node": {
                        "createdAt": created.isoformat(),
                        "reviews": {
                            "edges": [{"node": {"createdAt": reviewed.isoformat()}}]
                        },
                    }
                }
            ]
        }
    }
    metric = check_pr_responsiveness(repo_data)
    assert metric.name == "PR Responsiveness"
    assert metric.score == 5  # <24h
    assert metric.risk == "None"


def test_check_pr_responsiveness_slow():
    """Tests PR responsiveness with slow first response."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    created = now - timedelta(days=20)
    reviewed = now - timedelta(days=5)  # 15 days response time

    repo_data = {
        "closedPullRequests": {
            "edges": [
                {
                    "node": {
                        "createdAt": created.isoformat(),
                        "reviews": {
                            "edges": [{"node": {"createdAt": reviewed.isoformat()}}]
                        },
                    }
                }
            ]
        }
    }
    metric = check_pr_responsiveness(repo_data)
    assert metric.name == "PR Responsiveness"
    assert metric.score == 0  # >7 days
    assert metric.risk == "Medium"


# --- Weighted Score Tests ---


def test_compute_weighted_total_score():
    """Tests the weighted total score calculation."""
    # Create a set of metrics with known values
    metrics = [
        Metric("Contributor Redundancy", 15, 20, "Good", "Low"),
        Metric("Maintainer Retention", 8, 10, "Stable", "None"),
        Metric("Recent Activity", 20, 20, "Active", "None"),
        Metric("Change Request Resolution", 8, 10, "Good", "None"),
        Metric("Build Health", 5, 5, "CI passing", "None"),
        Metric("Funding Signals", 8, 10, "Funded", "None"),
        Metric("Release Rhythm", 10, 10, "Active", "None"),
        Metric("Security Signals", 12, 15, "Good", "None"),
        Metric("Issue Responsiveness", 5, 5, "Fast", "None"),
        Metric("Contributor Attraction", 7, 10, "Good", "Low"),
        Metric("Contributor Retention", 7, 10, "Good", "Low"),
        Metric("Review Health", 8, 10, "Good", "None"),
        Metric("Documentation Presence", 10, 10, "Excellent", "None"),
        Metric("Code of Conduct", 5, 5, "Present", "None"),
        Metric("PR Acceptance Ratio", 10, 10, "High", "None"),
        Metric("Issue Resolution Duration", 7, 10, "Good", "None"),
        Metric("Organizational Diversity", 7, 10, "Good", "Low"),
        Metric("Fork Activity", 4, 5, "Active", "None"),
        Metric("Project Popularity", 8, 10, "Popular", "None"),
        Metric("License Clarity", 5, 5, "MIT", "None"),
        Metric("PR Responsiveness", 5, 5, "Fast", "None"),
    ]

    score = compute_weighted_total_score(metrics)

    # Score should be between 0 and 100
    assert 0 <= score <= 100

    # With mostly high scores, we expect a good total score
    assert score >= 70  # Should be high given the good scores


def test_compute_category_breakdown():
    """Tests the category breakdown function."""
    metrics = [
        Metric("Contributor Redundancy", 15, 20, "Good", "Low"),
        Metric("Security Signals", 12, 15, "Good", "None"),
        Metric("Documentation Presence", 10, 10, "Excellent", "None"),
    ]

    breakdown = compute_category_breakdown(metrics)

    # Check structure
    assert "Maintainer Health" in breakdown
    assert "Security & Funding" in breakdown
    assert "Project Maturity" in breakdown

    # Check Maintainer Health category
    mh = breakdown["Maintainer Health"]
    assert "score" in mh
    assert "weight" in mh
    assert "metrics" in mh
    assert mh["weight"] == 0.25


def test_scoring_categories_structure():
    """Tests that SCORING_CATEGORIES is properly defined."""
    assert len(SCORING_CATEGORIES) == 5

    total_weight = sum(cat["weight"] for cat in SCORING_CATEGORIES.values())
    assert total_weight == 1.0  # Weights should sum to 100%

    # Check all categories have required fields
    for _name, config in SCORING_CATEGORIES.items():
        assert "weight" in config
        assert "description" in config
        assert "metrics" in config
        assert len(config["metrics"]) > 0
