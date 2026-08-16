"""
Tests for the bus_factor metric.
"""

import oss_sustain_guard.metrics.bus_factor as bus_factor
from oss_sustain_guard.metrics.base import MetricContext
from oss_sustain_guard.metrics.bus_factor import METRIC, check_bus_factor
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
    logins: list[str],
    total_count: int | None = None,
    default_branch: str | None = "main",
) -> VCSRepositoryData:
    commits = [{"author": {"user": {"login": login}}} for login in logins]
    total_commits = total_count if total_count is not None else len(commits)
    return _vcs_data(
        commits=commits,
        total_commits=total_commits,
        default_branch=default_branch,
    )


class TestBusFactorMetric:
    """Test the check_bus_factor metric function."""

    def test_bus_factor_no_default_branch(self):
        """Test when default branch is not available."""
        vcs_data = _vcs_data(default_branch=None)
        result = check_bus_factor(vcs_data)
        assert result.name == "Contributor Redundancy"
        assert result.score == 0
        assert result.max_score == 10
        assert "Commit history data not available" in result.message
        assert result.risk == "High"

    def test_bus_factor_no_target(self):
        """Test when default branch has no target."""
        vcs_data = _vcs_data(default_branch=None)
        result = check_bus_factor(vcs_data)
        assert result.name == "Contributor Redundancy"
        assert result.score == 0
        assert result.max_score == 10
        assert "Commit history data not available" in result.message
        assert result.risk == "High"

    def test_bus_factor_no_history(self):
        """Test when no commit history is available."""
        vcs_data = _vcs_data(commits=[])
        result = check_bus_factor(vcs_data)
        assert result.name == "Contributor Redundancy"
        assert result.score == 0
        assert result.max_score == 10
        assert "No commit history available for analysis" in result.message
        assert result.risk == "Critical"

    def test_bus_factor_single_contributor_high_percentage(self):
        """Test with single contributor having high percentage."""
        vcs_data = _vcs_with_commits(["user1"] * 5)
        result = check_bus_factor(vcs_data)
        assert result.name == "Contributor Redundancy"
        assert result.score == 5  # New project: 100% by single author
        assert result.max_score == 10
        assert (
            "Estimated from public contributions: 100% by single author"
            in result.message
        )
        assert result.risk == "Medium"

    def test_bus_factor_healthy_diversity(self):
        """Test with healthy contributor diversity."""
        vcs_data = _vcs_with_commits(["user1", "user2", "user3", "user4", "user5"])
        result = check_bus_factor(vcs_data)
        assert result.name == "Contributor Redundancy"
        assert result.score == 10
        assert result.max_score == 10
        assert (
            "Estimated from public contributions: Healthy diversity" in result.message
        )
        assert result.risk == "None"

    def test_bus_factor_only_bots(self):
        """Test when only bot commits are present."""
        vcs_data = _vcs_with_commits(["dependabot[bot]", "github-actions"])
        result = check_bus_factor(vcs_data)
        assert result.score == 0
        assert "No human contributors found" in result.message
        assert result.risk == "Critical"

    def test_bus_factor_with_merged_prs_users(self):
        """Test that PR mergers are counted as contributors."""
        # 1 commit by user1
        # 1 PR merged by user2
        vcs_data = _vcs_with_commits(["user1"])
        # Manually add merged PRs to the data structure since helper doesn't support it directly
        merged_prs = [{"mergedBy": {"login": "user2"}}]
        vcs_data = vcs_data._replace(merged_prs=merged_prs)

        result = check_bus_factor(vcs_data)
        # 2 active contributors total (user1, user2), 50% each
        # 50% => 8/10 score (Medium risk)
        assert result.score == 8
        assert (
            "Estimated from public contributions: 50% by top contributor"
            in result.message
        )
        assert "2 contributor(s) total" in result.message

    def test_bus_factor_mature_bdfl(self):
        """Test BDFL model detection for mature projects."""
        vcs_data = _vcs_with_commits(["founder"] * 10, total_count=1500)
        result = check_bus_factor(vcs_data)
        assert result.score == 8
        assert "Estimated from public contributions" in result.message
        assert "May have internal redundancy" in result.message
        assert result.risk == "Low"

    def test_bus_factor_mature_high_concentration(self):
        """Test high concentration for mature but non-BDFL projects."""
        vcs_data = _vcs_with_commits(["user1"] * 9 + ["user2"], total_count=200)
        result = check_bus_factor(vcs_data)
        assert result.score == 2
        assert "Estimated from public contributions: 90%" in result.message
        assert result.risk == "High"

    def test_bus_factor_high_concentration(self):
        """Test high concentration without maturity threshold."""
        vcs_data = _vcs_with_commits(
            ["user1"] * 7 + ["user2"] * 2 + ["user3"], total_count=50
        )
        result = check_bus_factor(vcs_data)
        assert result.score == 5
        assert "Estimated from public contributions: 70%" in result.message
        assert result.risk == "High"

    def test_bus_factor_medium_concentration(self):
        """Test medium concentration without maturity threshold."""
        vcs_data = _vcs_with_commits(["user1"] * 6 + ["user2"] * 4, total_count=80)
        result = check_bus_factor(vcs_data)
        assert result.score == 8
        assert (
            "Estimated from public contributions: 60% by top contributor"
            in result.message
        )
        assert result.risk == "Medium"

    def test_bus_factor_total_commits_zero(self, monkeypatch):
        """Test handling of zero total commits after filtering."""
        repo_data = _vcs_with_commits(["user1"])
        monkeypatch.setattr(bus_factor, "sum", lambda values: 0, raising=False)
        result = check_bus_factor(repo_data)
        assert result.score == 0
        assert "No commits found" in result.message
        assert result.risk == "Critical"

    def test_bus_factor_metric_spec_checker(self):
        """Test MetricSpec checker delegates to the metric function."""
        repo_data = _vcs_with_commits(["user1", "user2"])
        context = MetricContext(owner="owner", name="repo", repo_url="url")
        result = METRIC.checker.check(repo_data, context)
        assert result is not None
        assert result.name == "Contributor Redundancy"

    def test_bus_factor_metric_spec_on_error(self):
        """Test MetricSpec error handler formatting."""
        if METRIC.on_error is not None:
            result = METRIC.on_error(RuntimeError("boom"))
            assert result is not None
            assert result.score == 0
            assert "Analysis incomplete" in result.message
