"""
Tests for the license_clarity metric.
"""

from oss_sustain_guard.metrics.license_clarity import check_license_clarity


class TestLicenseClarityMetric:
    """Test the check_license_clarity metric function."""

    def test_license_clarity_no_license(self):
        """Test when no license is detected."""
        repo_data = {}
        result = check_license_clarity(repo_data)
        assert result.name == "License Clarity"
        assert result.score == 0
        assert result.max_score == 10
        assert "No license detected" in result.message
        assert result.risk == "High"

    def test_license_clarity_osi_approved(self):
        """Test with OSI-approved license."""
        repo_data = {"licenseInfo": {"name": "MIT License", "spdxId": "MIT"}}
        result = check_license_clarity(repo_data)
        assert result.name == "License Clarity"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: MIT License (OSI-approved)" in result.message
        assert result.risk == "None"

    def test_license_clarity_other_spdx(self):
        """Test with other SPDX license."""
        repo_data = {
            "licenseInfo": {"name": "Custom License", "spdxId": "LicenseRef-custom"}
        }
        result = check_license_clarity(repo_data)
        assert result.name == "License Clarity"
        assert result.score == 6
        assert result.max_score == 10
        assert "Good: Custom License detected" in result.message
        assert result.risk == "Low"

    def test_license_clarity_no_spdx(self):
        """Test with license but no SPDX ID."""
        repo_data = {"licenseInfo": {"name": "Unknown License"}}
        result = check_license_clarity(repo_data)
        assert result.name == "License Clarity"
        assert result.score == 4
        assert result.max_score == 10
        assert "Note: Unknown License detected" in result.message
        assert result.risk == "Medium"
