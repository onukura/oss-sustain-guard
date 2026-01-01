"""Tests for PR merge speed metric."""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.pr_merge_speed import check_pr_merge_speed


class TestPrMergeSpeed:
    """Test PR merge speed metric."""

    def test_no_merged_prs(self):
        """Test with no merged PRs."""
        repo_data = {"pullRequests": {"edges": []}}
        result = check_pr_merge_speed(repo_data)
        assert result.score == 5
        assert result.max_score == 10
        assert "No merged PRs available" in result.message
        assert result.risk == "None"

    def test_excellent_merge_speed(self):
        """Test excellent merge speed (<3 days)."""
        base_time = datetime.now()
        repo_data = {
            "pullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "mergedAt": (base_time + timedelta(days=1)).isoformat(),
                        }
                    },
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "mergedAt": (base_time + timedelta(days=2)).isoformat(),
                        }
                    },
                ]
            }
        }
        result = check_pr_merge_speed(repo_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_good_merge_speed(self):
        """Test good merge speed (3-7 days)."""
        base_time = datetime.now()
        repo_data = {
            "pullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "mergedAt": (base_time + timedelta(days=4)).isoformat(),
                        }
                    },
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "mergedAt": (base_time + timedelta(days=5)).isoformat(),
                        }
                    },
                ]
            }
        }
        result = check_pr_merge_speed(repo_data)
        assert result.score == 8
        assert result.max_score == 10
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_moderate_merge_speed(self):
        """Test moderate merge speed (7-30 days)."""
        base_time = datetime.now()
        repo_data = {
            "pullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "mergedAt": (base_time + timedelta(days=14)).isoformat(),
                        }
                    },
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "mergedAt": (base_time + timedelta(days=16)).isoformat(),
                        }
                    },
                ]
            }
        }
        result = check_pr_merge_speed(repo_data)
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_slow_merge_speed(self):
        """Test slow merge speed (>30 days)."""
        base_time = datetime.now()
        repo_data = {
            "pullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "mergedAt": (base_time + timedelta(days=45)).isoformat(),
                        }
                    },
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "mergedAt": (base_time + timedelta(days=50)).isoformat(),
                        }
                    },
                ]
            }
        }
        result = check_pr_merge_speed(repo_data)
        assert result.score == 2
        assert result.max_score == 10
        assert "Observe" in result.message
        assert result.risk == "High"
