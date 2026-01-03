"""
Tests for the documentation_presence metric.
"""

from oss_sustain_guard.metrics.documentation_presence import (
    check_documentation_presence,
)
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


class TestDocumentationPresenceMetric:
    """Test the check_documentation_presence metric function."""

    def test_documentation_all_present(self):
        """Test when all documentation signals are present."""
        vcs_data = _vcs_data(
            readme_size=1000,
            contributing_file_size=500,
            has_wiki=True,
            homepage_url="https://example.com",
            description="A great project description",
        )
        result = check_documentation_presence(vcs_data)
        assert result.name == "Documentation Presence"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: 5/5 documentation signals present" in result.message
        assert result.risk == "None"

    def test_documentation_three_signals(self):
        """Test with three documentation signals."""
        vcs_data = _vcs_data(
            readme_size=1000,
            contributing_file_size=500,
            has_wiki=True,
            description="A great project description",
        )
        result = check_documentation_presence(vcs_data)
        assert result.name == "Documentation Presence"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: 4/5 documentation signals present" in result.message
        assert result.risk == "None"

    def test_documentation_readme_plus_two(self):
        """Test with README and two other signals."""
        vcs_data = _vcs_data(
            readme_size=1000,
            contributing_file_size=500,
            homepage_url="https://example.com",
        )
        result = check_documentation_presence(vcs_data)
        assert result.name == "Documentation Presence"
        assert result.score == 7
        assert result.max_score == 10
        assert "Good: 3/5 documentation signals present" in result.message
        assert result.risk == "Low"

    def test_documentation_readme_only(self):
        """Test with only README present."""
        vcs_data = _vcs_data(readme_size=1000)
        result = check_documentation_presence(vcs_data)
        assert result.name == "Documentation Presence"
        assert result.score == 4
        assert result.max_score == 10
        assert "Basic: Only README detected" in result.message
        assert result.risk == "Medium"

    def test_documentation_none(self):
        """Test with no documentation."""
        vcs_data = _vcs_data()
        result = check_documentation_presence(vcs_data)
        assert result.name == "Documentation Presence"
        assert result.score == 0
        assert result.max_score == 10
        assert "No README or documentation found" in result.message
        assert result.risk == "High"

    def test_documentation_small_readme_symlink(self):
        """Test with small README that might be a symlink."""
        vcs_data = _vcs_data(
            raw_data={
                "readmeUpperCase": {
                    "byteSize": 50,
                    "text": "packages/docs/README.md",
                }
            }
        )
        result = check_documentation_presence(vcs_data)
        assert result.name == "Documentation Presence"
        assert result.score == 4
        assert result.max_score == 10
        assert "Basic: Only README detected" in result.message
        assert result.risk == "Medium"
