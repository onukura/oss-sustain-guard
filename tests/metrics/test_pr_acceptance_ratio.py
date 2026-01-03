"""Tests for PR acceptance ratio metric."""

from oss_sustain_guard.metrics.pr_acceptance_ratio import check_pr_acceptance_ratio
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


class TestPrAcceptanceRatio:
    """Test PR acceptance ratio metric."""

    def test_no_resolved_prs(self):
        """Test with no resolved PRs."""
        vcs_data = _vcs_data(total_merged_prs=0, closed_prs=[])
        result = check_pr_acceptance_ratio(vcs_data)
        assert result.score == 5
        assert result.max_score == 10
        assert "No resolved pull requests" in result.message
        assert result.risk == "None"

    def test_very_welcoming(self):
        """Test very welcoming acceptance rate."""
        closed_prs = [{"merged": False} for _ in range(20)]
        vcs_data = _vcs_data(total_merged_prs=80, closed_prs=closed_prs)
        result = check_pr_acceptance_ratio(vcs_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_good_acceptance(self):
        """Test good acceptance rate."""
        closed_prs = [{"merged": False} for _ in range(30)]
        vcs_data = _vcs_data(total_merged_prs=70, closed_prs=closed_prs)
        result = check_pr_acceptance_ratio(vcs_data)
        assert result.score == 7
        assert result.max_score == 10
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_moderate_acceptance(self):
        """Test moderate acceptance rate."""
        closed_prs = [{"merged": False} for _ in range(50)]
        vcs_data = _vcs_data(total_merged_prs=50, closed_prs=closed_prs)
        result = check_pr_acceptance_ratio(vcs_data)
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_needs_attention(self):
        """Test low acceptance rate that needs attention."""
        closed_prs = [{"merged": False} for _ in range(70)]
        vcs_data = _vcs_data(total_merged_prs=30, closed_prs=closed_prs)
        result = check_pr_acceptance_ratio(vcs_data)
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe" in result.message
        assert result.risk == "Medium"
