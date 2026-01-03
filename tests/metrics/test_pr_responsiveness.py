"""
Tests for the pr_responsiveness metric.
"""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.pr_responsiveness import check_pr_responsiveness
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


class TestPrResponsivenessMetric:
    """Test the check_pr_responsiveness metric function."""

    def test_pr_responsiveness_no_closed_prs(self):
        """Test when no closed PRs are available."""
        vcs_data = _vcs_data(closed_prs=[])
        result = check_pr_responsiveness(vcs_data)
        assert result.name == "PR Responsiveness"
        assert result.score == 5
        assert result.max_score == 10
        assert "No closed PRs to analyze responsiveness" in result.message
        assert result.risk == "None"

    def test_pr_responsiveness_no_response_times(self):
        """Test when PRs exist but no response times can be measured."""
        created_at = datetime.now()
        closed_prs = [
            {
                "createdAt": created_at.isoformat() + "Z",
                "reviews": [],
            }
        ]
        result = check_pr_responsiveness(_vcs_data(closed_prs=closed_prs))
        assert result.name == "PR Responsiveness"
        assert result.score == 2
        assert result.max_score == 10
        assert "Unable to measure PR response times" in result.message
        assert result.risk == "None"

    def test_pr_responsiveness_excellent(self):
        """Test with excellent responsiveness (<24h)."""
        created_at = datetime.now()
        response_at = created_at + timedelta(hours=12)
        closed_prs = [
            {
                "createdAt": created_at.isoformat() + "Z",
                "reviews": [{"createdAt": response_at.isoformat() + "Z"}],
            }
        ]
        result = check_pr_responsiveness(_vcs_data(closed_prs=closed_prs))
        assert result.name == "PR Responsiveness"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: Avg PR first response 12.0h" in result.message
        assert result.risk == "None"

    def test_pr_responsiveness_good(self):
        """Test with good responsiveness (<7d)."""
        created_at = datetime.now()
        response_at = created_at + timedelta(days=3)
        closed_prs = [
            {
                "createdAt": created_at.isoformat() + "Z",
                "reviews": [{"createdAt": response_at.isoformat() + "Z"}],
            }
        ]
        result = check_pr_responsiveness(_vcs_data(closed_prs=closed_prs))
        assert result.name == "PR Responsiveness"
        assert result.score == 6
        assert result.max_score == 10
        assert "Good: Avg PR first response 3.0d" in result.message
        assert result.risk == "Low"

    def test_pr_responsiveness_poor(self):
        """Test with poor responsiveness (>7d)."""
        created_at = datetime.now()
        response_at = created_at + timedelta(days=10)
        closed_prs = [
            {
                "createdAt": created_at.isoformat() + "Z",
                "reviews": [{"createdAt": response_at.isoformat() + "Z"}],
            }
        ]
        result = check_pr_responsiveness(_vcs_data(closed_prs=closed_prs))
        assert result.name == "PR Responsiveness"
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe: Avg PR first response 10.0d" in result.message
        assert result.risk == "Medium"
