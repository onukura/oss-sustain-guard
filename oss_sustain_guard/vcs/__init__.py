"""
VCS (Version Control System) abstraction layer for OSS Sustain Guard.

This module provides a unified interface for interacting with different VCS platforms
(GitHub, GitLab, Bitbucket, etc.) to fetch repository data for sustainability analysis.
"""

from oss_sustain_guard.vcs.base import BaseVCSProvider, VCSRepositoryData
from oss_sustain_guard.vcs.github import GitHubProvider
from oss_sustain_guard.vcs.gitlab import GitLabProvider

__all__ = [
    "BaseVCSProvider",
    "VCSRepositoryData",
    "GitHubProvider",
    "GitLabProvider",
    "get_vcs_provider",
    "register_vcs_provider",
    "list_supported_platforms",
]

# Registry of supported VCS providers
_PROVIDERS: dict[str, type[BaseVCSProvider]] = {
    "github": GitHubProvider,
    "gitlab": GitLabProvider,
}


def get_vcs_provider(platform: str = "github", **kwargs) -> BaseVCSProvider:
    """
    Factory function to get VCS provider instance.

    Args:
        platform: VCS platform name ('github', 'gitlab', etc.). Default: 'github'
        **kwargs: Provider-specific configuration (e.g., token, host)

    Returns:
        Initialized VCS provider instance

    Raises:
        ValueError: If platform is not supported

    Example:
        >>> provider = get_vcs_provider("github", token="ghp_xxx")
        >>> data = provider.get_repository_data("owner", "repo")
    """
    platform_lower = platform.lower()

    if platform_lower not in _PROVIDERS:
        supported = ", ".join(sorted(_PROVIDERS.keys()))
        raise ValueError(
            f"Unsupported VCS platform: {platform}. Supported platforms: {supported}"
        )

    provider_class = _PROVIDERS[platform_lower]
    return provider_class(**kwargs)


def register_vcs_provider(platform: str, provider_class: type[BaseVCSProvider]) -> None:
    """
    Register a custom VCS provider.

    This function allows plugins or extensions to register additional VCS providers
    beyond the built-in GitHub and GitLab support.

    Args:
        platform: Platform identifier (e.g., 'bitbucket', 'gitea')
        provider_class: Class implementing BaseVCSProvider interface

    Raises:
        TypeError: If provider_class doesn't inherit from BaseVCSProvider

    Example:
        >>> class CustomProvider(BaseVCSProvider):
        ...     pass
        >>> register_vcs_provider("custom", CustomProvider)
    """
    if not issubclass(provider_class, BaseVCSProvider):
        raise TypeError(
            f"Provider class must inherit from BaseVCSProvider, "
            f"got {type(provider_class)}"
        )

    _PROVIDERS[platform.lower()] = provider_class


def list_supported_platforms() -> list[str]:
    """
    List all supported VCS platforms.

    Returns:
        Sorted list of platform identifiers

    Example:
        >>> platforms = list_supported_platforms()
        >>> print(platforms)
        ['github', 'gitlab']
    """
    return sorted(_PROVIDERS.keys())
