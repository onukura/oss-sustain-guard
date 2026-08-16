"""Tests for issue resolution duration metric."""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.base import MetricContext
from oss_sustain_guard.metrics.issue_resolution_duration import (
    METRIC,
    check_issue_resolution_duration,
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


def _vcs_with_resolution(stars: int, days: int) -> VCSRepositoryData:
    base_time = datetime(2024, 1, 1)
    return _vcs_data(
        star_count=stars,
        closed_issues=[
            {
                "createdAt": base_time.isoformat(),
                "closedAt": (base_time + timedelta(days=days)).isoformat(),
            }
        ],
    )


class TestIssueResolutionDuration:
    """Test issue resolution duration metric."""

    def test_no_closed_issues(self):
        """Test with no closed issues."""
        vcs_data = _vcs_data()
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 7
        assert result.max_score == 10
        assert "No closed issues" in result.message
        assert result.risk == "None"

    def test_small_project_fast_resolution(self):
        """Test small project with fast issue resolution."""
        base_time = datetime.now()
        vcs_data = _vcs_data(
            star_count=5000,
            closed_issues=[
                {
                    "createdAt": base_time.isoformat(),
                    "closedAt": (base_time + timedelta(days=3)).isoformat(),
                }
            ],
        )
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_small_project_good_resolution(self):
        """Test small project with good issue resolution."""
        base_time = datetime.now()
        vcs_data = _vcs_data(
            star_count=5000,
            closed_issues=[
                {
                    "createdAt": base_time.isoformat(),
                    "closedAt": (base_time + timedelta(days=14)).isoformat(),
                }
            ],
        )
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 7
        assert result.max_score == 10
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_small_project_moderate_resolution(self):
        """Test small project with moderate issue resolution."""
        base_time = datetime.now()
        vcs_data = _vcs_data(
            star_count=5000,
            closed_issues=[
                {
                    "createdAt": base_time.isoformat(),
                    "closedAt": (base_time + timedelta(days=60)).isoformat(),
                }
            ],
        )
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_large_project_fast_resolution(self):
        """Test large project with fast issue resolution."""
        base_time = datetime.now()
        vcs_data = _vcs_data(
            star_count=50000,
            closed_issues=[
                {
                    "createdAt": base_time.isoformat(),
                    "closedAt": (base_time + timedelta(days=14)).isoformat(),
                }
            ],
        )
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_large_project_acceptable_resolution(self):
        """Test large project with acceptable issue resolution."""
        base_time = datetime.now()
        vcs_data = _vcs_data(
            star_count=50000,
            closed_issues=[
                {
                    "createdAt": base_time.isoformat(),
                    "closedAt": (base_time + timedelta(days=200)).isoformat(),
                }
            ],
        )
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 3
        assert result.max_score == 10
        assert "Monitor" in result.message
        assert result.risk == "Medium"

    def test_very_large_project_fast_resolution(self):
        """Test very large project with fast issue resolution."""
        base_time = datetime.now()
        vcs_data = _vcs_data(
            star_count=150000,
            closed_issues=[
                {
                    "createdAt": base_time.isoformat(),
                    "closedAt": (base_time + timedelta(days=30)).isoformat(),
                }
            ],
        )
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_very_large_project_needs_attention(self):
        """Test very large project that needs attention."""
        base_time = datetime.now()
        vcs_data = _vcs_data(
            star_count=150000,
            closed_issues=[
                {
                    "createdAt": base_time.isoformat(),
                    "closedAt": (base_time + timedelta(days=800)).isoformat(),
                }
            ],
        )
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe" in result.message
        assert result.risk == "High"

    def test_invalid_issue_dates(self):
        """Test invalid issue timestamps handling."""
        vcs_data = _vcs_data(
            closed_issues=[
                {"createdAt": "invalid", "closedAt": "invalid"},
                {"createdAt": datetime.now().isoformat()},
            ]
        )
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 5
        assert "Unable to calculate issue resolution times" in result.message
        assert result.risk == "None"

    def test_very_large_project_good_resolution(self):
        """Test very large project with good resolution."""
        vcs_data = _vcs_with_resolution(150000, 100)
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 7
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_very_large_project_moderate_resolution(self):
        """Test very large project with moderate resolution."""
        vcs_data = _vcs_with_resolution(150000, 200)
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 5
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_very_large_project_monitor_resolution(self):
        """Test very large project with monitor resolution."""
        vcs_data = _vcs_with_resolution(150000, 500)
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 3
        assert "Monitor" in result.message
        assert result.risk == "Medium"

    def test_large_project_good_resolution(self):
        """Test large project with good issue resolution."""
        vcs_data = _vcs_with_resolution(50000, 60)
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 7
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_large_project_moderate_resolution(self):
        """Test large project with moderate issue resolution."""
        vcs_data = _vcs_with_resolution(50000, 120)
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 5
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_large_project_backlog_resolution(self):
        """Test large project with significant backlog."""
        vcs_data = _vcs_with_resolution(50000, 400)
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 0
        assert "Observe" in result.message
        assert result.risk == "High"

    def test_small_project_slow_resolution(self):
        """Test small project with slow issue resolution."""
        vcs_data = _vcs_with_resolution(5000, 120)
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 2
        assert "Needs attention" in result.message
        assert result.risk == "High"

    def test_small_project_backlog_resolution(self):
        """Test small project with significant backlog."""
        vcs_data = _vcs_with_resolution(5000, 200)
        result = check_issue_resolution_duration(vcs_data)
        assert result.score == 0
        assert "Observe" in result.message
        assert result.risk == "High"

    def test_issue_resolution_metric_spec_checker(self):
        """Test MetricSpec checker delegates to the metric function."""
        repo_data = _vcs_with_resolution(5000, 3)
        context = MetricContext(owner="owner", name="repo", repo_url="url")
        result = METRIC.checker.check(repo_data, context)
        assert result is not None
        assert result.name == "Issue Resolution Duration"

    def test_issue_resolution_metric_spec_on_error(self):
        """Test MetricSpec error handler formatting."""
        assert METRIC.on_error is not None
        result = METRIC.on_error(RuntimeError("boom"))
        assert result.score == 0
        assert "Analysis incomplete" in result.message
