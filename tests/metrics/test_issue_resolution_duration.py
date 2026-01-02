"""Tests for issue resolution duration metric."""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.base import MetricContext
from oss_sustain_guard.metrics.issue_resolution_duration import (
    METRIC,
    check_issue_resolution_duration,
)


def _repo_with_resolution(stars: int, days: int) -> dict:
    base_time = datetime(2024, 1, 1)
    return {
        "stargazerCount": stars,
        "closedIssues": {
            "edges": [
                {
                    "node": {
                        "createdAt": base_time.isoformat(),
                        "closedAt": (base_time + timedelta(days=days)).isoformat(),
                    }
                }
            ]
        },
    }


class TestIssueResolutionDuration:
    """Test issue resolution duration metric."""

    def test_no_closed_issues(self):
        """Test with no closed issues."""
        repo_data = {"closedIssues": {"edges": []}}
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 7
        assert result.max_score == 10
        assert "No closed issues" in result.message
        assert result.risk == "None"

    def test_small_project_fast_resolution(self):
        """Test small project with fast issue resolution."""
        base_time = datetime.now()
        repo_data = {
            "stargazerCount": 5000,
            "closedIssues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "closedAt": (base_time + timedelta(days=3)).isoformat(),
                        }
                    }
                ]
            },
        }
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_small_project_good_resolution(self):
        """Test small project with good issue resolution."""
        base_time = datetime.now()
        repo_data = {
            "stargazerCount": 5000,
            "closedIssues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "closedAt": (base_time + timedelta(days=14)).isoformat(),
                        }
                    }
                ]
            },
        }
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 7
        assert result.max_score == 10
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_small_project_moderate_resolution(self):
        """Test small project with moderate issue resolution."""
        base_time = datetime.now()
        repo_data = {
            "stargazerCount": 5000,
            "closedIssues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "closedAt": (base_time + timedelta(days=60)).isoformat(),
                        }
                    }
                ]
            },
        }
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_large_project_fast_resolution(self):
        """Test large project with fast issue resolution."""
        base_time = datetime.now()
        repo_data = {
            "stargazerCount": 50000,
            "closedIssues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "closedAt": (base_time + timedelta(days=14)).isoformat(),
                        }
                    }
                ]
            },
        }
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_large_project_acceptable_resolution(self):
        """Test large project with acceptable issue resolution."""
        base_time = datetime.now()
        repo_data = {
            "stargazerCount": 50000,
            "closedIssues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "closedAt": (base_time + timedelta(days=200)).isoformat(),
                        }
                    }
                ]
            },
        }
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 3
        assert result.max_score == 10
        assert "Monitor" in result.message
        assert result.risk == "Medium"

    def test_very_large_project_fast_resolution(self):
        """Test very large project with fast issue resolution."""
        base_time = datetime.now()
        repo_data = {
            "stargazerCount": 150000,
            "closedIssues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "closedAt": (base_time + timedelta(days=30)).isoformat(),
                        }
                    }
                ]
            },
        }
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_very_large_project_needs_attention(self):
        """Test very large project that needs attention."""
        base_time = datetime.now()
        repo_data = {
            "stargazerCount": 150000,
            "closedIssues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "closedAt": (base_time + timedelta(days=800)).isoformat(),
                        }
                    }
                ]
            },
        }
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe" in result.message
        assert result.risk == "High"

    def test_invalid_issue_dates(self):
        """Test invalid issue timestamps handling."""
        repo_data = {
            "closedIssues": {
                "edges": [
                    {"node": {"createdAt": "invalid", "closedAt": "invalid"}},
                    {"node": {"createdAt": datetime.now().isoformat()}},
                ]
            }
        }
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 5
        assert "Unable to calculate issue resolution times" in result.message
        assert result.risk == "None"

    def test_very_large_project_good_resolution(self):
        """Test very large project with good resolution."""
        repo_data = _repo_with_resolution(150000, 100)
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 7
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_very_large_project_moderate_resolution(self):
        """Test very large project with moderate resolution."""
        repo_data = _repo_with_resolution(150000, 200)
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 5
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_very_large_project_monitor_resolution(self):
        """Test very large project with monitor resolution."""
        repo_data = _repo_with_resolution(150000, 500)
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 3
        assert "Monitor" in result.message
        assert result.risk == "Medium"

    def test_large_project_good_resolution(self):
        """Test large project with good issue resolution."""
        repo_data = _repo_with_resolution(50000, 60)
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 7
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_large_project_moderate_resolution(self):
        """Test large project with moderate issue resolution."""
        repo_data = _repo_with_resolution(50000, 120)
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 5
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_large_project_backlog_resolution(self):
        """Test large project with significant backlog."""
        repo_data = _repo_with_resolution(50000, 400)
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 0
        assert "Observe" in result.message
        assert result.risk == "High"

    def test_small_project_slow_resolution(self):
        """Test small project with slow issue resolution."""
        repo_data = _repo_with_resolution(5000, 120)
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 2
        assert "Needs attention" in result.message
        assert result.risk == "High"

    def test_small_project_backlog_resolution(self):
        """Test small project with significant backlog."""
        repo_data = _repo_with_resolution(5000, 200)
        result = check_issue_resolution_duration(repo_data)
        assert result.score == 0
        assert "Observe" in result.message
        assert result.risk == "High"

    def test_issue_resolution_metric_spec_checker(self):
        """Test MetricSpec checker delegates to the metric function."""
        repo_data = _repo_with_resolution(5000, 3)
        context = MetricContext(owner="owner", name="repo", repo_url="url")
        result = METRIC.checker(repo_data, context)
        assert result.name == "Issue Resolution Duration"

    def test_issue_resolution_metric_spec_on_error(self):
        """Test MetricSpec error handler formatting."""
        result = METRIC.on_error(RuntimeError("boom"))
        assert result.score == 0
        assert "Analysis incomplete" in result.message
