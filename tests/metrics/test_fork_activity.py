"""Tests for fork activity metric."""

from datetime import datetime, timedelta, timezone

from oss_sustain_guard.metrics.fork_activity import check_fork_activity


class TestForkActivity:
    """Test fork activity metric."""

    def test_no_forks(self):
        """Test with no forks."""
        repo_data = {"forkCount": 0, "forks": {"edges": []}}
        result = check_fork_activity(repo_data)
        assert result.score == 0
        assert result.max_score == 10
        assert "No forks yet" in result.message
        assert result.risk == "Low"

    def test_large_ecosystem_healthy(self):
        """Test large ecosystem with healthy fork activity."""
        now = datetime.now(timezone.utc)
        repo_data = {
            "forkCount": 150,
            "forks": {
                "edges": [
                    {
                        "node": {
                            "createdAt": (now - timedelta(days=60)).isoformat(),
                            "pushedAt": (now - timedelta(days=30)).isoformat(),
                            "defaultBranchRef": {
                                "target": {
                                    "history": {
                                        "edges": [
                                            {
                                                "node": {
                                                    "committedDate": (
                                                        now - timedelta(days=30)
                                                    ).isoformat()
                                                }
                                            }
                                        ]
                                    }
                                }
                            },
                        }
                    }
                ]
                * 3  # 3 active forks out of 20 sample
            },
        }
        result = check_fork_activity(repo_data)
        assert result.score == 2
        assert result.max_score == 10
        assert "Needs attention" in result.message
        assert result.risk == "Medium"

    def test_large_ecosystem_high_divergence(self):
        """Test large ecosystem with high fork divergence risk."""
        now = datetime.now(timezone.utc)
        repo_data = {
            "forkCount": 150,
            "forks": {
                "edges": [
                    {
                        "node": {
                            "createdAt": (now - timedelta(days=60)).isoformat(),
                            "pushedAt": (now - timedelta(days=30)).isoformat(),
                            "defaultBranchRef": {
                                "target": {
                                    "history": {
                                        "edges": [
                                            {
                                                "node": {
                                                    "committedDate": (
                                                        now - timedelta(days=30)
                                                    ).isoformat()
                                                }
                                            }
                                        ]
                                    }
                                }
                            },
                        }
                    }
                ]
                * 10  # 10 active forks out of 20 sample (>40%)
            },
        }
        result = check_fork_activity(repo_data)
        assert result.score == 2
        assert result.max_score == 10
        assert "Needs attention" in result.message
        assert result.risk == "Medium"

    def test_medium_ecosystem_growing(self):
        """Test medium ecosystem growing."""
        now = datetime.now(timezone.utc)
        repo_data = {
            "forkCount": 75,
            "forks": {
                "edges": [
                    {
                        "node": {
                            "createdAt": (now - timedelta(days=60)).isoformat(),
                            "pushedAt": (now - timedelta(days=30)).isoformat(),
                            "defaultBranchRef": {
                                "target": {
                                    "history": {
                                        "edges": [
                                            {
                                                "node": {
                                                    "committedDate": (
                                                        now - timedelta(days=30)
                                                    ).isoformat()
                                                }
                                            }
                                        ]
                                    }
                                }
                            },
                        }
                    }
                ]
                * 4  # 4 active forks out of 20 sample
            },
        }
        result = check_fork_activity(repo_data)
        assert result.score == 4
        assert result.max_score == 10
        assert "Monitor" in result.message
        assert result.risk == "Low"

    def test_small_ecosystem_emerging(self):
        """Test small ecosystem with emerging interest."""
        now = datetime.now(timezone.utc)
        repo_data = {
            "forkCount": 15,
            "forks": {
                "edges": [
                    {
                        "node": {
                            "createdAt": (now - timedelta(days=60)).isoformat(),
                            "pushedAt": (now - timedelta(days=30)).isoformat(),
                            "defaultBranchRef": {
                                "target": {
                                    "history": {
                                        "edges": [
                                            {
                                                "node": {
                                                    "committedDate": (
                                                        now - timedelta(days=30)
                                                    ).isoformat()
                                                }
                                            }
                                        ]
                                    }
                                }
                            },
                        }
                    }
                ]
                * 2  # 2 active forks
            },
        }
        result = check_fork_activity(repo_data)
        assert result.score == 6
        assert result.max_score == 10
        assert "Moderate" in result.message
        assert result.risk == "None"

    def test_very_small_ecosystem_limited(self):
        """Test very small ecosystem with limited activity."""
        repo_data = {
            "forkCount": 3,
            "forks": {
                "edges": [
                    {
                        "node": {
                            "createdAt": "2023-01-01T00:00:00Z",
                            "pushedAt": "2023-01-01T00:00:00Z",
                        }
                    }
                ]
                * 3  # 3 forks, no recent activity
            },
        }
        result = check_fork_activity(repo_data)
        assert result.score == 2
        assert result.max_score == 10
        assert "Limited" in result.message
        assert result.risk == "Low"
