"""Tests for VCS factory and provider registration."""

import pytest

from oss_sustain_guard.vcs import (
    get_vcs_provider,
    list_supported_platforms,
    register_vcs_provider,
)
from oss_sustain_guard.vcs.base import BaseVCSProvider, VCSRepositoryData
from oss_sustain_guard.vcs.github import GitHubProvider
from oss_sustain_guard.vcs.gitlab import GitLabProvider


def test_get_vcs_provider_returns_github_by_default():
    """Test that get_vcs_provider returns GitHub provider by default."""
    provider = get_vcs_provider("github", token="test_token")
    assert isinstance(provider, GitHubProvider)
    assert provider.get_platform_name() == "github"


def test_get_vcs_provider_returns_gitlab():
    """Test that get_vcs_provider returns GitLab provider when requested."""
    provider = get_vcs_provider("gitlab", token="test_token")
    assert isinstance(provider, GitLabProvider)
    assert provider.get_platform_name() == "gitlab"


def test_get_vcs_provider_case_insensitive():
    """Test that get_vcs_provider is case-insensitive."""
    provider = get_vcs_provider("GITHUB", token="test_token")
    assert isinstance(provider, GitHubProvider)

    provider2 = get_vcs_provider("GitHub", token="test_token")
    assert isinstance(provider2, GitHubProvider)

    provider3 = get_vcs_provider("GITLAB", token="test_token")
    assert isinstance(provider3, GitLabProvider)


def test_get_vcs_provider_unsupported_platform():
    """Test that get_vcs_provider raises error for unsupported platform."""
    with pytest.raises(ValueError, match="Unsupported VCS platform"):
        get_vcs_provider("bitbucket")


def test_get_vcs_provider_passes_kwargs():
    """Test that get_vcs_provider passes kwargs to provider constructor."""
    provider = get_vcs_provider("github", token="custom_token")
    assert isinstance(provider, GitHubProvider)


def test_list_supported_platforms():
    """Test list_supported_platforms returns available platforms."""
    platforms = list_supported_platforms()
    assert "github" in platforms
    assert "gitlab" in platforms
    assert isinstance(platforms, list)
    # Should be sorted
    assert platforms == sorted(platforms)


def test_register_vcs_provider():
    """Test registering a custom VCS provider."""

    class CustomProvider(BaseVCSProvider):
        def __init__(self, **kwargs):
            self.config = kwargs

        async def get_repository_data(
            self,
            owner: str,
            repo: str,
            scan_depth: str = "default",
            days_lookback: int | None = None,
            time_window: tuple[str, str] | None = None,
        ) -> VCSRepositoryData:
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
            return "custom"

        def validate_credentials(self) -> bool:
            return True

        def get_repository_url(self, owner: str, repo: str) -> str:
            return f"https://custom.com/{owner}/{repo}"

        def __repr__(self) -> str:
            """String representation of the provider."""
            return f"{self.__class__.__name__}(platform='{self.get_platform_name()}')"

    # Register custom provider
    register_vcs_provider("custom", CustomProvider)

    # Verify it's registered
    assert "custom" in list_supported_platforms()

    # Verify we can get it
    provider: BaseVCSProvider = get_vcs_provider(platform="custom", some_config="test")
    assert isinstance(provider, CustomProvider)
    assert provider.get_platform_name() == "custom"
    assert provider.config["some_config"] == "test"


def test_register_vcs_provider_requires_base_class():
    """Test that register_vcs_provider requires BaseVCSProvider subclass."""

    class NotAProvider:
        pass

    with pytest.raises(TypeError, match="must inherit from BaseVCSProvider"):
        register_vcs_provider("invalid", NotAProvider)  # type: ignore
