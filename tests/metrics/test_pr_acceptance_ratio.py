"""Tests for PR acceptance ratio metric."""

from oss_sustain_guard.metrics.pr_acceptance_ratio import check_pr_acceptance_ratio


class TestPrAcceptanceRatio:
    """Test PR acceptance ratio metric."""

    def test_no_resolved_prs(self):
        """Test with no resolved PRs."""
        repo_data = {
            "mergedPullRequestsCount": {"totalCount": 0},
            "closedPullRequests": {"edges": []},
        }
        result = check_pr_acceptance_ratio(repo_data)
        assert result.score == 5
        assert result.max_score == 10
        assert "No resolved pull requests" in result.message
        assert result.risk == "None"

    def test_very_welcoming(self):
        """Test very welcoming acceptance rate."""
        repo_data = {
            "mergedPullRequestsCount": {"totalCount": 80},
            "closedPullRequests": {
                "edges": [{"node": {"merged": True}} for _ in range(80)]
                + [{"node": {"merged": False}} for _ in range(20)]
            },
        }
        result = check_pr_acceptance_ratio(repo_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_good_acceptance(self):
        """Test good acceptance rate."""
        repo_data = {
            "mergedPullRequestsCount": {"totalCount": 70},
            "closedPullRequests": {
                "edges": [{"node": {"merged": True}} for _ in range(70)]
                + [{"node": {"merged": False}} for _ in range(30)]
            },
        }
        result = check_pr_acceptance_ratio(repo_data)
        assert result.score == 7
        assert result.max_score == 10
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_moderate_acceptance(self):
        """Test moderate acceptance rate."""
        repo_data = {
            "mergedPullRequestsCount": {"totalCount": 50},
            "closedPullRequests": {
                "edges": [{"node": {"merged": True}} for _ in range(50)]
                + [{"node": {"merged": False}} for _ in range(50)]
            },
        }
        result = check_pr_acceptance_ratio(repo_data)
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_needs_attention(self):
        """Test low acceptance rate that needs attention."""
        repo_data = {
            "mergedPullRequestsCount": {"totalCount": 30},
            "closedPullRequests": {
                "edges": [{"node": {"merged": True}} for _ in range(30)]
                + [{"node": {"merged": False}} for _ in range(70)]
            },
        }
        result = check_pr_acceptance_ratio(repo_data)
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe" in result.message
        assert result.risk == "Medium"
