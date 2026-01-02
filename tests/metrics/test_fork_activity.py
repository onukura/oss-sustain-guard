"""Tests for fork activity metric."""

from datetime import datetime, timedelta, timezone

from oss_sustain_guard.metrics.base import MetricContext
from oss_sustain_guard.metrics.fork_activity import METRIC, check_fork_activity


def _fork_edge(
    created_at: str | None,
    pushed_at: str | int | None,
    committed_at: str | None,
    include_branch: bool = True,
) -> dict:
    node: dict[str, object] = {}
    if created_at is not None:
        node["createdAt"] = created_at
    if pushed_at is not None:
        node["pushedAt"] = pushed_at
    if include_branch:
        history_edges = []
        if committed_at is not None:
            history_edges.append({"node": {"committedDate": committed_at}})
        node["defaultBranchRef"] = {"target": {"history": {"edges": history_edges}}}
    return {"node": node}


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

    def test_large_ecosystem_low_active_ratio(self):
        """Test large ecosystem with low active fork ratio."""
        now = datetime.now(timezone.utc)
        active = _fork_edge(
            (now - timedelta(days=60)).isoformat(),
            (now - timedelta(days=20)).isoformat(),
            (now - timedelta(days=20)).isoformat(),
        )
        inactive = _fork_edge(
            (now - timedelta(days=600)).isoformat(),
            (now - timedelta(days=400)).isoformat(),
            (now - timedelta(days=400)).isoformat(),
        )
        repo_data = {
            "forkCount": 120,
            "forks": {"edges": [active] + [inactive] * 9},
        }
        result = check_fork_activity(repo_data)
        assert result.score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_large_ecosystem_moderate_ratio(self):
        """Test large ecosystem with moderate active fork ratio."""
        now = datetime.now(timezone.utc)
        active = _fork_edge(
            (now - timedelta(days=60)).isoformat(),
            (now - timedelta(days=20)).isoformat(),
            (now - timedelta(days=20)).isoformat(),
        )
        inactive = _fork_edge(
            (now - timedelta(days=600)).isoformat(),
            (now - timedelta(days=400)).isoformat(),
            (now - timedelta(days=400)).isoformat(),
        )
        repo_data = {
            "forkCount": 120,
            "forks": {"edges": [active] * 3 + [inactive] * 7},
        }
        result = check_fork_activity(repo_data)
        assert result.score == 6
        assert "Monitor" in result.message
        assert result.risk == "Low"

    def test_medium_ecosystem_good_ratio(self):
        """Test medium ecosystem with good active fork ratio."""
        now = datetime.now(timezone.utc)
        active = _fork_edge(
            (now - timedelta(days=60)).isoformat(),
            (now - timedelta(days=20)).isoformat(),
            (now - timedelta(days=20)).isoformat(),
        )
        inactive = _fork_edge(
            (now - timedelta(days=600)).isoformat(),
            (now - timedelta(days=400)).isoformat(),
            (now - timedelta(days=400)).isoformat(),
        )
        repo_data = {
            "forkCount": 60,
            "forks": {"edges": [active] * 2 + [inactive] * 8},
        }
        result = check_fork_activity(repo_data)
        assert result.score == 8
        assert "Good" in result.message
        assert result.risk == "None"

    def test_small_ecosystem_fallback_push_date(self):
        """Test fallback to push date when default branch is missing."""
        now = datetime.now(timezone.utc)
        repo_data = {
            "forkCount": 12,
            "forks": {
                "edges": [
                    _fork_edge(
                        (now - timedelta(days=60)).isoformat(),
                        (now - timedelta(days=20)).isoformat(),
                        None,
                        include_branch=False,
                    )
                ]
            },
        }
        result = check_fork_activity(repo_data)
        assert result.score == 4
        assert "Early: 12 forks, 1 active" in result.message
        assert result.risk == "None"

    def test_very_small_ecosystem_active(self):
        """Test very small ecosystem with some activity."""
        now = datetime.now(timezone.utc)
        repo_data = {
            "forkCount": 5,
            "forks": {
                "edges": [
                    _fork_edge(
                        (now - timedelta(days=60)).isoformat(),
                        (now - timedelta(days=20)).isoformat(),
                        (now - timedelta(days=20)).isoformat(),
                    )
                ]
            },
        }
        result = check_fork_activity(repo_data)
        assert result.score == 4
        assert "Early: 5 fork(s), 1 active" in result.message
        assert result.risk == "Low"

    def test_fork_activity_invalid_dates(self):
        """Test handling of invalid fork timestamps."""
        repo_data = {
            "forkCount": 5,
            "forks": {
                "edges": [_fork_edge("not-a-date", 123, None, include_branch=False)]
            },
        }
        result = check_fork_activity(repo_data)
        assert result.score == 2
        assert "Limited" in result.message
        assert result.risk == "Low"

    def test_fork_activity_metric_spec_checker(self):
        """Test MetricSpec checker delegates to the metric function."""
        repo_data = {"forkCount": 0, "forks": {"edges": []}}
        context = MetricContext(owner="owner", name="repo", repo_url="url")
        result = METRIC.checker(repo_data, context)
        assert result.name == "Fork Activity"

    def test_fork_activity_metric_spec_on_error(self):
        """Test MetricSpec error handler formatting."""
        result = METRIC.on_error(RuntimeError("boom"))
        assert result.score == 0
        assert "Analysis incomplete" in result.message
