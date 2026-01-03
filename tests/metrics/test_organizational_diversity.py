"""Tests for organizational diversity metric."""

from oss_sustain_guard.metrics.organizational_diversity import (
    check_organizational_diversity,
)
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


class TestOrganizationalDiversity:
    """Test organizational diversity metric."""

    def test_no_commit_history(self):
        """Test with no commit history."""
        vcs_data = _vcs_data(default_branch=None, commits=[])
        result = check_organizational_diversity(vcs_data)
        assert result.score == 5
        assert result.max_score == 10
        assert "Commit history data not available" in result.message
        assert result.risk == "None"

    def test_highly_diverse(self):
        """Test highly diverse organizations."""
        commits = [
            {
                "author": {
                    "user": {"login": "user1", "company": "Company A"},
                    "email": "user1@companya.com",
                }
            },
            {
                "author": {
                    "user": {"login": "user2", "company": "Company B"},
                    "email": "user2@companyb.com",
                }
            },
            {
                "author": {
                    "user": {"login": "user3", "company": "Company C"},
                    "email": "user3@companyc.com",
                }
            },
            {
                "author": {
                    "user": {"login": "user4", "company": "Company D"},
                    "email": "user4@companyd.com",
                }
            },
            {
                "author": {
                    "user": {"login": "user5", "company": "Company E"},
                    "email": "user5@companye.com",
                }
            },
        ]
        result = check_organizational_diversity(_vcs_data(commits=commits))
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_good_diversity(self):
        """Test good organizational diversity."""
        commits = [
            {
                "author": {
                    "user": {"login": "user1", "company": "Company A"},
                    "email": "user1@companya.com",
                }
            },
            {
                "author": {
                    "user": {"login": "user2", "company": "Company B"},
                    "email": "user2@companyb.com",
                }
            },
            {
                "author": {
                    "user": {"login": "user3", "company": "Company C"},
                    "email": "user3@companyc.com",
                }
            },
        ]
        result = check_organizational_diversity(_vcs_data(commits=commits))
        assert result.score == 7
        assert result.max_score == 10
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_moderate_diversity(self):
        """Test moderate organizational diversity."""
        commits = [
            {
                "author": {
                    "user": {"login": "user1", "company": "Company A"},
                    "email": "user1@companya.com",
                }
            },
            {
                "author": {
                    "user": {"login": "user2", "company": "Company B"},
                    "email": "user2@companyb.com",
                }
            },
        ]
        result = check_organizational_diversity(_vcs_data(commits=commits))
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_single_organization(self):
        """Test single organization dependency."""
        commits = [
            {
                "author": {
                    "user": {"login": "user1", "company": "Company A"},
                    "email": "user1@companya.com",
                }
            },
            {
                "author": {
                    "user": {"login": "user2", "company": "Company A"},
                    "email": "user2@companya.com",
                }
            },
        ]
        result = check_organizational_diversity(_vcs_data(commits=commits))
        assert result.score == 2
        assert result.max_score == 10
        assert "Single organization dominates" in result.message
        assert result.risk == "High"

    def test_personal_project(self):
        """Test personal project with no organizational data."""
        commits = [
            {
                "author": {
                    "user": {"login": "user1", "company": None},
                    "email": "user1@gmail.com",
                }
            }
        ]
        result = check_organizational_diversity(_vcs_data(commits=commits))
        assert result.score == 5
        assert result.max_score == 10
        assert "Unable to determine organizational diversity" in result.message
        assert result.risk == "None"
