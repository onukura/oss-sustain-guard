"""
Tests for the maintainer_drain metric.
"""

from datetime import datetime, timedelta, timezone

from oss_sustain_guard.metrics.maintainer_drain import check_maintainer_drain


class TestMaintainerDrainMetric:
    """Test the check_maintainer_drain metric function."""

    def test_maintainer_drain_no_default_branch(self):
        """Test when default branch is not available."""
        repo_data = {}
        result = check_maintainer_drain(repo_data)
        assert result.name == "Maintainer Retention"
        assert result.score == 10
        assert result.max_score == 10
        assert "Maintainer data not available" in result.message
        assert result.risk == "None"

    def test_maintainer_drain_insufficient_history(self):
        """Test when commit history is insufficient."""
        repo_data = {
            "defaultBranchRef": {"target": {"history": {"edges": [{"node": {}}] * 10}}}
        }
        result = check_maintainer_drain(repo_data)
        assert result.name == "Maintainer Retention"
        assert result.score == 10
        assert result.max_score == 10
        assert "Insufficient commit history" in result.message
        assert result.risk == "None"

    def test_maintainer_drain_critical_drain(self):
        """Test with critical maintainer drain (90% reduction)."""
        now = datetime.now(timezone.utc)
        recent_date = now - timedelta(days=30)
        older_date = now - timedelta(days=200)
        # Create 50 commits: 25 recent with 1 contributor, 25 older with 10 contributors
        recent_commits = [
            {
                "node": {
                    "authoredDate": recent_date.isoformat(),
                    "author": {"user": {"login": "user1"}},
                }
            }
        ] * 25
        older_commits = []
        for i in range(10):
            older_commits.extend(
                [
                    {
                        "node": {
                            "authoredDate": older_date.isoformat(),
                            "author": {"user": {"login": f"user{i}"}},
                        }
                    }
                ]
                * 2
            )
        older_commits.extend(
            [{"node": {"author": {"user": {"login": "user1"}}}}] * 5
        )  # Make 25 total

        repo_data = {
            "defaultBranchRef": {
                "target": {"history": {"edges": recent_commits + older_commits}}
            }
        }
        result = check_maintainer_drain(repo_data)
        assert result.name == "Maintainer Retention"
        assert result.score == 0
        assert result.max_score == 10
        assert "Critical: 90% reduction in maintainers" in result.message
        assert result.risk == "Critical"

    def test_maintainer_drain_high_drain(self):
        """Test with high maintainer drain (70% reduction)."""
        now = datetime.now(timezone.utc)
        recent_date = now - timedelta(days=30)
        older_date = now - timedelta(days=200)
        # 3 recent contributors, 10 older
        recent_commits = []
        for i in range(3):
            recent_commits.extend(
                [
                    {
                        "node": {
                            "authoredDate": recent_date.isoformat(),
                            "author": {"user": {"login": f"user{i}"}},
                        }
                    }
                ]
                * 8
            )
        recent_commits.extend(
            [
                {
                    "node": {
                        "authoredDate": recent_date.isoformat(),
                        "author": {"user": {"login": "user0"}},
                    }
                }
            ]
            * 1
        )  # Make 25

        older_commits = []
        for i in range(10):
            older_commits.extend(
                [
                    {
                        "node": {
                            "authoredDate": older_date.isoformat(),
                            "author": {"user": {"login": f"user{i}"}},
                        }
                    }
                ]
                * 2
            )
        older_commits.extend(
            [
                {
                    "node": {
                        "authoredDate": older_date.isoformat(),
                        "author": {"user": {"login": "user0"}},
                    }
                }
            ]
            * 5
        )  # Make 25

        repo_data = {
            "defaultBranchRef": {
                "target": {"history": {"edges": recent_commits + older_commits}}
            }
        }
        result = check_maintainer_drain(repo_data)
        assert result.name == "Maintainer Retention"
        assert result.score == 3
        assert result.max_score == 10
        assert "High: 70% reduction in maintainers" in result.message
        assert result.risk == "High"

    def test_maintainer_drain_medium_drain(self):
        """Test with medium maintainer drain (50% reduction)."""
        now = datetime.now(timezone.utc)
        recent_date = now - timedelta(days=30)
        older_date = now - timedelta(days=200)
        # 5 recent contributors, 10 older
        recent_commits = []
        for i in range(5):
            recent_commits.extend(
                [
                    {
                        "node": {
                            "authoredDate": recent_date.isoformat(),
                            "author": {"user": {"login": f"user{i}"}},
                        }
                    }
                ]
                * 5
            )

        older_commits = []
        for i in range(10):
            older_commits.extend(
                [
                    {
                        "node": {
                            "authoredDate": older_date.isoformat(),
                            "author": {"user": {"login": f"user{i}"}},
                        }
                    }
                ]
                * 2
            )
        older_commits.extend(
            [
                {
                    "node": {
                        "authoredDate": older_date.isoformat(),
                        "author": {"user": {"login": "user0"}},
                    }
                }
            ]
            * 5
        )  # Make 25

        repo_data = {
            "defaultBranchRef": {
                "target": {"history": {"edges": recent_commits + older_commits}}
            }
        }
        result = check_maintainer_drain(repo_data)
        assert result.name == "Maintainer Retention"
        assert result.score == 5
        assert result.max_score == 10
        assert "Medium: 50% reduction in maintainers" in result.message
        assert result.risk == "Medium"

    def test_maintainer_drain_stable(self):
        """Test with stable maintainer retention."""
        # 8 recent contributors, 8 older
        recent_commits = []
        for i in range(8):
            recent_commits.extend(
                [{"node": {"author": {"user": {"login": f"user{i}"}}}}] * 3
            )
        recent_commits.extend(
            [{"node": {"author": {"user": {"login": "user0"}}}}] * 1
        )  # Make 25

        older_commits = []
        for i in range(8):
            older_commits.extend(
                [{"node": {"author": {"user": {"login": f"user{i}"}}}}] * 3
            )
        older_commits.extend(
            [{"node": {"author": {"user": {"login": "user0"}}}}] * 1
        )  # Make 25

        repo_data = {
            "defaultBranchRef": {
                "target": {"history": {"edges": recent_commits + older_commits}}
            }
        }
        result = check_maintainer_drain(repo_data)
        assert result.name == "Maintainer Retention"
        assert result.score == 10
        assert result.max_score == 10
        assert "Stable: 8 active maintainers" in result.message
        assert result.risk == "None"
