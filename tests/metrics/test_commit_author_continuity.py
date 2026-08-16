"""
Tests for the commit_author_continuity metric.
"""

from datetime import datetime, timedelta, timezone

from oss_sustain_guard.metrics.commit_author_continuity import (
    METRIC_NAME,
    check_commit_author_continuity,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

NOW = datetime.now(timezone.utc)


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
    merged_prs: list[dict] | None = None,
) -> VCSRepositoryData:
    commit_total = total_commits if total_commits is not None else len(commits)
    return _vcs_data(
        commits=commits,
        total_commits=commit_total,
        default_branch=default_branch,
        merged_prs=merged_prs or [],
    )


def _commits(
    login: str, days_ago: int, count: int, email: str | None = None
) -> list[dict]:
    """Build `count` commits authored `days_ago` days ago by `login`."""
    author: dict = {"user": {"login": login}} if login else {"user": None}
    if email is not None:
        author["email"] = email
    return [
        {
            "authoredDate": (NOW - timedelta(days=days_ago)).isoformat(),
            "author": author,
        }
        for _ in range(count)
    ]


def _email_commits(email: str, days_ago: int, count: int) -> list[dict]:
    """Build commits with no linked account, identified only by email."""
    return [
        {
            "authoredDate": (NOW - timedelta(days=days_ago)).isoformat(),
            "author": {"user": None, "email": email},
        }
        for _ in range(count)
    ]


def _merged_pr(login: str, days_ago: int) -> dict:
    return {
        "mergedAt": (NOW - timedelta(days=days_ago)).isoformat(),
        "mergedBy": {"login": login},
    }


class TestCommitAuthorContinuityMetric:
    """Test the check_commit_author_continuity metric function."""

    def test_no_default_branch(self):
        """Data unavailable is not penalized."""
        result = check_commit_author_continuity(_vcs_data(default_branch=None))
        assert result.name == METRIC_NAME
        assert result.score == 10
        assert "not available" in result.message
        assert result.risk == "None"

    def test_no_commit_timestamps(self):
        """Commits without dates cannot be windowed, so they are not penalized."""
        result = check_commit_author_continuity(
            _vcs_with_commits([{"author": {"user": {"login": "user1"}}}] * 50)
        )
        assert result.score == 10
        assert "timestamps not available" in result.message
        assert result.risk == "None"

    def test_dormant_project_is_penalized(self):
        """Regression test for issue #11: a stale sample must not read as healthy.

        50 commits by 8 authors, all 300-500 days old — the shape that used to
        score 10/10 with "Stable: 8 active maintainers".
        """
        commits = []
        for i in range(8):
            commits.extend(_commits(f"user{i}", 300 + i * 20, 6))
        result = check_commit_author_continuity(_vcs_with_commits(commits))
        assert result.score == 3
        assert result.risk == "High"
        assert "no human commit or merge" in result.message
        assert result.metadata is not None
        assert result.metadata["days_since_last_activity"] == 300

    def test_abandoned_project_is_critical(self):
        """No human activity for over a year."""
        result = check_commit_author_continuity(
            _vcs_with_commits(_commits("user1", 500, 30))
        )
        assert result.score == 0
        assert result.risk == "Critical"
        assert "Needs support" in result.message

    def test_stable_principal_committers(self):
        """The people carrying the project in the previous window are still there."""
        commits = _commits("lead", 30, 12) + _commits("second", 60, 8)
        commits += _commits("lead", 250, 12) + _commits("second", 300, 8)
        result = check_commit_author_continuity(_vcs_with_commits(commits))
        assert result.score == 10
        assert result.risk == "None"
        assert "Stable: 1/1 principal committer(s)" in result.message
        assert result.metadata is not None
        assert result.metadata["continuity_rate"] == 100

    def test_principal_committer_lost_while_drive_by_commits_continue(self):
        """The inverted signal from issue #11: more authors, but the lead is gone.

        The previous window is carried by one lead; the recent window has three
        one-off contributors instead. Author head count went up, health did not.
        """
        commits = []
        for i in range(3):
            commits.extend(_commits(f"drive-by{i}", 30 + i * 10, 1))
        commits += _commits("lead", 250, 20)
        result = check_commit_author_continuity(_vcs_with_commits(commits))
        assert result.score == 0
        assert result.risk == "Critical"
        assert "none of the 1 principal committer(s)" in result.message

    def test_partial_retention_is_monitored(self):
        """One of two principal committers remains."""
        commits = _commits("lead", 30, 10)
        commits += _commits("lead", 250, 10) + _commits("second", 260, 10)
        result = check_commit_author_continuity(_vcs_with_commits(commits))
        assert result.score == 7
        assert result.risk == "Low"
        assert "only 1/2 principal committer(s)" in result.message

    def test_low_retention_needs_attention(self):
        """Only one of the previous window's principal committers remains.

        Four authors split the previous window evenly, so the smallest set
        holding a majority of its commits is three of them.
        """
        commits = _commits("a", 30, 5)
        for index, login in enumerate(["a", "b", "c", "d"]):
            commits += _commits(login, 250 + index, 5)
        result = check_commit_author_continuity(_vcs_with_commits(commits))
        assert result.score == 4
        assert result.risk == "Medium"
        assert "only 1/3 principal committer(s)" in result.message

    def test_handover_is_not_treated_as_drain(self):
        """New maintainers replaced the old ones at a comparable commit volume."""
        commits = _commits("newlead", 30, 18) + _commits("old", 250, 20)
        result = check_commit_author_continuity(_vcs_with_commits(commits))
        assert result.score == 5
        assert result.risk == "Medium"
        assert "Handover" in result.message

    def test_pr_merge_counts_as_maintainer_activity(self):
        """A maintainer who shifted from committing to merging is still retained."""
        commits = _commits("contributor", 30, 4) + _commits("lead", 250, 20)
        result = check_commit_author_continuity(
            _vcs_with_commits(commits, merged_prs=[_merged_pr("lead", 20)])
        )
        assert result.score == 10
        assert "Stable: 1/1 principal committer(s)" in result.message

    def test_shallow_sample_is_not_penalized(self):
        """A busy project's sample can end inside the comparison window."""
        commits = _commits("lead", 10, 40) + _commits("second", 20, 40)
        result = check_commit_author_continuity(_vcs_with_commits(commits))
        assert result.score == 10
        assert result.risk == "None"
        assert "Commit sample starts" in result.message

    def test_new_project_is_not_penalized(self):
        """History reaches back far enough, but the project only just started."""
        commits = _commits("founder", 10, 20) + _commits("founder", 400, 1)
        result = check_commit_author_continuity(_vcs_with_commits(commits))
        assert result.score == 10
        assert result.risk == "None"
        assert "Too little activity" in result.message

    def test_bots_are_excluded(self):
        """A recent window carried only by bots is not maintainer activity."""
        commits = _commits("dependabot[bot]", 30, 20) + _commits("lead", 250, 20)
        result = check_commit_author_continuity(_vcs_with_commits(commits))
        assert result.score == 3
        assert result.risk == "High"
        assert "no human commit or merge" in result.message

    def test_email_only_commits_are_merged_into_the_login(self):
        """The same person must not count as two identities.

        `lead` commits with a linked account and, in the recent window, with a
        bare email. Without canonicalization the email would look like a
        different person and the lead would read as gone.
        """
        commits = _email_commits("lead@example.com", 30, 10)
        commits += _commits("lead", 250, 20, email="lead@example.com")
        result = check_commit_author_continuity(_vcs_with_commits(commits))
        assert result.score == 10
        assert "Stable: 1/1 principal committer(s)" in result.message


class TestDeprecatedAlias:
    """The pre-v0.26.0 import path must keep working."""

    def test_check_maintainer_drain_delegates(self):
        from oss_sustain_guard.metrics.maintainer_drain import (
            METRIC,
            check_maintainer_drain,
        )

        result = check_maintainer_drain(_vcs_data(default_branch=None))
        assert result.name == METRIC_NAME
        assert METRIC.name == METRIC_NAME
