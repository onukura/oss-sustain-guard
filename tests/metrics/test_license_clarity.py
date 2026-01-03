"""
Tests for the license_clarity metric.
"""

from oss_sustain_guard.metrics.license_clarity import check_license_clarity
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


class TestLicenseClarityMetric:
    """Test the check_license_clarity metric function."""

    def test_license_clarity_no_license(self):
        """Test when no license is detected."""
        vcs_data = _vcs_data()
        result = check_license_clarity(vcs_data)
        assert result.name == "License Clarity"
        assert result.score == 0
        assert result.max_score == 10
        assert "No license detected" in result.message
        assert result.risk == "High"

    def test_license_clarity_osi_approved(self):
        """Test with OSI-approved license."""
        vcs_data = _vcs_data(license_info={"name": "MIT License", "spdxId": "MIT"})
        result = check_license_clarity(vcs_data)
        assert result.name == "License Clarity"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: MIT License (OSI-approved)" in result.message
        assert result.risk == "None"

    def test_license_clarity_other_spdx(self):
        """Test with other SPDX license."""
        vcs_data = _vcs_data(
            license_info={"name": "Custom License", "spdxId": "LicenseRef-custom"}
        )
        result = check_license_clarity(vcs_data)
        assert result.name == "License Clarity"
        assert result.score == 6
        assert result.max_score == 10
        assert "Good: Custom License detected" in result.message
        assert result.risk == "Low"

    def test_license_clarity_no_spdx(self):
        """Test with license but no SPDX ID."""
        vcs_data = _vcs_data(license_info={"name": "Unknown License"})
        result = check_license_clarity(vcs_data)
        assert result.name == "License Clarity"
        assert result.score == 4
        assert result.max_score == 10
        assert "Note: Unknown License detected" in result.message
        assert result.risk == "Medium"
