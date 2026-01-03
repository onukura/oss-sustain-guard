"""
Tests for the release_cadence metric.
"""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.release_cadence import check_release_cadence
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


class TestReleaseCadenceMetric:
    """Test the check_release_cadence metric function."""

    def test_release_cadence_archived(self):
        """Test when repository is archived."""
        vcs_data = _vcs_data(is_archived=True)
        result = check_release_cadence(vcs_data)
        assert result.name == "Release Rhythm"
        assert result.score == 10
        assert result.max_score == 10
        assert "Archived repository" in result.message
        assert result.risk == "None"

    def test_release_cadence_no_releases(self):
        """Test when no releases are found."""
        vcs_data = _vcs_data()
        result = check_release_cadence(vcs_data)
        assert result.name == "Release Rhythm"
        assert result.score == 0
        assert result.max_score == 10
        assert "No releases found" in result.message
        assert result.risk == "High"

    def test_release_cadence_active(self):
        """Test with recent release (<3 months)."""
        recent_date = datetime.now() - timedelta(days=30)
        vcs_data = _vcs_data(
            releases=[
                {
                    "publishedAt": recent_date.isoformat() + "Z",
                    "tagName": "v1.0.0",
                }
            ]
        )
        result = check_release_cadence(vcs_data)
        assert result.name == "Release Rhythm"
        assert result.score == 10
        assert result.max_score == 10
        assert "Active: Last release" in result.message
        assert result.risk == "None"

    def test_release_cadence_moderate(self):
        """Test with moderate release (3-6 months)."""
        moderate_date = datetime.now() - timedelta(days=120)
        vcs_data = _vcs_data(
            releases=[
                {
                    "publishedAt": moderate_date.isoformat() + "Z",
                    "tagName": "v1.0.0",
                }
            ]
        )
        result = check_release_cadence(vcs_data)
        assert result.name == "Release Rhythm"
        assert result.score == 7
        assert result.max_score == 10
        assert "Moderate: Last release" in result.message
        assert result.risk == "Low"

    def test_release_cadence_slow(self):
        """Test with slow release (6-12 months)."""
        slow_date = datetime.now() - timedelta(days=240)
        vcs_data = _vcs_data(
            releases=[
                {
                    "publishedAt": slow_date.isoformat() + "Z",
                    "tagName": "v1.0.0",
                }
            ]
        )
        result = check_release_cadence(vcs_data)
        assert result.name == "Release Rhythm"
        assert result.score == 4
        assert result.max_score == 10
        assert "Slow: Last release" in result.message
        assert result.risk == "Medium"

    def test_release_cadence_abandoned(self):
        """Test with old release (>12 months)."""
        old_date = datetime.now() - timedelta(days=400)
        vcs_data = _vcs_data(
            releases=[
                {
                    "publishedAt": old_date.isoformat() + "Z",
                    "tagName": "v1.0.0",
                }
            ]
        )
        result = check_release_cadence(vcs_data)
        assert result.name == "Release Rhythm"
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe: Last release" in result.message
        assert result.risk == "High"
