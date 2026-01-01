"""
Tests for the single_maintainer_load metric.
"""

from oss_sustain_guard.metrics.single_maintainer_load import (
    check_single_maintainer_load,
)


class TestSingleMaintainerLoadMetric:
    """Test the check_single_maintainer_load metric function."""

    def test_single_maintainer_load_no_activity(self):
        """Test when no closing activity is available."""
        repo_data = {"pullRequests": {"edges": []}, "closedIssues": {"edges": []}}
        result = check_single_maintainer_load(repo_data)
        assert result.name == "Maintainer Load Distribution"
        assert result.score == 5
        assert result.max_score == 10
        assert "No Issue/PR closing activity to analyze" in result.message
        assert result.risk == "None"

    def test_single_maintainer_load_healthy_distribution(self):
        """Test with healthy workload distribution (Gini < 0.3)."""
        repo_data = {
            "pullRequests": {
                "edges": [
                    {"node": {"mergedBy": {"login": "user1"}}},
                    {"node": {"mergedBy": {"login": "user2"}}},
                    {"node": {"mergedBy": {"login": "user3"}}},
                    {"node": {"mergedBy": {"login": "user4"}}},
                    {"node": {"mergedBy": {"login": "user5"}}},
                ]
            },
            "closedIssues": {"edges": []},
        }
        result = check_single_maintainer_load(repo_data)
        assert result.name == "Maintainer Load Distribution"
        assert result.score == 10
        assert result.max_score == 10
        assert "Healthy: Workload well distributed" in result.message
        assert result.risk == "None"

    def test_single_maintainer_load_moderate_distribution(self):
        """Test with moderate workload distribution (Gini 0.3-0.5)."""
        repo_data = {
            "pullRequests": {
                "edges": [
                    {"node": {"mergedBy": {"login": "user1"}}},
                    {"node": {"mergedBy": {"login": "user1"}}},
                    {"node": {"mergedBy": {"login": "user2"}}},
                    {"node": {"mergedBy": {"login": "user3"}}},
                ]
            },
            "closedIssues": {"edges": []},
        }
        result = check_single_maintainer_load(repo_data)
        assert result.name == "Maintainer Load Distribution"
        assert result.score == 10
        assert result.max_score == 10
        assert "Healthy: Workload well distributed" in result.message
        assert result.risk == "None"

    def test_single_maintainer_load_high_concentration(self):
        """Test with high workload concentration (Gini 0.5-0.7)."""
        repo_data = {
            "pullRequests": {
                "edges": [
                    {"node": {"mergedBy": {"login": "user1"}}},
                    {"node": {"mergedBy": {"login": "user1"}}},
                    {"node": {"mergedBy": {"login": "user1"}}},
                    {"node": {"mergedBy": {"login": "user2"}}},
                ]
            },
            "closedIssues": {"edges": []},
        }
        result = check_single_maintainer_load(repo_data)
        assert result.name == "Maintainer Load Distribution"
        assert result.score == 10
        assert result.max_score == 10
        assert "Healthy: Workload well distributed" in result.message
        assert result.risk == "None"

    def test_single_maintainer_load_very_high_concentration(self):
        """Test with very high workload concentration (Gini > 0.7)."""
        repo_data = {
            "pullRequests": {
                "edges": [
                    {"node": {"mergedBy": {"login": "user1"}}},
                    {"node": {"mergedBy": {"login": "user1"}}},
                    {"node": {"mergedBy": {"login": "user1"}}},
                    {"node": {"mergedBy": {"login": "user1"}}},
                    {"node": {"mergedBy": {"login": "user1"}}},
                ]
            },
            "closedIssues": {"edges": []},
        }
        result = check_single_maintainer_load(repo_data)
        assert result.name == "Maintainer Load Distribution"
        assert result.score == 2
        assert result.max_score == 10
        assert "Needs support: Very high workload concentration" in result.message
        assert result.risk == "High"
