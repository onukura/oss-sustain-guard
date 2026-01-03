"""
Tests for the review_health metric.
"""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.review_health import check_review_health
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


class TestReviewHealthMetric:
    """Test the check_review_health metric function."""

    def test_review_health_no_prs(self):
        """Test when no pull requests are available."""
        vcs_data = _vcs_data(merged_prs=[])
        result = check_review_health(vcs_data)
        assert result.name == "Review Health"
        assert result.score == 5
        assert result.max_score == 10
        assert "No recent merged pull requests to analyze" in result.message
        assert result.risk == "None"

    def test_review_health_no_reviews(self):
        """Test when PRs exist but no reviews."""
        created_at = datetime.now()
        merged_prs = [
            {
                "createdAt": created_at.isoformat() + "Z",
                "reviews": {"edges": [], "totalCount": 0},
            }
        ]
        result = check_review_health(_vcs_data(merged_prs=merged_prs))
        assert result.name == "Review Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "No review activity detected" in result.message
        assert result.risk == "Medium"

    def test_review_health_excellent(self):
        """Test with excellent review health."""
        created_at = datetime.now()
        review_at = created_at + timedelta(hours=24)  # <48h
        merged_prs = [
            {
                "createdAt": created_at.isoformat() + "Z",
                "reviews": {
                    "edges": [
                        {"node": {"createdAt": review_at.isoformat() + "Z"}},
                        {
                            "node": {
                                "createdAt": (
                                    review_at + timedelta(hours=1)
                                ).isoformat()
                                + "Z"
                            }
                        },
                    ],
                    "totalCount": 2,
                },
            }
        ]
        result = check_review_health(_vcs_data(merged_prs=merged_prs))
        assert result.name == "Review Health"
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent: Avg time to first review 24.0h" in result.message
        assert result.risk == "None"

    def test_review_health_good(self):
        """Test with good review health."""
        created_at = datetime.now()
        review_at = created_at + timedelta(days=3)  # <7d
        merged_prs = [
            {
                "createdAt": created_at.isoformat() + "Z",
                "reviews": {
                    "edges": [{"node": {"createdAt": review_at.isoformat() + "Z"}}],
                    "totalCount": 1,
                },
            }
        ]
        result = check_review_health(_vcs_data(merged_prs=merged_prs))
        assert result.name == "Review Health"
        assert result.score == 7
        assert result.max_score == 10
        assert "Good: Avg time to first review 72.0h" in result.message
        assert result.risk == "Low"

    def test_review_health_moderate(self):
        """Test with moderate review health."""
        created_at = datetime.now()
        review_at = created_at + timedelta(days=5)  # <7d but low reviews
        merged_prs = [
            {
                "createdAt": created_at.isoformat() + "Z",
                "reviews": {
                    "edges": [{"node": {"createdAt": review_at.isoformat() + "Z"}}],
                    "totalCount": 0,
                },
            }
        ]
        result = check_review_health(_vcs_data(merged_prs=merged_prs))
        assert result.name == "Review Health"
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate: Avg time to first review 120.0h" in result.message
        assert result.risk == "Medium"

    def test_review_health_poor(self):
        """Test with poor review health."""
        created_at = datetime.now()
        review_at = created_at + timedelta(days=10)  # >7d
        merged_prs = [
            {
                "createdAt": created_at.isoformat() + "Z",
                "reviews": {
                    "edges": [{"node": {"createdAt": review_at.isoformat() + "Z"}}],
                    "totalCount": 1,
                },
            }
        ]
        result = check_review_health(_vcs_data(merged_prs=merged_prs))
        assert result.name == "Review Health"
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe: Slow review process" in result.message
        assert result.risk == "Medium"
