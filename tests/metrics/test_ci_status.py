"""
Tests for the ci_status metric.
"""

from oss_sustain_guard.metrics.base import MetricContext
from oss_sustain_guard.metrics.ci_status import METRIC, check_ci_status


class TestCiStatusMetric:
    """Test the check_ci_status metric function."""

    def test_ci_status_archived_repository(self):
        """Test when repository is archived."""
        repo_data = {"isArchived": True}
        result = check_ci_status(repo_data)
        assert result.name == "Build Health"
        assert result.score == 10
        assert result.max_score == 10
        assert "Repository archived" in result.message
        assert result.risk == "None"

    def test_ci_status_no_default_branch(self):
        """Test when default branch is not available."""
        repo_data = {}
        result = check_ci_status(repo_data)
        assert result.name == "Build Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "CI status data not available" in result.message
        assert result.risk == "High"

    def test_ci_status_no_target(self):
        """Test when default branch has no target."""
        repo_data = {"defaultBranchRef": {}}
        result = check_ci_status(repo_data)
        assert result.name == "Build Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "CI status data not available" in result.message
        assert result.risk == "High"

    def test_ci_status_no_check_suites(self):
        """Test when no checkSuites data."""
        repo_data = {"defaultBranchRef": {"target": {}}}
        result = check_ci_status(repo_data)
        assert result.name == "Build Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "No CI configuration detected" in result.message
        assert result.risk == "High"

    def test_ci_status_empty_check_suites(self):
        """Test when checkSuites is empty."""
        repo_data = {"defaultBranchRef": {"target": {"checkSuites": {"nodes": []}}}}
        result = check_ci_status(repo_data)
        assert result.name == "Build Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "No recent CI checks" in result.message
        assert result.risk == "High"

    def test_ci_status_success(self):
        """Test when CI status is SUCCESS."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "checkSuites": {
                        "nodes": [{"conclusion": "SUCCESS", "status": "COMPLETED"}]
                    }
                }
            }
        }
        result = check_ci_status(repo_data)
        assert result.name == "Build Health"
        assert result.score == 10
        assert result.max_score == 10
        assert "success" in result.message
        assert result.risk == "None"

    def test_ci_status_failure(self):
        """Test when CI status is FAILURE."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "checkSuites": {
                        "nodes": [{"conclusion": "FAILURE", "status": "COMPLETED"}]
                    }
                }
            }
        }
        result = check_ci_status(repo_data)
        assert result.name == "Build Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "failure" in result.message
        assert result.risk == "Medium"

    def test_ci_status_in_progress(self):
        """Test when CI status is IN_PROGRESS."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "checkSuites": {
                        "nodes": [{"conclusion": None, "status": "IN_PROGRESS"}]
                    }
                }
            }
        }
        result = check_ci_status(repo_data)
        assert result.name == "Build Health"
        assert result.score == 6
        assert result.max_score == 10
        assert "Tests in progress" in result.message
        assert result.risk == "Low"

    def test_ci_status_queued(self):
        """Test when CI status is QUEUED."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "checkSuites": {"nodes": [{"conclusion": None, "status": "QUEUED"}]}
                }
            }
        }
        result = check_ci_status(repo_data)
        assert result.name == "Build Health"
        assert result.score == 6
        assert result.max_score == 10
        assert "Tests queued" in result.message
        assert result.risk == "Low"

    def test_ci_status_skipped(self):
        """Test when CI status is SKIPPED."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "checkSuites": {
                        "nodes": [{"conclusion": "SKIPPED", "status": "COMPLETED"}]
                    }
                }
            }
        }
        result = check_ci_status(repo_data)
        assert result.name == "Build Health"
        assert result.score == 6
        assert result.max_score == 10
        assert "skipped" in result.message
        assert result.risk == "Low"

    def test_ci_status_latest_suite_not_dict(self):
        """Test when latest check suite is not a dict."""
        repo_data = {
            "defaultBranchRef": {"target": {"checkSuites": {"nodes": ["oops"]}}}
        }
        result = check_ci_status(repo_data)
        assert result.score == 0
        assert "No recent CI checks" in result.message
        assert result.risk == "High"

    def test_ci_status_non_string_values(self):
        """Test when conclusion and status are not strings."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "checkSuites": {"nodes": [{"conclusion": 123, "status": 456}]}
                }
            }
        }
        result = check_ci_status(repo_data)
        assert result.score == 6
        assert "Configured" in result.message
        assert result.risk == "Low"

    def test_ci_status_unknown_conclusion(self):
        """Test when CI status is unknown."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "checkSuites": {
                        "nodes": [{"conclusion": "WEIRD", "status": "COMPLETED"}]
                    }
                }
            }
        }
        result = check_ci_status(repo_data)
        assert result.score == 4
        assert "Unknown" in result.message
        assert result.risk == "Low"

    def test_ci_status_metric_spec_checker(self):
        """Test MetricSpec checker delegates to the metric function."""
        repo_data = {"isArchived": True}
        context = MetricContext(owner="owner", name="repo", repo_url="url")
        result = METRIC.checker(repo_data, context)
        assert result.name == "Build Health"

    def test_ci_status_metric_spec_on_error(self):
        """Test MetricSpec error handler formatting."""
        result = METRIC.on_error(RuntimeError("boom"))
        assert result.score == 0
        assert "Analysis incomplete" in result.message
