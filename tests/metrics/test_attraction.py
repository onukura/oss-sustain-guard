"""
Tests for the attraction metric.
"""

from datetime import datetime, timedelta, timezone

from oss_sustain_guard.metrics.attraction import check_attraction


class TestAttractionMetric:
    """Test the check_attraction metric function."""

    def test_attraction_no_default_branch(self):
        """Test when default branch is not available."""
        repo_data = {}
        result = check_attraction(repo_data)
        assert result.name == "Contributor Attraction"
        assert result.score == 0
        assert result.max_score == 10
        assert "Commit history data not available" in result.message
        assert result.risk == "Medium"

    def test_attraction_no_history(self):
        """Test when no commit history is available."""
        repo_data = {"defaultBranchRef": {"target": {"history": {"edges": []}}}}
        result = check_attraction(repo_data)
        assert result.name == "Contributor Attraction"
        assert result.score == 0
        assert result.max_score == 10
        assert "No commit history available for analysis" in result.message
        assert result.risk == "Medium"

    def test_attraction_strong_attraction(self):
        """Test with 5+ new contributors."""
        now = datetime.now(timezone.utc)
        six_months_ago = now - timedelta(days=180)
        recent_date = six_months_ago + timedelta(days=30)
        old_date = six_months_ago - timedelta(days=30)

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
                                    "author": {"user": {"login": "user3"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user4"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "user5"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                            {
                                "node": {
                                    "author": {"user": {"login": "olduser"}},
                                    "authoredDate": old_date.isoformat(),
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_attraction(repo_data)
        assert result.name == "Contributor Attraction"
        assert result.score == 10
        assert result.max_score == 10
        assert "Strong: 5 new contributors in last 6 months" in result.message
        assert result.risk == "None"

    def test_attraction_good_attraction(self):
        """Test with 3-4 new contributors."""
        now = datetime.now(timezone.utc)
        six_months_ago = now - timedelta(days=180)
        recent_date = six_months_ago + timedelta(days=30)

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
                                    "author": {"user": {"login": "user3"}},
                                    "authoredDate": recent_date.isoformat(),
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_attraction(repo_data)
        assert result.name == "Contributor Attraction"
        assert result.score == 7
        assert result.max_score == 10
        assert "Good: 3 new contributors in last 6 months" in result.message
        assert result.risk == "Low"

    def test_attraction_moderate_attraction(self):
        """Test with 1-2 new contributors."""
        now = datetime.now(timezone.utc)
        six_months_ago = now - timedelta(days=180)
        recent_date = six_months_ago + timedelta(days=30)

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
        result = check_attraction(repo_data)
        assert result.name == "Contributor Attraction"
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate: 1 new contributor(s) in last 6 months" in result.message
        assert result.risk == "Medium"

    def test_attraction_no_new_contributors(self):
        """Test with no new contributors."""
        now = datetime.now(timezone.utc)
        six_months_ago = now - timedelta(days=180)
        old_date = six_months_ago - timedelta(days=30)

        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {
                                "node": {
                                    "author": {"user": {"login": "olduser"}},
                                    "authoredDate": old_date.isoformat(),
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_attraction(repo_data)
        assert result.name == "Contributor Attraction"
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe: No new contributors in last 6 months" in result.message
        assert result.risk == "Medium"
