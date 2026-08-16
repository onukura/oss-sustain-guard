"""
LFX Insights integration for OSS Sustain Guard.

This module provides URL generation for LFX Insights project pages and badges.
It does NOT make HTTP requests to LFX servers - it only generates URLs that
can be embedded in HTML/Markdown reports.

This design makes the integration:
- Resilient to LFX API changes/outages
- Fast (no network calls during analysis)
- Simple (no API keys or rate limits)
"""

from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote

# Type definitions
ResolutionMethod = Literal["config", "heuristic", "none"]
BadgeType = Literal["health-score", "active-contributors", "contributors"]


@dataclass
class LFXInfo:
    """
    LFX Insights information for a project.

    Attributes:
        project_slug: LFX project identifier (e.g., "kubernetes-kubernetes")
        project_url: URL to the LFX Insights project dashboard
        badges: Dictionary mapping badge types to badge image URLs
        repos_url: Optional repository URL to include in badge queries
        resolution: How the project_slug was determined
    """

    project_slug: str
    project_url: str
    badges: dict[str, str]
    repos_url: str | None = None
    resolution: ResolutionMethod = "heuristic"


class LFXUrlBuilder:
    """
    Builds URLs for LFX Insights projects and badges.

    This class handles URL generation only - no HTTP requests are made.
    """

    BASE_URL = "https://insights.linuxfoundation.org"
    DEFAULT_BADGES: list[BadgeType] = ["health-score", "active-contributors"]

    @classmethod
    def build_project_url(cls, project_slug: str) -> str:
        """
        Build URL to LFX Insights project dashboard.

        Args:
            project_slug: LFX project identifier

        Returns:
            Full URL to the project page

        Example:
            >>> LFXUrlBuilder.build_project_url("kubernetes-kubernetes")
            'https://insights.linuxfoundation.org/project/kubernetes-kubernetes'
        """
        return f"{cls.BASE_URL}/project/{project_slug}"

    @classmethod
    def build_badge_url(
        cls, badge_type: BadgeType, project_slug: str, repos_url: str | None = None
    ) -> str:
        """
        Build URL to LFX Insights badge image.

        Args:
            badge_type: Type of badge (health-score, active-contributors, contributors)
            project_slug: LFX project identifier
            repos_url: Optional repository URL for active-contributors badge

        Returns:
            Full URL to the badge image

        Example:
            >>> LFXUrlBuilder.build_badge_url("health-score", "kubernetes-kubernetes")
            'https://insights.linuxfoundation.org/api/badge/health-score?project=kubernetes-kubernetes'

            >>> LFXUrlBuilder.build_badge_url(
            ...     "active-contributors",
            ...     "ant-design-ant-design",
            ...     "https://github.com/ant-design/ant-design"
            ... )
            'https://insights.linuxfoundation.org/api/badge/active-contributors?project=ant-design-ant-design&repos=https%3A%2F%2Fgithub.com%2Fant-design%2Fant-design'
        """
        url = f"{cls.BASE_URL}/api/badge/{badge_type}?project={project_slug}"

        # Add repos parameter for active-contributors if provided
        if repos_url and badge_type == "active-contributors":
            encoded_repo = quote(repos_url, safe="")
            url += f"&repos={encoded_repo}"

        return url

    @classmethod
    def build_all_badges(
        cls,
        project_slug: str,
        badge_types: list[BadgeType] | None = None,
        repos_url: str | None = None,
    ) -> dict[str, str]:
        """
        Build URLs for multiple badge types.

        Args:
            project_slug: LFX project identifier
            badge_types: List of badge types to generate (uses DEFAULT_BADGES if None)
            repos_url: Optional repository URL for active-contributors badge

        Returns:
            Dictionary mapping badge type to badge URL

        Example:
            >>> badges = LFXUrlBuilder.build_all_badges("kubernetes-kubernetes")
            >>> badges["health-score"]
            'https://insights.linuxfoundation.org/api/badge/health-score?project=kubernetes-kubernetes'
        """
        if badge_types is None:
            badge_types = cls.DEFAULT_BADGES

        return {
            badge_type: cls.build_badge_url(badge_type, project_slug, repos_url)
            for badge_type in badge_types
        }


class LFXProjectResolver:
    """
    Resolves package/repository identifiers to LFX project slugs.

    Resolution strategy (in priority order):
    1. Explicit mapping from configuration
    2. Heuristic inference from repository URL
    3. None (unable to resolve)
    """

    @staticmethod
    def resolve_from_github_url(github_url: str) -> str | None:
        """
        Infer LFX project slug from GitHub repository URL.

        Many LFX projects use the pattern: "{owner}-{repo}"

        Args:
            github_url: GitHub repository URL

        Returns:
            Inferred project slug, or None if unable to parse

        Example:
            >>> LFXProjectResolver.resolve_from_github_url(
            ...     "https://github.com/kubernetes/kubernetes"
            ... )
            'kubernetes-kubernetes'

            >>> LFXProjectResolver.resolve_from_github_url(
            ...     "https://github.com/ant-design/ant-design"
            ... )
            'ant-design-ant-design'
        """
        if not github_url or not isinstance(github_url, str):
            return None

        # Normalize URL
        github_url = github_url.rstrip("/")

        # Extract owner and repo from GitHub URL
        # Supports formats:
        # - https://github.com/owner/repo
        # - git@github.com:owner/repo.git
        parts = None
        if "github.com/" in github_url:
            parts = github_url.split("github.com/")[-1].split("/")
        elif "github.com:" in github_url:
            parts = github_url.split("github.com:")[-1].split("/")

        if not parts or len(parts) < 2:
            return None

        owner = parts[0]
        repo = parts[1].replace(".git", "")

        if not owner or not repo:
            return None

        # Common LFX pattern: owner-repo
        return f"{owner}-{repo}"

    @staticmethod
    def resolve(
        package_name: str,
        repo_url: str | None = None,
        config_mapping: dict[str, str] | None = None,
    ) -> tuple[str | None, ResolutionMethod]:
        """
        Resolve package to LFX project slug.

        Args:
            package_name: Package identifier (e.g., "pypi:requests", "npm:react")
            repo_url: Repository URL (if known)
            config_mapping: Explicit package -> LFX slug mapping from config

        Returns:
            Tuple of (project_slug, resolution_method)
            - project_slug is None if unable to resolve
            - resolution_method indicates how it was resolved

        Example:
            >>> # Config mapping (highest priority)
            >>> mapping = {"pypi:requests": "psf-requests"}
            >>> LFXProjectResolver.resolve("pypi:requests", config_mapping=mapping)
            ('psf-requests', 'config')

            >>> # Heuristic from GitHub URL
            >>> LFXProjectResolver.resolve(
            ...     "npm:react",
            ...     repo_url="https://github.com/facebook/react"
            ... )
            ('facebook-react', 'heuristic')

            >>> # Unable to resolve
            >>> LFXProjectResolver.resolve("pypi:unknown")
            (None, 'none')
        """
        # Priority 1: Explicit configuration mapping
        if config_mapping and package_name in config_mapping:
            return config_mapping[package_name], "config"

        # Priority 2: Heuristic from repository URL
        if repo_url:
            if "github.com" in repo_url:
                slug = LFXProjectResolver.resolve_from_github_url(repo_url)
                if slug:
                    return slug, "heuristic"

        # Unable to resolve
        return None, "none"


def get_lfx_info(
    package_name: str,
    repo_url: str | None = None,
    config_mapping: dict[str, str] | None = None,
    badge_types: list[BadgeType] | None = None,
) -> LFXInfo | None:
    """
    Get LFX Insights information for a package.

    This is the main entry point for integrating LFX data into reports.

    Args:
        package_name: Package identifier
        repo_url: Repository URL (if known)
        config_mapping: Explicit package -> LFX slug mapping from config
        badge_types: List of badge types to generate (uses defaults if None)

    Returns:
        LFXInfo object with URLs, or None if unable to resolve

    Example:
        >>> info = get_lfx_info(
        ...     "npm:react",
        ...     repo_url="https://github.com/facebook/react"
        ... )
        >>> info.project_url
        'https://insights.linuxfoundation.org/project/facebook-react'
        >>> info.badges["health-score"]
        'https://insights.linuxfoundation.org/api/badge/health-score?project=facebook-react'
        >>> info.resolution
        'heuristic'
    """
    project_slug, resolution = LFXProjectResolver.resolve(
        package_name, repo_url, config_mapping
    )

    if not project_slug:
        return None

    project_url = LFXUrlBuilder.build_project_url(project_slug)
    badges = LFXUrlBuilder.build_all_badges(project_slug, badge_types, repo_url)

    return LFXInfo(
        project_slug=project_slug,
        project_url=project_url,
        badges=badges,
        repos_url=repo_url,
        resolution=resolution,
    )
