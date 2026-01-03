"""
Tests for the funding metric.
"""

from oss_sustain_guard.metrics.funding import check_funding, is_corporate_backed
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


class TestFundingMetric:
    """Test the check_funding metric function."""

    def test_is_corporate_backed_organization(self):
        """Test detection of organization-owned repository."""
        repo_data = _vcs_data(owner_type="Organization", owner_login="microsoft")
        assert is_corporate_backed(repo_data) is True

    def test_is_corporate_backed_user(self):
        """Test detection of user-owned repository."""
        repo_data = _vcs_data(owner_type="User", owner_login="johndoe")
        assert is_corporate_backed(repo_data) is False

    def test_is_corporate_backed_no_owner(self):
        """Test when owner data is missing."""
        repo_data = {}
        assert is_corporate_backed(repo_data) is False

    def test_funding_corporate_with_funding_links(self):
        """Test corporate-backed repository with funding links."""
        vcs_data = _vcs_data(
            owner_type="Organization",
            owner_login="microsoft",
            funding_links=["https://github.com/sponsors/microsoft"],
        )
        result = check_funding(vcs_data)
        assert result.name == "Funding Signals"
        assert result.score == 10
        assert result.max_score == 10
        assert (
            "Well-supported: microsoft organization + 1 funding link" in result.message
        )
        assert result.risk == "None"

    def test_funding_corporate_without_funding_links(self):
        """Test corporate-backed repository without funding links."""
        vcs_data = _vcs_data(
            owner_type="Organization",
            owner_login="google",
            funding_links=[],
        )
        result = check_funding(vcs_data)
        assert result.name == "Funding Signals"
        assert result.score == 10
        assert result.max_score == 10
        assert "Well-supported: Organization maintained by google" in result.message
        assert result.risk == "None"

    def test_funding_community_with_funding_links(self):
        """Test community-driven repository with funding links."""
        vcs_data = _vcs_data(
            owner_type="User",
            owner_login="johndoe",
            funding_links=["https://github.com/sponsors/johndoe"],
        )
        result = check_funding(vcs_data)
        assert result.name == "Funding Signals"
        assert result.score == 8
        assert result.max_score == 10
        assert "Community-funded: 1 funding link" in result.message
        assert result.risk == "None"

    def test_funding_community_without_funding_links(self):
        """Test community-driven repository without funding links."""
        vcs_data = _vcs_data(
            owner_type="User",
            owner_login="johndoe",
            funding_links=[],
        )
        result = check_funding(vcs_data)
        assert result.name == "Funding Signals"
        assert result.score == 0
        assert result.max_score == 10
        assert "No funding sources detected" in result.message
        assert result.risk == "Low"
