"""Tests for MetricChecker compatibility helpers."""

from oss_sustain_guard.metrics.base import Metric, MetricChecker, MetricContext


class DummyChecker(MetricChecker):
    """Simple checker that captures the VCS data passed to it."""

    def __init__(self) -> None:
        self.last_vcs_data = None

    def check(self, vcs_data, _context: MetricContext) -> Metric:
        self.last_vcs_data = vcs_data
        return Metric("Dummy", 1, 10, "Note: ok", "None")


def test_metric_checker_check_legacy_converts_repo_info():
    repo_info = {
        "isArchived": False,
        "pushedAt": "2024-01-01T00:00:00Z",
        "owner": {"__typename": "Organization", "login": "octo", "name": "Octo Org"},
        "defaultBranchRef": {
            "name": "main",
            "target": {
                "history": {
                    "edges": [{"node": {"committedDate": "2024-01-02T00:00:00Z"}}],
                    "totalCount": 5,
                },
                "checkSuites": {
                    "nodes": [{"conclusion": "SUCCESS", "status": "COMPLETED"}]
                },
            },
        },
        "pullRequests": {"edges": [{"node": {"mergedAt": "2024-01-03T00:00:00Z"}}]},
        "closedPullRequests": {
            "edges": [{"node": {"closedAt": "2024-01-04T00:00:00Z"}}],
            "totalCount": 1,
        },
        "mergedPullRequestsCount": {"totalCount": 3},
        "releases": {"edges": [{"node": {"publishedAt": "2024-01-05T00:00:00Z"}}]},
        "issues": {
            "edges": [{"node": {"createdAt": "2024-01-06T00:00:00Z"}}],
            "totalCount": 12,
        },
        "closedIssues": {
            "edges": [{"node": {"closedAt": "2024-01-07T00:00:00Z"}}],
            "totalCount": 4,
        },
        "vulnerabilityAlerts": {
            "edges": [{"node": {"securityVulnerability": {"severity": "HIGH"}}}]
        },
        "isSecurityPolicyEnabled": True,
        "codeOfConduct": {
            "name": "Contributor Covenant",
            "url": "https://example.com/coc",
        },
        "licenseInfo": {
            "name": "MIT",
            "spdxId": "MIT",
            "url": "https://example.com/license",
        },
        "hasWikiEnabled": True,
        "hasIssuesEnabled": True,
        "hasDiscussionsEnabled": False,
        "fundingLinks": [{"platform": "github", "url": "https://example.com/fund"}],
        "forks": {"edges": [{"node": {"createdAt": "2024-01-08T00:00:00Z"}}]},
        "forkCount": 2,
        "stargazerCount": 42,
        "watchers": {"totalCount": 7},
        "description": "Test repo",
        "homepageUrl": "https://example.com",
        "repositoryTopics": {"nodes": [{"topic": {"name": "python"}}]},
        "readmeUpperCase": {"byteSize": 123, "text": "README"},
        "contributingFile": {"byteSize": 456},
        "primaryLanguage": {"name": "Python"},
    }

    checker = DummyChecker()
    context = MetricContext(owner="octo", name="repo", repo_url="https://example.com")

    metric = checker.check_legacy(repo_info, context)

    assert metric.name == "Dummy"
    assert checker.last_vcs_data is not None
    assert checker.last_vcs_data.star_count == 42
    assert checker.last_vcs_data.watchers_count == 7
    assert checker.last_vcs_data.topics == ["python"]
    assert checker.last_vcs_data.readme_size == 123
    assert checker.last_vcs_data.contributing_file_size == 456
    assert checker.last_vcs_data.default_branch == "main"
    assert checker.last_vcs_data.open_issues_count == 12
    assert checker.last_vcs_data.language == "Python"
