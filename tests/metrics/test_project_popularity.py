"""
Tests for the project_popularity metric.
"""

from oss_sustain_guard.metrics.project_popularity import check_project_popularity
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


class TestProjectPopularityMetric:
    """Test the check_project_popularity metric function."""

    def test_project_popularity_very_popular(self):
        """Test with 1000+ stars."""
        vcs_data = _vcs_data(star_count=1500, watchers_count=200)
        result = check_project_popularity(vcs_data)
        assert result.name == "Project Popularity"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: ⭐ 1500 stars, 200 watchers. Very popular" in result.message
        assert result.risk == "None"

    def test_project_popularity_popular(self):
        """Test with 500-999 stars."""
        vcs_data = _vcs_data(star_count=750, watchers_count=100)
        result = check_project_popularity(vcs_data)
        assert result.name == "Project Popularity"
        assert result.score == 8
        assert result.max_score == 10
        assert "Popular: ⭐ 750 stars, 100 watchers" in result.message
        assert result.risk == "None"

    def test_project_popularity_growing(self):
        """Test with 100-499 stars."""
        vcs_data = _vcs_data(star_count=250, watchers_count=50)
        result = check_project_popularity(vcs_data)
        assert result.name == "Project Popularity"
        assert result.score == 6
        assert result.max_score == 10
        assert "Growing: ⭐ 250 stars, 50 watchers. Active interest" in result.message
        assert result.risk == "None"

    def test_project_popularity_emerging(self):
        """Test with 50-99 stars."""
        vcs_data = _vcs_data(star_count=75, watchers_count=20)
        result = check_project_popularity(vcs_data)
        assert result.name == "Project Popularity"
        assert result.score == 4
        assert result.max_score == 10
        assert "Emerging: ⭐ 75 stars. Building community" in result.message
        assert result.risk == "Low"

    def test_project_popularity_early(self):
        """Test with 10-49 stars."""
        vcs_data = _vcs_data(star_count=25, watchers_count=10)
        result = check_project_popularity(vcs_data)
        assert result.name == "Project Popularity"
        assert result.score == 2
        assert result.max_score == 10
        assert "Early: ⭐ 25 stars. New or niche project" in result.message
        assert result.risk == "Low"

    def test_project_popularity_new(self):
        """Test with <10 stars."""
        vcs_data = _vcs_data(star_count=5, watchers_count=2)
        result = check_project_popularity(vcs_data)
        assert result.name == "Project Popularity"
        assert result.score == 0
        assert result.max_score == 10
        assert "Note: ⭐ 5 stars. Very new or specialized project" in result.message
        assert result.risk == "Low"

    def test_project_popularity_no_data(self):
        """Test with no star data."""
        vcs_data = _vcs_data()
        result = check_project_popularity(vcs_data)
        assert result.name == "Project Popularity"
        assert result.score == 0
        assert result.max_score == 10
        assert "Note: ⭐ 0 stars. Very new or specialized project" in result.message
        assert result.risk == "Low"
