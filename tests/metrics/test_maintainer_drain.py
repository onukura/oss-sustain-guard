"""
Tests for the maintainer_drain metric.
"""

from datetime import datetime, timedelta, timezone

from oss_sustain_guard.metrics.maintainer_drain import check_maintainer_drain
from oss_sustain_guard.vcs.base import VCSRepositoryData


def _vcs_data(**overrides) -> VCSRepositoryData:
    data = VCSRepositoryData(
        is_archived=False,
        pushed_at=None,
        owner_type="User",
        owner_login="owner",
        owner_name=None,
        star_count=0,
        description=None,
        homepage_url=None,
        topics=[],
        readme_size=None,
        contributing_file_size=None,
        default_branch="main",
        watchers_count=0,
        open_issues_count=0,
        language=None,
        commits=[],
        total_commits=0,
        merged_prs=[],
        closed_prs=[],
        total_merged_prs=0,
        releases=[],
        open_issues=[],
        closed_issues=[],
        total_closed_issues=0,
        vulnerability_alerts=None,
        has_security_policy=False,
        code_of_conduct=None,
        license_info=None,
        has_wiki=False,
        has_issues=True,
        has_discussions=False,
        funding_links=[],
        forks=[],
        total_forks=0,
        ci_status=None,
        sample_counts={},
        raw_data=None,
    )
    return data._replace(**overrides)


def _vcs_with_commits(
    commits: list[dict],
    total_commits: int | None = None,
    default_branch: str | None = "main",
) -> VCSRepositoryData:
    commit_total = total_commits if total_commits is not None else len(commits)
    return _vcs_data(
        commits=commits,
        total_commits=commit_total,
        default_branch=default_branch,
    )


class TestMaintainerDrainMetric:
    """Test the check_maintainer_drain metric function."""

    def test_maintainer_drain_no_default_branch(self):
        """Test when default branch is not available."""
        vcs_data = _vcs_data(default_branch=None)
        result = check_maintainer_drain(vcs_data)
        assert result.name == "Maintainer Retention"
        assert result.score == 10
        assert result.max_score == 10
        assert "Maintainer data not available" in result.message
        assert result.risk == "None"

    def test_maintainer_drain_insufficient_history(self):
        """Test when commit history is insufficient."""
        vcs_data = _vcs_with_commits([{}] * 10)
        result = check_maintainer_drain(vcs_data)
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
                "authoredDate": recent_date.isoformat(),
                "author": {"user": {"login": "user1"}},
            }
        ] * 25
        older_commits = []
        for i in range(10):
            older_commits.extend(
                [
                    {
                        "authoredDate": older_date.isoformat(),
                        "author": {"user": {"login": f"user{i}"}},
                    }
                ]
                * 2
            )
        older_commits.extend(
            [{"author": {"user": {"login": "user1"}}}] * 5
        )  # Make 25 total

        vcs_data = _vcs_with_commits(recent_commits + older_commits)
        result = check_maintainer_drain(vcs_data)
        assert result.name == "Maintainer Retention"
        assert result.score == 0
        assert result.max_score == 10
        assert "Needs support: 90% reduction in maintainers" in result.message
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
                        "authoredDate": recent_date.isoformat(),
                        "author": {"user": {"login": f"user{i}"}},
                    }
                ]
                * 8
            )
        recent_commits.extend(
            [
                {
                    "authoredDate": recent_date.isoformat(),
                    "author": {"user": {"login": "user0"}},
                }
            ]
            * 1
        )  # Make 25

        older_commits = []
        for i in range(10):
            older_commits.extend(
                [
                    {
                        "authoredDate": older_date.isoformat(),
                        "author": {"user": {"login": f"user{i}"}},
                    }
                ]
                * 2
            )
        older_commits.extend(
            [
                {
                    "authoredDate": older_date.isoformat(),
                    "author": {"user": {"login": "user0"}},
                }
            ]
            * 5
        )  # Make 25

        vcs_data = _vcs_with_commits(recent_commits + older_commits)
        result = check_maintainer_drain(vcs_data)
        assert result.name == "Maintainer Retention"
        assert result.score == 3
        assert result.max_score == 10
        assert "Needs attention: 70% reduction in maintainers" in result.message
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
                        "authoredDate": recent_date.isoformat(),
                        "author": {"user": {"login": f"user{i}"}},
                    }
                ]
                * 5
            )

        older_commits = []
        for i in range(10):
            older_commits.extend(
                [
                    {
                        "authoredDate": older_date.isoformat(),
                        "author": {"user": {"login": f"user{i}"}},
                    }
                ]
                * 2
            )
        older_commits.extend(
            [
                {
                    "authoredDate": older_date.isoformat(),
                    "author": {"user": {"login": "user0"}},
                }
            ]
            * 5
        )  # Make 25

        vcs_data = _vcs_with_commits(recent_commits + older_commits)
        result = check_maintainer_drain(vcs_data)
        assert result.name == "Maintainer Retention"
        assert result.score == 5
        assert result.max_score == 10
        assert "Monitor: 50% reduction in maintainers" in result.message
        assert result.risk == "Medium"

    def test_maintainer_drain_stable(self):
        """Test with stable maintainer retention."""
        # 8 recent contributors, 8 older
        recent_commits = []
        for i in range(8):
            recent_commits.extend([{"author": {"user": {"login": f"user{i}"}}}] * 3)
        recent_commits.extend([{"author": {"user": {"login": "user0"}}}] * 1)  # Make 25

        older_commits = []
        for i in range(8):
            older_commits.extend([{"author": {"user": {"login": f"user{i}"}}}] * 3)
        older_commits.extend([{"author": {"user": {"login": "user0"}}}] * 1)  # Make 25

        vcs_data = _vcs_with_commits(recent_commits + older_commits)
        result = check_maintainer_drain(vcs_data)
        assert result.name == "Maintainer Retention"
        assert result.score == 10
        assert result.max_score == 10
        assert "Stable: 8 active maintainers" in result.message
        assert result.risk == "None"
