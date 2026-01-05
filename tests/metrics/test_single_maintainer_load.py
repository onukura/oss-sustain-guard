"""
Tests for the single_maintainer_load metric.
"""

from oss_sustain_guard.metrics.base import MetricContext
from oss_sustain_guard.metrics.single_maintainer_load import (
    METRIC,
    check_single_maintainer_load,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData


def _vcs_data(**overrides) -> VCSRepositoryData:
    data = VCSRepositoryData(
        is_archived=False,
        pushed_at=None,
        owner_type="User",
        owner_login="owner",
        owner_name=None,
        star_count=0,
        description=None,
        homepage_url=None,
        topics=[],
        readme_size=None,
        contributing_file_size=None,
        default_branch="main",
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
        raw_data=None,
    )
    return data._replace(**overrides)


class TestSingleMaintainerLoadMetric:
    """Test the check_single_maintainer_load metric function."""

    def test_single_maintainer_load_no_activity(self):
        """Test when no closing activity is available."""
        vcs_data = _vcs_data(merged_prs=[], raw_data={"closedIssues": {"edges": []}})
        result = check_single_maintainer_load(vcs_data)
        assert result.name == "Maintainer Load Distribution"
        assert result.score == 5
        assert result.max_score == 10
        assert "No Issue/PR closing activity to analyze" in result.message
        assert result.risk == "None"

    def test_single_maintainer_load_healthy_distribution(self):
        """Test with healthy workload distribution (Gini < 0.3)."""
        merged_prs = [
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user2"}},
            {"mergedBy": {"login": "user3"}},
            {"mergedBy": {"login": "user4"}},
            {"mergedBy": {"login": "user5"}},
        ]
        result = check_single_maintainer_load(_vcs_data(merged_prs=merged_prs))
        assert result.name == "Maintainer Load Distribution"
        assert result.score == 10
        assert result.max_score == 10
        assert "Healthy: Workload well distributed" in result.message
        assert result.risk == "None"

    def test_single_maintainer_load_moderate_distribution(self):
        """Test with moderate workload distribution (Gini 0.3-0.5)."""
        merged_prs = [
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user2"}},
            {"mergedBy": {"login": "user3"}},
        ]
        result = check_single_maintainer_load(_vcs_data(merged_prs=merged_prs))
        assert result.name == "Maintainer Load Distribution"
        assert result.score == 10
        assert result.max_score == 10
        assert "Healthy: Workload well distributed" in result.message
        assert result.risk == "None"

    def test_single_maintainer_load_high_concentration(self):
        """Test with high workload concentration (Gini 0.5-0.7)."""
        merged_prs = [
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user2"}},
        ]
        result = check_single_maintainer_load(_vcs_data(merged_prs=merged_prs))
        assert result.name == "Maintainer Load Distribution"
        assert result.score == 10
        assert result.max_score == 10
        assert "Healthy: Workload well distributed" in result.message
        assert result.risk == "None"

    def test_single_maintainer_load_very_high_concentration(self):
        """Test with very high workload concentration (Gini > 0.7)."""
        merged_prs = [
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user1"}},
        ]
        result = check_single_maintainer_load(_vcs_data(merged_prs=merged_prs))
        assert result.name == "Maintainer Load Distribution"
        assert result.score == 2
        assert result.max_score == 10
        assert "Needs support: Very high workload concentration" in result.message
        assert result.risk == "High"

    def test_single_maintainer_load_issue_closers(self):
        """Test workload distribution with issue timeline closers."""
        raw_data = {
            "closedIssues": {
                "edges": [
                    {
                        "node": {
                            "timelineItems": {
                                "edges": [
                                    {"node": {"actor": {"login": "user1"}}},
                                    {"node": {"actor": {"login": "user2"}}},
                                ]
                            }
                        }
                    }
                ]
            }
        }
        result = check_single_maintainer_load(
            _vcs_data(merged_prs=[], raw_data=raw_data)
        )
        assert result.score == 2
        assert "Needs support: Very high workload concentration" in result.message
        assert result.risk == "High"

    def test_single_maintainer_load_closed_by(self):
        """Test workload distribution using closedBy data."""
        closed_issues = [
            {"closedBy": {"login": "user1"}},
            {"closedBy": {"login": "user2"}},
        ]
        result = check_single_maintainer_load(
            _vcs_data(merged_prs=[], closed_issues=closed_issues)
        )
        assert result.score == 10
        assert "Healthy: Workload well distributed" in result.message
        assert result.risk == "None"

    def test_single_maintainer_load_moderate_gini(self):
        """Test with moderate workload concentration (Gini 0.3-0.5)."""
        merged_prs = [
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user1"}},
            {"mergedBy": {"login": "user2"}},
        ]
        result = check_single_maintainer_load(_vcs_data(merged_prs=merged_prs))
        assert result.score == 6
        assert "Moderate: Some workload concentration" in result.message
        assert result.risk == "Low"

    def test_single_maintainer_load_high_gini(self):
        """Test with high workload concentration (Gini 0.5-0.7)."""
        merged_prs = [{"mergedBy": {"login": "user1"}}] * 20 + [
            {"mergedBy": {"login": "user2"}},
            {"mergedBy": {"login": "user3"}},
        ]
        result = check_single_maintainer_load(_vcs_data(merged_prs=merged_prs))
        assert result.score == 4
        assert "Observe: High workload concentration" in result.message
        assert result.risk == "Medium"

    def test_single_maintainer_load_metric_spec_checker(self):
        """Test MetricSpec checker delegates to the metric function."""
        repo_data = _vcs_data(merged_prs=[], raw_data={"closedIssues": {"edges": []}})
        context = MetricContext(owner="owner", name="repo", repo_url="url")
        result = METRIC.checker.check(repo_data, context)
        assert result is not None
        assert result.name == "Maintainer Load Distribution"

    def test_single_maintainer_load_metric_spec_on_error(self):
        """Test MetricSpec error handler formatting."""
        assert METRIC.on_error is not None
        result = METRIC.on_error(RuntimeError("boom"))
        assert result.score == 0
        assert "Analysis incomplete" in result.message
