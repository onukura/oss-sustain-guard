"""
Tests for the code_of_conduct metric.
"""

from oss_sustain_guard.metrics.code_of_conduct import check_code_of_conduct


class TestCodeOfConductMetric:
    """Test the check_code_of_conduct metric function."""

    def test_code_of_conduct_present(self):
        """Test when Code of Conduct is present."""
        repo_data = {"codeOfConduct": {"name": "Contributor Covenant"}}
        result = check_code_of_conduct(repo_data)
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
        repo_data = {}
        result = check_code_of_conduct(repo_data)
        assert result.name == "Code of Conduct"
        assert result.score == 0
        assert result.max_score == 10
        assert "No Code of Conduct detected" in result.message
        assert result.risk == "Low"

    def test_code_of_conduct_empty(self):
        """Test when codeOfConduct exists but has no name."""
        repo_data = {"codeOfConduct": {}}
        result = check_code_of_conduct(repo_data)
        assert result.name == "Code of Conduct"
        assert result.score == 0
        assert result.max_score == 10
        assert "No Code of Conduct detected" in result.message
        assert result.risk == "Low"
