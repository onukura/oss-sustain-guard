"""Tests for community health metric."""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.community_health import check_community_health


class TestCommunityHealth:
    """Test community health metric."""

    def test_no_issues(self):
        """Test with no open issues."""
        repo_data = {"issues": {"edges": []}}
        result = check_community_health(repo_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "No open issues" in result.message
        assert result.risk == "None"

    def test_no_response_data(self):
        """Test with issues but no response data."""
        repo_data = {
            "issues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": "2023-01-01T00:00:00Z",
                            "comments": {"edges": []},
                        }
                    }
                ]
            }
        }
        result = check_community_health(repo_data)
        assert result.score == 6
        assert result.max_score == 10
        assert "No recent issue responses" in result.message
        assert result.risk == "None"

    def test_excellent_response_time(self):
        """Test excellent response time (<48 hours)."""
        base_time = datetime.now()
        repo_data = {
            "issues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "comments": {
                                "edges": [
                                    {
                                        "node": {
                                            "createdAt": (
                                                base_time + timedelta(hours=24)
                                            ).isoformat()
                                        }
                                    }
                                ]
                            },
                        }
                    }
                ]
            }
        }
        result = check_community_health(repo_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_good_response_time(self):
        """Test good response time (<7 days)."""
        base_time = datetime.now()
        repo_data = {
            "issues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "comments": {
                                "edges": [
                                    {
                                        "node": {
                                            "createdAt": (
                                                base_time + timedelta(days=3)
                                            ).isoformat()
                                        }
                                    }
                                ]
                            },
                        }
                    }
                ]
            }
        }
        result = check_community_health(repo_data)
        assert result.score == 6
        assert result.max_score == 10
        assert "Good" in result.message
        assert result.risk == "None"

    def test_slow_response_time(self):
        """Test slow response time (7-30 days)."""
        base_time = datetime.now()
        repo_data = {
            "issues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "comments": {
                                "edges": [
                                    {
                                        "node": {
                                            "createdAt": (
                                                base_time + timedelta(days=14)
                                            ).isoformat()
                                        }
                                    }
                                ]
                            },
                        }
                    }
                ]
            }
        }
        result = check_community_health(repo_data)
        assert result.score == 2
        assert result.max_score == 10
        assert "Slow" in result.message
        assert result.risk == "Medium"

    def test_poor_response_time(self):
        """Test poor response time (>30 days)."""
        base_time = datetime.now()
        repo_data = {
            "issues": {
                "edges": [
                    {
                        "node": {
                            "createdAt": base_time.isoformat(),
                            "comments": {
                                "edges": [
                                    {
                                        "node": {
                                            "createdAt": (
                                                base_time + timedelta(days=60)
                                            ).isoformat()
                                        }
                                    }
                                ]
                            },
                        }
                    }
                ]
            }
        }
        result = check_community_health(repo_data)
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe" in result.message
        assert result.risk == "High"
