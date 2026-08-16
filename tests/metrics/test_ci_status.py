"""
Tests for the ci_status metric.
"""

from oss_sustain_guard.metrics.base import MetricContext
from oss_sustain_guard.metrics.ci_status import METRIC, check_ci_status
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


class TestCiStatusMetric:
    """Test the check_ci_status metric function."""

    def test_ci_status_archived_repository(self):
        """Test when repository is archived."""
        vcs_data = _vcs_data(is_archived=True)
        result = check_ci_status(vcs_data)
        assert result.name == "Build Health"
        assert result.score == 10
        assert result.max_score == 10
        assert "Repository archived" in result.message
        assert result.risk == "None"

    def test_ci_status_skipped_without_data(self):
        """Test that CI status is skipped when no CI data is available."""
        vcs_data = _vcs_data()
        result = check_ci_status(vcs_data)
        assert result is not None
        assert result.name == "Build Health"
        assert result.score == 0
        assert "CI status data not available" in result.message

    def test_ci_status_no_default_branch(self):
        """Test when default branch is not available."""
        vcs_data = _vcs_data(default_branch=None, raw_data={})
        result = check_ci_status(vcs_data)
        assert result.name == "Build Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "CI status data not available" in result.message
        assert result.risk == "High"

    def test_ci_status_no_target(self):
        """Test when default branch has no target."""
        vcs_data = _vcs_data(raw_data={"defaultBranchRef": {}})
        result = check_ci_status(vcs_data)
        assert result.name == "Build Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "CI status data not available" in result.message
        assert result.risk == "High"

    def test_ci_status_no_check_suites(self):
        """Test when no checkSuites data."""
        vcs_data = _vcs_data(raw_data={"defaultBranchRef": {"target": {}}})
        result = check_ci_status(vcs_data)
        assert result.name == "Build Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "No CI configuration detected" in result.message
        assert result.risk == "High"

    def test_ci_status_empty_check_suites(self):
        """Test when checkSuites is empty."""
        vcs_data = _vcs_data(
            raw_data={"defaultBranchRef": {"target": {"checkSuites": {"nodes": []}}}}
        )
        result = check_ci_status(vcs_data)
        assert result.name == "Build Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "No recent CI checks" in result.message
        assert result.risk == "High"

    def test_ci_status_success(self):
        """Test when CI status is SUCCESS."""
        vcs_data = _vcs_data(ci_status={"conclusion": "SUCCESS", "status": "COMPLETED"})
        result = check_ci_status(vcs_data)
        assert result.name == "Build Health"
        assert result.score == 10
        assert result.max_score == 10
        assert "success" in result.message
        assert result.risk == "None"

    def test_ci_status_failure(self):
        """Test when CI status is FAILURE."""
        vcs_data = _vcs_data(ci_status={"conclusion": "FAILURE", "status": "COMPLETED"})
        result = check_ci_status(vcs_data)
        assert result.name == "Build Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "failure" in result.message
        assert result.risk == "Medium"

    def test_ci_status_in_progress(self):
        """Test when CI status is IN_PROGRESS."""
        vcs_data = _vcs_data(ci_status={"conclusion": None, "status": "IN_PROGRESS"})
        result = check_ci_status(vcs_data)
        assert result.name == "Build Health"
        assert result.score == 6
        assert result.max_score == 10
        assert "Tests in progress" in result.message
        assert result.risk == "Low"

    def test_ci_status_queued(self):
        """Test when CI status is QUEUED."""
        vcs_data = _vcs_data(ci_status={"conclusion": None, "status": "QUEUED"})
        result = check_ci_status(vcs_data)
        assert result.name == "Build Health"
        assert result.score == 6
        assert result.max_score == 10
        assert "Tests queued" in result.message
        assert result.risk == "Low"

    def test_ci_status_skipped(self):
        """Test when CI status is SKIPPED."""
        vcs_data = _vcs_data(ci_status={"conclusion": "SKIPPED", "status": "COMPLETED"})
        result = check_ci_status(vcs_data)
        assert result.name == "Build Health"
        assert result.score == 6
        assert result.max_score == 10
        assert "skipped" in result.message
        assert result.risk == "Low"

    def test_ci_status_latest_suite_not_dict(self):
        """Test when latest check suite is not a dict."""
        vcs_data = _vcs_data(
            raw_data={
                "defaultBranchRef": {"target": {"checkSuites": {"nodes": ["oops"]}}}
            }
        )
        result = check_ci_status(vcs_data)
        assert result.score == 0
        assert "No recent CI checks" in result.message
        assert result.risk == "High"

    def test_ci_status_non_string_values(self):
        """Test when conclusion and status are not strings."""
        vcs_data = _vcs_data(ci_status={"conclusion": 123, "status": 456})
        result = check_ci_status(vcs_data)
        assert result.score == 6
        assert "Configured" in result.message
        assert result.risk == "Low"

    def test_ci_status_unknown_conclusion(self):
        """Test when CI status is unknown."""
        vcs_data = _vcs_data(ci_status={"conclusion": "WEIRD", "status": "COMPLETED"})
        result = check_ci_status(vcs_data)
        assert result.score == 4
        assert "Unknown" in result.message
        assert result.risk == "Low"

    def test_ci_status_metric_spec_checker(self):
        """Test MetricSpec checker delegates to the metric function."""
        repo_data = _vcs_data(is_archived=True)
        context = MetricContext(owner="owner", name="repo", repo_url="url")
        result = METRIC.checker.check(repo_data, context)
        assert result is not None
        assert result.name == "Build Health"

    def test_ci_status_metric_spec_on_error(self):
        """Test MetricSpec error handler formatting."""
        if METRIC.on_error is not None:
            result = METRIC.on_error(RuntimeError("boom"))
            assert result.score == 0
            assert "Analysis incomplete" in result.message
