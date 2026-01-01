"""
Tests for the pr_responsiveness metric.
"""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.pr_responsiveness import check_pr_responsiveness


class TestPrResponsivenessMetric:
    """Test the check_pr_responsiveness metric function."""

    def test_pr_responsiveness_no_closed_prs(self):
        """Test when no closed PRs are available."""
        repo_data = {"closedPullRequests": {"edges": []}}
        result = check_pr_responsiveness(repo_data)
        assert result.name == "PR Responsiveness"
        assert result.score == 5
        assert result.max_score == 10
        assert "No closed PRs to analyze responsiveness" in result.message
        assert result.risk == "None"

    def test_pr_responsiveness_no_response_times(self):
        """Test when PRs exist but no response times can be measured."""
        created_at = datetime.now()
        repo_data = {
            "closedPullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": created_at.isoformat() + "Z",
                            "reviews": {"edges": []},
                        }
                    }
                ]
            }
        }
        result = check_pr_responsiveness(repo_data)
        assert result.name == "PR Responsiveness"
        assert result.score == 2
        assert result.max_score == 10
        assert "Unable to measure PR response times" in result.message
        assert result.risk == "None"

    def test_pr_responsiveness_excellent(self):
        """Test with excellent responsiveness (<24h)."""
        created_at = datetime.now()
        response_at = created_at + timedelta(hours=12)
        repo_data = {
            "closedPullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": created_at.isoformat() + "Z",
                            "reviews": {
                                "edges": [
                                    {
                                        "node": {
                                            "createdAt": response_at.isoformat() + "Z"
                                        }
                                    }
                                ]
                            },
                        }
                    }
                ]
            }
        }
        result = check_pr_responsiveness(repo_data)
        assert result.name == "PR Responsiveness"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: Avg PR first response 12.0h" in result.message
        assert result.risk == "None"

    def test_pr_responsiveness_good(self):
        """Test with good responsiveness (<7d)."""
        created_at = datetime.now()
        response_at = created_at + timedelta(days=3)
        repo_data = {
            "closedPullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": created_at.isoformat() + "Z",
                            "reviews": {
                                "edges": [
                                    {
                                        "node": {
                                            "createdAt": response_at.isoformat() + "Z"
                                        }
                                    }
                                ]
                            },
                        }
                    }
                ]
            }
        }
        result = check_pr_responsiveness(repo_data)
        assert result.name == "PR Responsiveness"
        assert result.score == 6
        assert result.max_score == 10
        assert "Good: Avg PR first response 3.0d" in result.message
        assert result.risk == "Low"

    def test_pr_responsiveness_poor(self):
        """Test with poor responsiveness (>7d)."""
        created_at = datetime.now()
        response_at = created_at + timedelta(days=10)
        repo_data = {
            "closedPullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": created_at.isoformat() + "Z",
                            "reviews": {
                                "edges": [
                                    {
                                        "node": {
                                            "createdAt": response_at.isoformat() + "Z"
                                        }
                                    }
                                ]
                            },
                        }
                    }
                ]
            }
        }
        result = check_pr_responsiveness(repo_data)
        assert result.name == "PR Responsiveness"
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe: Avg PR first response 10.0d" in result.message
        assert result.risk == "Medium"
