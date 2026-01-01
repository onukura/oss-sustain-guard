"""
Tests for the zombie_status metric.
"""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.zombie_status import check_zombie_status


class TestZombieStatusMetric:
    """Test the check_zombie_status metric function."""

    def test_zombie_status_archived(self):
        """Test when repository is archived."""
        repo_data = {"isArchived": True}
        result = check_zombie_status(repo_data)
        assert result.name == "Recent Activity"
        assert result.score == 5
        assert result.max_score == 10
        assert "Repository is archived" in result.message
        assert result.risk == "Medium"

    def test_zombie_status_no_pushed_at(self):
        """Test when pushedAt is not available."""
        repo_data = {}
        result = check_zombie_status(repo_data)
        assert result.name == "Recent Activity"
        assert result.score == 0
        assert result.max_score == 10
        assert "Last activity data not available" in result.message
        assert result.risk == "High"

    def test_zombie_status_very_old(self):
        """Test with activity over 2 years ago."""
        old_date = datetime.now() - timedelta(days=800)
        repo_data = {"pushedAt": old_date.isoformat() + "Z"}
        result = check_zombie_status(repo_data)
        assert result.name == "Recent Activity"
        assert result.score == 0
        assert result.max_score == 10
        assert "No activity for" in result.message
        assert result.risk == "Critical"

    def test_zombie_status_old(self):
        """Test with activity over 1 year ago."""
        old_date = datetime.now() - timedelta(days=400)
        repo_data = {"pushedAt": old_date.isoformat() + "Z"}
        result = check_zombie_status(repo_data)
        assert result.name == "Recent Activity"
        assert result.score == 2
        assert result.max_score == 10
        assert "Last activity" in result.message
        assert result.risk == "High"

    def test_zombie_status_six_months(self):
        """Test with activity over 6 months ago."""
        moderate_date = datetime.now() - timedelta(days=200)
        repo_data = {"pushedAt": moderate_date.isoformat() + "Z"}
        result = check_zombie_status(repo_data)
        assert result.name == "Recent Activity"
        assert result.score == 5
        assert result.max_score == 10
        assert "Last activity" in result.message
        assert result.risk == "Medium"

    def test_zombie_status_three_months(self):
        """Test with activity over 3 months ago."""
        recent_date = datetime.now() - timedelta(days=100)
        repo_data = {"pushedAt": recent_date.isoformat() + "Z"}
        result = check_zombie_status(repo_data)
        assert result.name == "Recent Activity"
        assert result.score == 8
        assert result.max_score == 10
        assert "Last activity" in result.message
        assert result.risk == "Low"

    def test_zombie_status_recent(self):
        """Test with recent activity."""
        recent_date = datetime.now() - timedelta(days=30)
        repo_data = {"pushedAt": recent_date.isoformat() + "Z"}
        result = check_zombie_status(repo_data)
        assert result.name == "Recent Activity"
        assert result.score == 10
        assert result.max_score == 10
        assert "Recently active" in result.message
        assert result.risk == "None"
