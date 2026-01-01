"""
Tests for the retention metric.
"""

from datetime import datetime, timedelta, timezone

from oss_sustain_guard.metrics.retention import check_retention


class TestRetentionMetric:
    """Test the check_retention metric function."""

    def test_retention_no_default_branch(self):
        """Test when default branch is not available."""
        repo_data = {}
        result = check_retention(repo_data)
        assert result.name == "Contributor Retention"
        assert result.score == 5
        assert result.max_score == 10
        assert "Commit history data not available" in result.message
        assert result.risk == "Medium"

    def test_retention_no_history(self):
        """Test when no commit history is available."""
        repo_data = {"defaultBranchRef": {"target": {"history": {"edges": []}}}}
        result = check_retention(repo_data)
        assert result.name == "Contributor Retention"
        assert result.score == 5
        assert result.max_score == 10
        assert "No commit history available for analysis" in result.message
        assert result.risk == "Medium"

    def test_retention_new_project(self):
        """Test for new project with no earlier contributors."""
        now = datetime.now(timezone.utc)
        recent_date = now - timedelta(days=30)

        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {
                                "node": {
                                    "author": {"user": {"login": "user1"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_retention(repo_data)
        assert result.name == "Contributor Retention"
        assert result.score == 10
        assert result.max_score == 10
        assert "New project: Not enough history to assess retention" in result.message
        assert result.risk == "None"

    def test_retention_excellent(self):
        """Test with excellent retention (80%+)."""
        now = datetime.now(timezone.utc)
        recent_date = now - timedelta(days=30)
        earlier_date = now - timedelta(days=120)

        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {
                                "node": {
                                    "author": {"user": {"login": "user1"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user2"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user1"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user2"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user3"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user3"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_retention(repo_data)
        assert result.name == "Contributor Retention"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: 100% contributor retention" in result.message
        assert result.risk == "None"

    def test_retention_good(self):
        """Test with good retention (60-79%)."""
        now = datetime.now(timezone.utc)
        recent_date = now - timedelta(days=30)
        earlier_date = now - timedelta(days=120)

        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {
                                "node": {
                                    "author": {"user": {"login": "user1"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user2"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user1"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user2"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user3"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_retention(repo_data)
        assert result.name == "Contributor Retention"
        assert result.score == 7
        assert result.max_score == 10
        assert "Good: 67% contributor retention" in result.message
        assert result.risk == "Low"

    def test_retention_moderate(self):
        """Test with moderate retention (40-59%)."""
        now = datetime.now(timezone.utc)
        recent_date = now - timedelta(days=30)
        earlier_date = now - timedelta(days=120)

        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {
                                "node": {
                                    "author": {"user": {"login": "user1"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user1"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user2"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_retention(repo_data)
        assert result.name == "Contributor Retention"
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate: 50% contributor retention" in result.message
        assert result.risk == "Medium"

    def test_retention_poor(self):
        """Test with poor retention (<40%)."""
        now = datetime.now(timezone.utc)
        recent_date = now - timedelta(days=30)
        earlier_date = now - timedelta(days=120)

        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {
                                "node": {
                                    "author": {"user": {"login": "user1"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user1"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user2"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user3"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user4"}},
                                    "authoredDate": earlier_date.isoformat(),
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_retention(repo_data)
        assert result.name == "Contributor Retention"
        assert result.score == 0
        assert result.max_score == 10
        assert "Needs attention: 25% contributor retention" in result.message
        assert result.risk == "High"
