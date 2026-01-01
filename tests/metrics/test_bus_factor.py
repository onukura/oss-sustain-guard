"""
Tests for the bus_factor metric.
"""

from oss_sustain_guard.metrics.bus_factor import check_bus_factor


class TestBusFactorMetric:
    """Test the check_bus_factor metric function."""

    def test_bus_factor_no_default_branch(self):
        """Test when default branch is not available."""
        repo_data = {}
        result = check_bus_factor(repo_data)
        assert result.name == "Contributor Redundancy"
        assert result.score == 0
        assert result.max_score == 10
        assert "Commit history data not available" in result.message
        assert result.risk == "High"

    def test_bus_factor_no_target(self):
        """Test when default branch has no target."""
        repo_data = {"defaultBranchRef": {}}
        result = check_bus_factor(repo_data)
        assert result.name == "Contributor Redundancy"
        assert result.score == 0
        assert result.max_score == 10
        assert "Commit history data not available" in result.message
        assert result.risk == "High"

    def test_bus_factor_no_history(self):
        """Test when no commit history is available."""
        repo_data = {"defaultBranchRef": {"target": {"history": {"edges": []}}}}
        result = check_bus_factor(repo_data)
        assert result.name == "Contributor Redundancy"
        assert result.score == 0
        assert result.max_score == 10
        assert "No commit history available for analysis" in result.message
        assert result.risk == "Critical"

    def test_bus_factor_single_contributor_high_percentage(self):
        """Test with single contributor having high percentage."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {"node": {"author": {"user": {"login": "user1"}}}},
                            {"node": {"author": {"user": {"login": "user1"}}}},
                            {"node": {"author": {"user": {"login": "user1"}}}},
                            {"node": {"author": {"user": {"login": "user1"}}}},
                            {"node": {"author": {"user": {"login": "user1"}}}},
                        ]
                    }
                }
            }
        }
        result = check_bus_factor(repo_data)
        assert result.name == "Contributor Redundancy"
        assert result.score == 5  # New project: 100% by single author
        assert result.max_score == 10
        assert "New project: 100% by single author" in result.message
        assert result.risk == "Medium"

    def test_bus_factor_healthy_diversity(self):
        """Test with healthy contributor diversity."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {"node": {"author": {"user": {"login": "user1"}}}},
                            {"node": {"author": {"user": {"login": "user2"}}}},
                            {"node": {"author": {"user": {"login": "user3"}}}},
                            {"node": {"author": {"user": {"login": "user4"}}}},
                            {"node": {"author": {"user": {"login": "user5"}}}},
                        ]
                    }
                }
            }
        }
        result = check_bus_factor(repo_data)
        assert result.name == "Contributor Redundancy"
        assert result.score == 10
        assert result.max_score == 10
        assert "Healthy: 5 active contributors" in result.message
        assert result.risk == "None"
