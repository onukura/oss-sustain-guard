"""Tests for community health metric."""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.community_health import check_community_health
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


class TestCommunityHealth:
    """Test community health metric."""

    def test_no_issues(self):
        """Test with no open issues."""
        vcs_data = _vcs_data(open_issues=[])
        result = check_community_health(vcs_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "No open issues" in result.message
        assert result.risk == "None"

    def test_no_response_data(self):
        """Test with issues but no response data."""
        open_issues = [{"createdAt": "2023-01-01T00:00:00Z", "comments": {"edges": []}}]
        result = check_community_health(_vcs_data(open_issues=open_issues))
        assert result.score == 6
        assert result.max_score == 10
        assert "No recent issue responses" in result.message
        assert result.risk == "None"

    def test_excellent_response_time(self):
        """Test excellent response time (<48 hours)."""
        base_time = datetime.now()
        open_issues = [
            {
                "createdAt": base_time.isoformat(),
                "comments": {
                    "edges": [
                        {
                            "node": {
                                "createdAt": (
                                    base_time + timedelta(hours=24)
                                ).isoformat()
                            }
                        }
                    ]
                },
            }
        ]
        result = check_community_health(_vcs_data(open_issues=open_issues))
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_good_response_time(self):
        """Test good response time (<7 days)."""
        base_time = datetime.now()
        open_issues = [
            {
                "createdAt": base_time.isoformat(),
                "comments": {
                    "edges": [
                        {
                            "node": {
                                "createdAt": (base_time + timedelta(days=3)).isoformat()
                            }
                        }
                    ]
                },
            }
        ]
        result = check_community_health(_vcs_data(open_issues=open_issues))
        assert result.score == 6
        assert result.max_score == 10
        assert "Good" in result.message
        assert result.risk == "None"

    def test_slow_response_time(self):
        """Test slow response time (7-30 days)."""
        base_time = datetime.now()
        open_issues = [
            {
                "createdAt": base_time.isoformat(),
                "comments": {
                    "edges": [
                        {
                            "node": {
                                "createdAt": (
                                    base_time + timedelta(days=14)
                                ).isoformat()
                            }
                        }
                    ]
                },
            }
        ]
        result = check_community_health(_vcs_data(open_issues=open_issues))
        assert result.score == 2
        assert result.max_score == 10
        assert "Needs attention" in result.message
        assert result.risk == "Medium"

    def test_poor_response_time(self):
        """Test poor response time (>30 days)."""
        base_time = datetime.now()
        open_issues = [
            {
                "createdAt": base_time.isoformat(),
                "comments": {
                    "edges": [
                        {
                            "node": {
                                "createdAt": (
                                    base_time + timedelta(days=60)
                                ).isoformat()
                            }
                        }
                    ]
                },
            }
        ]
        result = check_community_health(_vcs_data(open_issues=open_issues))
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe" in result.message
        assert result.risk == "High"
