"""
Tests for the stale_issue_ratio metric.
"""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.stale_issue_ratio import check_stale_issue_ratio
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


class TestStaleIssueRatioMetric:
    """Test the check_stale_issue_ratio metric function."""

    def test_stale_issue_ratio_no_issues(self):
        """Test when no closed issues are available."""
        vcs_data = _vcs_data(closed_issues=[])
        result = check_stale_issue_ratio(vcs_data)
        assert result.name == "Stale Issue Ratio"
        assert result.score == 5
        assert result.max_score == 10
        assert "No closed issues in recent history" in result.message
        assert result.risk == "None"

    def test_stale_issue_ratio_healthy(self):
        """Test with healthy stale ratio (<15%)."""
        now = datetime.now()
        recent_update = now - timedelta(days=30)
        stale_update = now - timedelta(days=100)

        closed_issues = [
            {"updatedAt": recent_update.isoformat() + "Z"},
            {"updatedAt": recent_update.isoformat() + "Z"},
            {"updatedAt": recent_update.isoformat() + "Z"},
            {"updatedAt": recent_update.isoformat() + "Z"},
            {"updatedAt": stale_update.isoformat() + "Z"},  # 1 stale out of 5 = 20%
        ]
        result = check_stale_issue_ratio(_vcs_data(closed_issues=closed_issues))
        assert result.name == "Stale Issue Ratio"
        assert result.score == 6
        assert result.max_score == 10
        assert "Acceptable: 20.0% of issues are stale" in result.message
        assert result.risk == "Low"

    def test_stale_issue_ratio_very_healthy(self):
        """Test with very healthy stale ratio (<15%)."""
        now = datetime.now()
        recent_update = now - timedelta(days=30)

        closed_issues = [
            {"updatedAt": recent_update.isoformat() + "Z"},
            {"updatedAt": recent_update.isoformat() + "Z"},
            {"updatedAt": recent_update.isoformat() + "Z"},
            {"updatedAt": recent_update.isoformat() + "Z"},
            {"updatedAt": recent_update.isoformat() + "Z"},
        ]
        result = check_stale_issue_ratio(_vcs_data(closed_issues=closed_issues))
        assert result.name == "Stale Issue Ratio"
        assert result.score == 10
        assert result.max_score == 10
        assert "Healthy: 0.0% of issues are stale" in result.message
        assert result.risk == "None"

    def test_stale_issue_ratio_medium(self):
        """Test with medium stale ratio (30-50%)."""
        now = datetime.now()
        recent_update = now - timedelta(days=30)
        stale_update = now - timedelta(days=100)

        closed_issues = [
            {"updatedAt": recent_update.isoformat() + "Z"},
            {"updatedAt": recent_update.isoformat() + "Z"},
            {"updatedAt": stale_update.isoformat() + "Z"},
        ]
        result = check_stale_issue_ratio(_vcs_data(closed_issues=closed_issues))
        assert result.name == "Stale Issue Ratio"
        assert result.score == 4
        assert result.max_score == 10
        assert "Observe: 33.3% of issues are stale" in result.message
        assert result.risk == "Medium"

    def test_stale_issue_ratio_high(self):
        """Test with high stale ratio (>50%)."""
        now = datetime.now()
        stale_update = now - timedelta(days=100)

        closed_issues = [
            {"updatedAt": stale_update.isoformat() + "Z"},
            {"updatedAt": stale_update.isoformat() + "Z"},
            {"updatedAt": stale_update.isoformat() + "Z"},
        ]
        result = check_stale_issue_ratio(_vcs_data(closed_issues=closed_issues))
        assert result.name == "Stale Issue Ratio"
        assert result.score == 2
        assert result.max_score == 10
        assert "Significant: 100.0% of issues are stale" in result.message
        assert result.risk == "High"
