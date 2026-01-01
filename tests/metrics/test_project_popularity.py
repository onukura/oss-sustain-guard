"""
Tests for the project_popularity metric.
"""

from oss_sustain_guard.metrics.project_popularity import check_project_popularity


class TestProjectPopularityMetric:
    """Test the check_project_popularity metric function."""

    def test_project_popularity_very_popular(self):
        """Test with 1000+ stars."""
        repo_data = {"stargazerCount": 1500, "watchers": {"totalCount": 200}}
        result = check_project_popularity(repo_data)
        assert result.name == "Project Popularity"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: ⭐ 1500 stars, 200 watchers. Very popular" in result.message
        assert result.risk == "None"

    def test_project_popularity_popular(self):
        """Test with 500-999 stars."""
        repo_data = {"stargazerCount": 750, "watchers": {"totalCount": 100}}
        result = check_project_popularity(repo_data)
        assert result.name == "Project Popularity"
        assert result.score == 8
        assert result.max_score == 10
        assert "Popular: ⭐ 750 stars, 100 watchers" in result.message
        assert result.risk == "None"

    def test_project_popularity_growing(self):
        """Test with 100-499 stars."""
        repo_data = {"stargazerCount": 250, "watchers": {"totalCount": 50}}
        result = check_project_popularity(repo_data)
        assert result.name == "Project Popularity"
        assert result.score == 6
        assert result.max_score == 10
        assert "Growing: ⭐ 250 stars, 50 watchers. Active interest" in result.message
        assert result.risk == "None"

    def test_project_popularity_emerging(self):
        """Test with 50-99 stars."""
        repo_data = {"stargazerCount": 75, "watchers": {"totalCount": 20}}
        result = check_project_popularity(repo_data)
        assert result.name == "Project Popularity"
        assert result.score == 4
        assert result.max_score == 10
        assert "Emerging: ⭐ 75 stars. Building community" in result.message
        assert result.risk == "Low"

    def test_project_popularity_early(self):
        """Test with 10-49 stars."""
        repo_data = {"stargazerCount": 25, "watchers": {"totalCount": 10}}
        result = check_project_popularity(repo_data)
        assert result.name == "Project Popularity"
        assert result.score == 2
        assert result.max_score == 10
        assert "Early: ⭐ 25 stars. New or niche project" in result.message
        assert result.risk == "Low"

    def test_project_popularity_new(self):
        """Test with <10 stars."""
        repo_data = {"stargazerCount": 5, "watchers": {"totalCount": 2}}
        result = check_project_popularity(repo_data)
        assert result.name == "Project Popularity"
        assert result.score == 0
        assert result.max_score == 10
        assert "Note: ⭐ 5 stars. Very new or specialized project" in result.message
        assert result.risk == "Low"

    def test_project_popularity_no_data(self):
        """Test with no star data."""
        repo_data = {}
        result = check_project_popularity(repo_data)
        assert result.name == "Project Popularity"
        assert result.score == 0
        assert result.max_score == 10
        assert "Note: ⭐ 0 stars. Very new or specialized project" in result.message
        assert result.risk == "Low"
