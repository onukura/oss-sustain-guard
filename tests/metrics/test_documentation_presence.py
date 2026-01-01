"""
Tests for the documentation_presence metric.
"""

from oss_sustain_guard.metrics.documentation_presence import (
    check_documentation_presence,
)


class TestDocumentationPresenceMetric:
    """Test the check_documentation_presence metric function."""

    def test_documentation_all_present(self):
        """Test when all documentation signals are present."""
        repo_data = {
            "readmeUpperCase": {"byteSize": 1000},
            "contributingFile": {"byteSize": 500},
            "hasWikiEnabled": True,
            "homepageUrl": "https://example.com",
            "description": "A great project description",
        }
        result = check_documentation_presence(repo_data)
        assert result.name == "Documentation Presence"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: 5/5 documentation signals present" in result.message
        assert result.risk == "None"

    def test_documentation_three_signals(self):
        """Test with three documentation signals."""
        repo_data = {
            "readmeUpperCase": {"byteSize": 1000},
            "contributingFile": {"byteSize": 500},
            "hasWikiEnabled": True,
            "description": "A great project description",
        }
        result = check_documentation_presence(repo_data)
        assert result.name == "Documentation Presence"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: 4/5 documentation signals present" in result.message
        assert result.risk == "None"

    def test_documentation_readme_plus_two(self):
        """Test with README and two other signals."""
        repo_data = {
            "readmeUpperCase": {"byteSize": 1000},
            "contributingFile": {"byteSize": 500},
            "homepageUrl": "https://example.com",
        }
        result = check_documentation_presence(repo_data)
        assert result.name == "Documentation Presence"
        assert result.score == 7
        assert result.max_score == 10
        assert "Good: 3/5 documentation signals present" in result.message
        assert result.risk == "Low"

    def test_documentation_readme_only(self):
        """Test with only README present."""
        repo_data = {"readmeUpperCase": {"byteSize": 1000}}
        result = check_documentation_presence(repo_data)
        assert result.name == "Documentation Presence"
        assert result.score == 4
        assert result.max_score == 10
        assert "Basic: Only README detected" in result.message
        assert result.risk == "Medium"

    def test_documentation_none(self):
        """Test with no documentation."""
        repo_data = {}
        result = check_documentation_presence(repo_data)
        assert result.name == "Documentation Presence"
        assert result.score == 0
        assert result.max_score == 10
        assert "No README or documentation found" in result.message
        assert result.risk == "High"

    def test_documentation_small_readme_symlink(self):
        """Test with small README that might be a symlink."""
        repo_data = {
            "readmeUpperCase": {"byteSize": 50, "text": "packages/docs/README.md"}
        }
        result = check_documentation_presence(repo_data)
        assert result.name == "Documentation Presence"
        assert result.score == 4
        assert result.max_score == 10
        assert "Basic: Only README detected" in result.message
        assert result.risk == "Medium"
