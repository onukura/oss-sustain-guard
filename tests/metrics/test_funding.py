"""
Tests for the funding metric.
"""

from oss_sustain_guard.metrics.funding import check_funding, is_corporate_backed


class TestFundingMetric:
    """Test the check_funding metric function."""

    def test_is_corporate_backed_organization(self):
        """Test detection of organization-owned repository."""
        repo_data = {"owner": {"__typename": "Organization", "login": "microsoft"}}
        assert is_corporate_backed(repo_data) is True

    def test_is_corporate_backed_user(self):
        """Test detection of user-owned repository."""
        repo_data = {"owner": {"__typename": "User", "login": "johndoe"}}
        assert is_corporate_backed(repo_data) is False

    def test_is_corporate_backed_no_owner(self):
        """Test when owner data is missing."""
        repo_data = {}
        assert is_corporate_backed(repo_data) is False

    def test_funding_corporate_with_funding_links(self):
        """Test corporate-backed repository with funding links."""
        repo_data = {
            "owner": {"__typename": "Organization", "login": "microsoft"},
            "fundingLinks": ["https://github.com/sponsors/microsoft"],
        }
        result = check_funding(repo_data)
        assert result.name == "Funding Signals"
        assert result.score == 10
        assert result.max_score == 10
        assert (
            "Well-supported: microsoft organization + 1 funding link" in result.message
        )
        assert result.risk == "None"

    def test_funding_corporate_without_funding_links(self):
        """Test corporate-backed repository without funding links."""
        repo_data = {
            "owner": {"__typename": "Organization", "login": "google"},
            "fundingLinks": [],
        }
        result = check_funding(repo_data)
        assert result.name == "Funding Signals"
        assert result.score == 10
        assert result.max_score == 10
        assert "Well-supported: Organization maintained by google" in result.message
        assert result.risk == "None"

    def test_funding_community_with_funding_links(self):
        """Test community-driven repository with funding links."""
        repo_data = {
            "owner": {"__typename": "User", "login": "johndoe"},
            "fundingLinks": ["https://github.com/sponsors/johndoe"],
        }
        result = check_funding(repo_data)
        assert result.name == "Funding Signals"
        assert result.score == 8
        assert result.max_score == 10
        assert "Community-funded: 1 funding link" in result.message
        assert result.risk == "None"

    def test_funding_community_without_funding_links(self):
        """Test community-driven repository without funding links."""
        repo_data = {
            "owner": {"__typename": "User", "login": "johndoe"},
            "fundingLinks": [],
        }
        result = check_funding(repo_data)
        assert result.name == "Funding Signals"
        assert result.score == 0
        assert result.max_score == 10
        assert "No funding sources detected" in result.message
        assert result.risk == "Low"
