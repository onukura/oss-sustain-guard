"""
Tests for the code_of_conduct metric.
"""

from oss_sustain_guard.metrics.code_of_conduct import check_code_of_conduct
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


class TestCodeOfConductMetric:
    """Test the check_code_of_conduct metric function."""

    def test_code_of_conduct_present(self):
        """Test when Code of Conduct is present."""
        vcs_data = _vcs_data(code_of_conduct={"name": "Contributor Covenant"})
        result = check_code_of_conduct(vcs_data)
        assert result.name == "Code of Conduct"
        assert result.score == 10
        assert result.max_score == 10
        assert (
            "Excellent: Code of Conduct present (Contributor Covenant)"
            in result.message
        )
        assert result.risk == "None"

    def test_code_of_conduct_absent(self):
        """Test when Code of Conduct is absent."""
        vcs_data = _vcs_data()
        result = check_code_of_conduct(vcs_data)
        assert result.name == "Code of Conduct"
        assert result.score == 0
        assert result.max_score == 10
        assert "No Code of Conduct detected" in result.message
        assert result.risk == "Low"

    def test_code_of_conduct_empty(self):
        """Test when codeOfConduct exists but has no name."""
        vcs_data = _vcs_data(code_of_conduct={})
        result = check_code_of_conduct(vcs_data)
        assert result.name == "Code of Conduct"
        assert result.score == 0
        assert result.max_score == 10
        assert "No Code of Conduct detected" in result.message
        assert result.risk == "Low"
