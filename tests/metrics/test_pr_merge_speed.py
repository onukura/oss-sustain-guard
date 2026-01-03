"""Tests for PR merge speed metric."""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.pr_merge_speed import check_pr_merge_speed
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


class TestPrMergeSpeed:
    """Test PR merge speed metric."""

    def test_no_merged_prs(self):
        """Test with no merged PRs."""
        vcs_data = _vcs_data(merged_prs=[])
        result = check_pr_merge_speed(vcs_data)
        assert result.score == 5
        assert result.max_score == 10
        assert "No merged PRs available" in result.message
        assert result.risk == "None"

    def test_excellent_merge_speed(self):
        """Test excellent merge speed (<3 days)."""
        base_time = datetime.now()
        merged_prs = [
            {
                "createdAt": base_time.isoformat(),
                "mergedAt": (base_time + timedelta(days=1)).isoformat(),
            },
            {
                "createdAt": base_time.isoformat(),
                "mergedAt": (base_time + timedelta(days=2)).isoformat(),
            },
        ]
        result = check_pr_merge_speed(_vcs_data(merged_prs=merged_prs))
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_good_merge_speed(self):
        """Test good merge speed (3-7 days)."""
        base_time = datetime.now()
        merged_prs = [
            {
                "createdAt": base_time.isoformat(),
                "mergedAt": (base_time + timedelta(days=4)).isoformat(),
            },
            {
                "createdAt": base_time.isoformat(),
                "mergedAt": (base_time + timedelta(days=5)).isoformat(),
            },
        ]
        result = check_pr_merge_speed(_vcs_data(merged_prs=merged_prs))
        assert result.score == 8
        assert result.max_score == 10
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_moderate_merge_speed(self):
        """Test moderate merge speed (7-30 days)."""
        base_time = datetime.now()
        merged_prs = [
            {
                "createdAt": base_time.isoformat(),
                "mergedAt": (base_time + timedelta(days=14)).isoformat(),
            },
            {
                "createdAt": base_time.isoformat(),
                "mergedAt": (base_time + timedelta(days=16)).isoformat(),
            },
        ]
        result = check_pr_merge_speed(_vcs_data(merged_prs=merged_prs))
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_slow_merge_speed(self):
        """Test slow merge speed (>30 days)."""
        base_time = datetime.now()
        merged_prs = [
            {
                "createdAt": base_time.isoformat(),
                "mergedAt": (base_time + timedelta(days=45)).isoformat(),
            },
            {
                "createdAt": base_time.isoformat(),
                "mergedAt": (base_time + timedelta(days=50)).isoformat(),
            },
        ]
        result = check_pr_merge_speed(_vcs_data(merged_prs=merged_prs))
        assert result.score == 2
        assert result.max_score == 10
        assert "Observe" in result.message
        assert result.risk == "High"
