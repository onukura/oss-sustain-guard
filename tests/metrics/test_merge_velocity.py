"""
Tests for the merge_velocity metric.
"""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.merge_velocity import check_merge_velocity
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


class TestMergeVelocityMetric:
    """Test the check_merge_velocity metric function."""

    def test_merge_velocity_no_prs(self):
        """Test when no pull requests are available."""
        vcs_data = _vcs_data()
        result = check_merge_velocity(vcs_data)
        assert result.name == "Change Request Resolution"
        assert result.score == 10
        assert result.max_score == 10
        assert "No merged PRs available for analysis" in result.message
        assert result.risk == "None"

    def test_merge_velocity_no_merge_times(self):
        """Test when PRs exist but no merge times can be calculated."""
        vcs_data = _vcs_data(merged_prs=[{"createdAt": None, "mergedAt": None}])
        result = check_merge_velocity(vcs_data)
        assert result.name == "Change Request Resolution"
        assert result.score == 10
        assert result.max_score == 10
        assert "Unable to analyze merge velocity" in result.message
        assert result.risk == "None"

    def test_merge_velocity_excellent(self):
        """Test with excellent merge velocity (<500h)."""
        created_at = datetime.now()
        merged_at = created_at + timedelta(days=10)  # 240h
        vcs_data = _vcs_data(
            merged_prs=[
                {
                    "createdAt": created_at.isoformat() + "Z",
                    "mergedAt": merged_at.isoformat() + "Z",
                }
            ]
        )
        result = check_merge_velocity(vcs_data)
        assert result.name == "Change Request Resolution"
        assert result.score == 10
        assert result.max_score == 10
        assert "Good: Average merge time 240 hours" in result.message
        assert result.risk == "None"

    def test_merge_velocity_medium(self):
        """Test with medium merge velocity (500-1000h)."""
        created_at = datetime.now()
        merged_at = created_at + timedelta(days=30)  # 720h
        vcs_data = _vcs_data(
            merged_prs=[
                {
                    "createdAt": created_at.isoformat() + "Z",
                    "mergedAt": merged_at.isoformat() + "Z",
                }
            ]
        )
        result = check_merge_velocity(vcs_data)
        assert result.name == "Change Request Resolution"
        assert result.score == 6
        assert result.max_score == 10
        assert "Monitor: Average merge time 720 hours" in result.message
        assert result.risk == "Medium"

    def test_merge_velocity_high(self):
        """Test with high merge velocity (1000-2000h)."""
        created_at = datetime.now()
        merged_at = created_at + timedelta(days=60)  # 1440h
        vcs_data = _vcs_data(
            merged_prs=[
                {
                    "createdAt": created_at.isoformat() + "Z",
                    "mergedAt": merged_at.isoformat() + "Z",
                }
            ]
        )
        result = check_merge_velocity(vcs_data)
        assert result.name == "Change Request Resolution"
        assert result.score == 2
        assert result.max_score == 10
        assert "Note: Average merge time 1440 hours" in result.message
        assert result.risk == "High"

    def test_merge_velocity_critical(self):
        """Test with critical merge velocity (>2000h)."""
        created_at = datetime.now()
        merged_at = created_at + timedelta(days=100)  # 2400h
        vcs_data = _vcs_data(
            merged_prs=[
                {
                    "createdAt": created_at.isoformat() + "Z",
                    "mergedAt": merged_at.isoformat() + "Z",
                }
            ]
        )
        result = check_merge_velocity(vcs_data)
        assert result.name == "Change Request Resolution"
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe: Average merge time 2400 hours" in result.message
        assert result.risk == "Critical"
