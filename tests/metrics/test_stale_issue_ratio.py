"""
Tests for the stale_issue_ratio metric.
"""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.stale_issue_ratio import check_stale_issue_ratio


class TestStaleIssueRatioMetric:
    """Test the check_stale_issue_ratio metric function."""

    def test_stale_issue_ratio_no_issues(self):
        """Test when no closed issues are available."""
        repo_data = {"closedIssues": {"edges": []}}
        result = check_stale_issue_ratio(repo_data)
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

        repo_data = {
            "closedIssues": {
                "edges": [
                    {"node": {"updatedAt": recent_update.isoformat() + "Z"}},
                    {"node": {"updatedAt": recent_update.isoformat() + "Z"}},
                    {"node": {"updatedAt": recent_update.isoformat() + "Z"}},
                    {"node": {"updatedAt": recent_update.isoformat() + "Z"}},
                    {
                        "node": {"updatedAt": stale_update.isoformat() + "Z"}
                    },  # 1 stale out of 5 = 20%
                ]
            }
        }
        result = check_stale_issue_ratio(repo_data)
        assert result.name == "Stale Issue Ratio"
        assert result.score == 6
        assert result.max_score == 10
        assert "Acceptable: 20.0% of issues are stale" in result.message
        assert result.risk == "Low"

    def test_stale_issue_ratio_very_healthy(self):
        """Test with very healthy stale ratio (<15%)."""
        now = datetime.now()
        recent_update = now - timedelta(days=30)

        repo_data = {
            "closedIssues": {
                "edges": [
                    {"node": {"updatedAt": recent_update.isoformat() + "Z"}},
                    {"node": {"updatedAt": recent_update.isoformat() + "Z"}},
                    {"node": {"updatedAt": recent_update.isoformat() + "Z"}},
                    {"node": {"updatedAt": recent_update.isoformat() + "Z"}},
                    {"node": {"updatedAt": recent_update.isoformat() + "Z"}},
                ]
            }
        }
        result = check_stale_issue_ratio(repo_data)
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

        repo_data = {
            "closedIssues": {
                "edges": [
                    {"node": {"updatedAt": recent_update.isoformat() + "Z"}},
                    {"node": {"updatedAt": recent_update.isoformat() + "Z"}},
                    {"node": {"updatedAt": stale_update.isoformat() + "Z"}},
                ]
            }
        }
        result = check_stale_issue_ratio(repo_data)
        assert result.name == "Stale Issue Ratio"
        assert result.score == 4
        assert result.max_score == 10
        assert "Observe: 33.3% of issues are stale" in result.message
        assert result.risk == "Medium"

    def test_stale_issue_ratio_high(self):
        """Test with high stale ratio (>50%)."""
        now = datetime.now()
        stale_update = now - timedelta(days=100)

        repo_data = {
            "closedIssues": {
                "edges": [
                    {"node": {"updatedAt": stale_update.isoformat() + "Z"}},
                    {"node": {"updatedAt": stale_update.isoformat() + "Z"}},
                    {"node": {"updatedAt": stale_update.isoformat() + "Z"}},
                ]
            }
        }
        result = check_stale_issue_ratio(repo_data)
        assert result.name == "Stale Issue Ratio"
        assert result.score == 2
        assert result.max_score == 10
        assert "Significant: 100.0% of issues are stale" in result.message
        assert result.risk == "High"
