"""Tests for VCS base module."""

import pytest

from oss_sustain_guard.vcs.base import BaseVCSProvider, VCSRepositoryData


def test_vcs_repository_data_structure():
    """Test VCSRepositoryData can be instantiated."""
    data = VCSRepositoryData(
        is_archived=False,
        pushed_at="2024-01-01T00:00:00Z",
        owner_type="User",
        owner_login="testuser",
        owner_name="Test User",
        star_count=0,
        description=None,
        homepage_url=None,
        topics=[],
        readme_size=None,
        contributing_file_size=None,
        default_branch=None,
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

    assert data.owner_login == "testuser"
    assert data.is_archived is False
    assert data.total_commits == 0


def test_base_vcs_provider_is_abstract():
    """Test that BaseVCSProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseVCSProvider()  # type: ignore


def test_base_vcs_provider_subclass_requires_implementation():
    """Test that subclassing BaseVCSProvider requires implementing abstract methods."""

    class IncompleteProvider(BaseVCSProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()  # type: ignore


def test_base_vcs_provider_can_be_subclassed():
    """Test that BaseVCSProvider can be properly subclassed."""

    class TestProvider(BaseVCSProvider):
        def get_repository_data(self, owner: str, repo: str) -> VCSRepositoryData:
            return VCSRepositoryData(
                is_archived=False,
                pushed_at=None,
                owner_type="User",
                owner_login=owner,
                owner_name=None,
                star_count=0,
                description=None,
                homepage_url=None,
                topics=[],
                readme_size=None,
                contributing_file_size=None,
                default_branch=None,
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

        def get_platform_name(self) -> str:
            return "test"

        def validate_credentials(self) -> bool:
            return True

        def get_repository_url(self, owner: str, repo: str) -> str:
            return f"https://test.com/{owner}/{repo}"

    provider = TestProvider()
    assert provider.get_platform_name() == "test"
    assert provider.validate_credentials() is True
    assert provider.get_repository_url("owner", "repo") == "https://test.com/owner/repo"

    data = provider.get_repository_data("testowner", "testrepo")
    assert data.owner_login == "testowner"
