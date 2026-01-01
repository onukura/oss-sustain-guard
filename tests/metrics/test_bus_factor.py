"""
Tests for the bus_factor metric.
"""

import oss_sustain_guard.metrics.bus_factor as bus_factor
from oss_sustain_guard.metrics.base import MetricContext
from oss_sustain_guard.metrics.bus_factor import METRIC, check_bus_factor


def _repo_with_commits(logins: list[str], total_count: int | None = None) -> dict:
    edges = [{"node": {"author": {"user": {"login": login}}}} for login in logins]
    history: dict[str, object] = {"edges": edges}
    if total_count is not None:
        history["totalCount"] = total_count
    return {"defaultBranchRef": {"target": {"history": history}}}


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

    def test_bus_factor_only_bots(self):
        """Test when only bot commits are present."""
        repo_data = _repo_with_commits(["dependabot[bot]", "github-actions"])
        result = check_bus_factor(repo_data)
        assert result.score == 0
        assert "No human contributors found" in result.message
        assert result.risk == "Critical"

    def test_bus_factor_mature_bdfl(self):
        """Test BDFL model detection for mature projects."""
        repo_data = _repo_with_commits(["founder"] * 10, total_count=1500)
        result = check_bus_factor(repo_data)
        assert result.score == 8
        assert "BDFL model" in result.message
        assert result.risk == "Low"

    def test_bus_factor_mature_high_concentration(self):
        """Test high concentration for mature but non-BDFL projects."""
        repo_data = _repo_with_commits(["user1"] * 9 + ["user2"], total_count=200)
        result = check_bus_factor(repo_data)
        assert result.score == 2
        assert "High: 90% of recent commits" in result.message
        assert result.risk == "High"

    def test_bus_factor_high_concentration(self):
        """Test high concentration without maturity threshold."""
        repo_data = _repo_with_commits(
            ["user1"] * 7 + ["user2"] * 2 + ["user3"], total_count=50
        )
        result = check_bus_factor(repo_data)
        assert result.score == 5
        assert "High: 70% of commits" in result.message
        assert result.risk == "High"

    def test_bus_factor_medium_concentration(self):
        """Test medium concentration without maturity threshold."""
        repo_data = _repo_with_commits(["user1"] * 6 + ["user2"] * 4, total_count=80)
        result = check_bus_factor(repo_data)
        assert result.score == 8
        assert "Medium: 60% by top contributor" in result.message
        assert result.risk == "Medium"

    def test_bus_factor_total_commits_zero(self, monkeypatch):
        """Test handling of zero total commits after filtering."""
        repo_data = _repo_with_commits(["user1"])
        monkeypatch.setattr(bus_factor, "sum", lambda values: 0, raising=False)
        result = check_bus_factor(repo_data)
        assert result.score == 0
        assert "No commits found" in result.message
        assert result.risk == "Critical"

    def test_bus_factor_metric_spec_checker(self):
        """Test MetricSpec checker delegates to the metric function."""
        repo_data = _repo_with_commits(["user1", "user2"])
        context = MetricContext(owner="owner", name="repo", repo_url="url")
        result = METRIC.checker(repo_data, context)
        assert result.name == "Contributor Redundancy"

    def test_bus_factor_metric_spec_on_error(self):
        """Test MetricSpec error handler formatting."""
        result = METRIC.on_error(RuntimeError("boom"))
        assert result.score == 0
        assert "Analysis incomplete" in result.message
