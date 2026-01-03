"""
VCS (Version Control System) abstraction layer for OSS Sustain Guard.

This module provides a unified interface for interacting with different VCS platforms
(GitHub, GitLab, Bitbucket, etc.) to fetch repository data for sustainability analysis.
"""

from importlib import import_module
from importlib.metadata import entry_points
from warnings import warn

from oss_sustain_guard.vcs.base import BaseVCSProvider, VCSRepositoryData

_BUILTIN_PROVIDERS = [
    "oss_sustain_guard.vcs.github",
    "oss_sustain_guard.vcs.gitlab",
]


def _load_builtin_providers() -> list[type[BaseVCSProvider]]:
    providers: list[type[BaseVCSProvider]] = []
    for module_path in _BUILTIN_PROVIDERS:
        module = import_module(module_path)
        provider = getattr(module, "PROVIDER", None)
        if provider is not None:
            providers.append(provider)
    return providers


def _load_entrypoint_providers() -> list[type[BaseVCSProvider]]:
    providers: list[type[BaseVCSProvider]] = []
    for entry_point in entry_points(group="oss_sustain_guard.vcs"):
        try:
            loaded = entry_point.load()
        except Exception as exc:
            warn(
                f"Note: Unable to load VCS provider plugin '{entry_point.name}': {exc}",
                stacklevel=2,
            )
            continue
        if isinstance(loaded, type) and issubclass(loaded, BaseVCSProvider):
            providers.append(loaded)
            continue
        if callable(loaded):
            try:
                provider = loaded()
            except Exception as exc:
                warn(
                    "Note: Unable to initialize VCS provider plugin "
                    f"'{entry_point.name}': {exc}",
                    stacklevel=2,
                )
                continue
            if isinstance(provider, type) and issubclass(provider, BaseVCSProvider):
                providers.append(provider)
    return providers


def load_providers() -> list[type[BaseVCSProvider]]:
    """Load built-in and entrypoint VCS providers.

    Built-in providers are always loaded. Entrypoint providers are added if they do
    not share a platform name with an existing built-in provider.
    """
    providers = _load_builtin_providers()
    existing = {
        provider.__name__.lower().replace("provider", "") for provider in providers
    }

    for provider in _load_entrypoint_providers():
        platform_name = provider.__name__.lower().replace("provider", "")
        if platform_name in existing:
            continue
        providers.append(provider)
        existing.add(platform_name)

    return providers


# Registry of supported VCS providers
_PROVIDERS: dict[str, type[BaseVCSProvider]] = {}


def _initialize_providers() -> None:
    """Initialize all registered providers."""
    global _PROVIDERS
    if not _PROVIDERS:
        for provider_class in load_providers():
            # Infer platform name from class name (e.g., GitHubProvider -> github)
            platform_name = provider_class.__name__.lower().replace("provider", "")
            _PROVIDERS[platform_name] = provider_class


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
    _initialize_providers()
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
    _initialize_providers()
    return sorted(_PROVIDERS.keys())


__all__ = [
    "BaseVCSProvider",
    "VCSRepositoryData",
    "get_vcs_provider",
    "register_vcs_provider",
    "list_supported_platforms",
]
