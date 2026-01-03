"""
Tests for the zombie_status metric.
"""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.zombie_status import check_zombie_status
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


class TestZombieStatusMetric:
    """Test the check_zombie_status metric function."""

    def test_zombie_status_archived(self):
        """Test when repository is archived."""
        vcs_data = _vcs_data(is_archived=True)
        result = check_zombie_status(vcs_data)
        assert result.name == "Recent Activity"
        assert result.score == 5
        assert result.max_score == 10
        assert "Repository is archived" in result.message
        assert result.risk == "Medium"

    def test_zombie_status_no_pushed_at(self):
        """Test when pushedAt is not available."""
        vcs_data = _vcs_data()
        result = check_zombie_status(vcs_data)
        assert result.name == "Recent Activity"
        assert result.score == 0
        assert result.max_score == 10
        assert "Last activity data not available" in result.message
        assert result.risk == "High"

    def test_zombie_status_very_old(self):
        """Test with activity over 2 years ago."""
        old_date = datetime.now() - timedelta(days=800)
        vcs_data = _vcs_data(pushed_at=old_date.isoformat() + "Z")
        result = check_zombie_status(vcs_data)
        assert result.name == "Recent Activity"
        assert result.score == 0
        assert result.max_score == 10
        assert "No activity for" in result.message
        assert result.risk == "Critical"

    def test_zombie_status_old(self):
        """Test with activity over 1 year ago."""
        old_date = datetime.now() - timedelta(days=400)
        vcs_data = _vcs_data(pushed_at=old_date.isoformat() + "Z")
        result = check_zombie_status(vcs_data)
        assert result.name == "Recent Activity"
        assert result.score == 2
        assert result.max_score == 10
        assert "Last activity" in result.message
        assert result.risk == "High"

    def test_zombie_status_six_months(self):
        """Test with activity over 6 months ago."""
        moderate_date = datetime.now() - timedelta(days=200)
        vcs_data = _vcs_data(pushed_at=moderate_date.isoformat() + "Z")
        result = check_zombie_status(vcs_data)
        assert result.name == "Recent Activity"
        assert result.score == 5
        assert result.max_score == 10
        assert "Last activity" in result.message
        assert result.risk == "Medium"

    def test_zombie_status_three_months(self):
        """Test with activity over 3 months ago."""
        recent_date = datetime.now() - timedelta(days=100)
        vcs_data = _vcs_data(pushed_at=recent_date.isoformat() + "Z")
        result = check_zombie_status(vcs_data)
        assert result.name == "Recent Activity"
        assert result.score == 8
        assert result.max_score == 10
        assert "Last activity" in result.message
        assert result.risk == "Low"

    def test_zombie_status_recent(self):
        """Test with recent activity."""
        recent_date = datetime.now() - timedelta(days=30)
        vcs_data = _vcs_data(pushed_at=recent_date.isoformat() + "Z")
        result = check_zombie_status(vcs_data)
        assert result.name == "Recent Activity"
        assert result.score == 10
        assert result.max_score == 10
        assert "Recently active" in result.message
        assert result.risk == "None"
