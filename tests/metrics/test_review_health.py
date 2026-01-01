"""
Tests for the review_health metric.
"""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.review_health import check_review_health


class TestReviewHealthMetric:
    """Test the check_review_health metric function."""

    def test_review_health_no_prs(self):
        """Test when no pull requests are available."""
        repo_data = {"pullRequests": {"edges": []}}
        result = check_review_health(repo_data)
        assert result.name == "Review Health"
        assert result.score == 5
        assert result.max_score == 10
        assert "No recent merged pull requests to analyze" in result.message
        assert result.risk == "None"

    def test_review_health_no_reviews(self):
        """Test when PRs exist but no reviews."""
        created_at = datetime.now()
        repo_data = {
            "pullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": created_at.isoformat() + "Z",
                            "reviews": {"edges": [], "totalCount": 0},
                        }
                    }
                ]
            }
        }
        result = check_review_health(repo_data)
        assert result.name == "Review Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "No review activity detected" in result.message
        assert result.risk == "Medium"

    def test_review_health_excellent(self):
        """Test with excellent review health."""
        created_at = datetime.now()
        review_at = created_at + timedelta(hours=24)  # <48h
        repo_data = {
            "pullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": created_at.isoformat() + "Z",
                            "reviews": {
                                "edges": [
                                    {
                                        "node": {
                                            "createdAt": review_at.isoformat() + "Z"
                                        }
                                    },
                                    {
                                        "node": {
                                            "createdAt": (
                                                review_at + timedelta(hours=1)
                                            ).isoformat()
                                            + "Z"
                                        }
                                    },
                                ],
                                "totalCount": 2,
                            },
                        }
                    }
                ]
            }
        }
        result = check_review_health(repo_data)
        assert result.name == "Review Health"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: Avg time to first review 24.0h" in result.message
        assert result.risk == "None"

    def test_review_health_good(self):
        """Test with good review health."""
        created_at = datetime.now()
        review_at = created_at + timedelta(days=3)  # <7d
        repo_data = {
            "pullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": created_at.isoformat() + "Z",
                            "reviews": {
                                "edges": [
                                    {
                                        "node": {
                                            "createdAt": review_at.isoformat() + "Z"
                                        }
                                    },
                                ],
                                "totalCount": 1,
                            },
                        }
                    }
                ]
            }
        }
        result = check_review_health(repo_data)
        assert result.name == "Review Health"
        assert result.score == 7
        assert result.max_score == 10
        assert "Good: Avg time to first review 72.0h" in result.message
        assert result.risk == "Low"

    def test_review_health_moderate(self):
        """Test with moderate review health."""
        created_at = datetime.now()
        review_at = created_at + timedelta(days=5)  # <7d but low reviews
        repo_data = {
            "pullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": created_at.isoformat() + "Z",
                            "reviews": {
                                "edges": [
                                    {
                                        "node": {
                                            "createdAt": review_at.isoformat() + "Z"
                                        }
                                    },
                                ],
                                "totalCount": 0,  # Low count
                            },
                        }
                    }
                ]
            }
        }
        result = check_review_health(repo_data)
        assert result.name == "Review Health"
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate: Avg time to first review 120.0h" in result.message
        assert result.risk == "Medium"

    def test_review_health_poor(self):
        """Test with poor review health."""
        created_at = datetime.now()
        review_at = created_at + timedelta(days=10)  # >7d
        repo_data = {
            "pullRequests": {
                "edges": [
                    {
                        "node": {
                            "createdAt": created_at.isoformat() + "Z",
                            "reviews": {
                                "edges": [
                                    {
                                        "node": {
                                            "createdAt": review_at.isoformat() + "Z"
                                        }
                                    },
                                ],
                                "totalCount": 1,
                            },
                        }
                    }
                ]
            }
        }
        result = check_review_health(repo_data)
        assert result.name == "Review Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe: Slow review process" in result.message
        assert result.risk == "Medium"
