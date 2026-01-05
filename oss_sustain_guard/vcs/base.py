"""
Base VCS provider abstraction for OSS Sustain Guard.

This module defines the abstract interface that all VCS providers (GitHub, GitLab, etc.)
must implement to provide normalized repository data for sustainability analysis.
"""

from abc import ABC, abstractmethod
from typing import Any, NamedTuple


class VCSRepositoryData(NamedTuple):
    """
    Normalized repository data from any VCS platform.

    This structure provides a unified format for repository data regardless of
    the source VCS platform (GitHub, GitLab, Bitbucket, etc.).
    """

    # Basic repository info
    is_archived: bool
    pushed_at: str | None
    owner_type: str  # "Organization", "User", or "Group"
    owner_login: str
    owner_name: str | None  # Display name (for organizations)

    # Repository metadata
    star_count: int  # GitHub stargazersCount, GitLab starCount
    description: str | None  # Project description
    homepage_url: str | None  # Project homepage URL
    topics: list[str]  # Repository topics or tags
    readme_size: int | None  # README byte size
    contributing_file_size: int | None  # CONTRIBUTING byte size
    default_branch: str | None  # Default branch name
    watchers_count: int  # Repository watcher count
    open_issues_count: int  # Total open issues
    language: str | None  # Primary programming language

    # Commit data
    commits: list[dict[str, Any]]  # List of commit objects with author, date, etc.
    total_commits: int  # Total commit count (may be larger than sample)

    # Pull/Merge Request data
    merged_prs: list[dict[str, Any]]  # List of merged PR/MR objects
    closed_prs: list[dict[str, Any]]  # List of closed but not merged PR/MRs
    total_merged_prs: int

    # Release data
    releases: list[dict[str, Any]]  # List of release objects with dates

    # Issue data
    open_issues: list[dict[str, Any]]  # List of open issue objects
    closed_issues: list[dict[str, Any]]  # List of closed issue objects
    total_closed_issues: int

    # Security & compliance
    vulnerability_alerts: list[dict[str, Any]] | None  # None if not available
    has_security_policy: bool
    code_of_conduct: dict[str, str] | None  # {"name": str, "url": str}
    license_info: dict[str, str] | None  # {"name": str, "spdxId": str, "url": str}

    # Project features
    has_wiki: bool
    has_issues: bool
    has_discussions: bool

    # Funding information
    funding_links: list[dict[str, str]]  # [{"platform": str, "url": str}, ...]

    # Fork data
    forks: list[dict[str, Any]]  # List of fork objects with activity data
    total_forks: int

    # CI/CD status
    ci_status: dict[str, str] | None  # {"conclusion": str, "status": str}

    # Metadata
    sample_counts: dict[str, int]  # Sample sizes for each data type
    raw_data: dict[str, Any] | None  # Optional: original platform-specific data


class BaseVCSProvider(ABC):
    """
    Abstract base class for VCS providers.

    All VCS provider implementations (GitHub, GitLab, etc.) must inherit from this
    class and implement its abstract methods to ensure a consistent interface.
    """

    @abstractmethod
    async def get_repository_data(
        self,
        owner: str,
        repo: str,
        scan_depth: str = "default",
        days_lookback: int | None = None,
        time_window: tuple[str, str] | None = None,
    ) -> VCSRepositoryData:
        """
        Fetch normalized repository data from the VCS platform.

        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            scan_depth: Sampling depth - "shallow", "default", or "deep"
            days_lookback: Optional time filter (days to look back), None = no limit
            time_window: Optional (since, until) ISO timestamp tuple for precise window.
                        If provided, takes precedence over days_lookback.

        Returns:
            Normalized VCSRepositoryData structure

        Raises:
            ValueError: If repository not found or credentials invalid
            httpx.HTTPStatusError: If API request fails
        """
        pass

    @abstractmethod
    def get_platform_name(self) -> str:
        """
        Return the platform identifier.

        Returns:
            Platform name in lowercase (e.g., 'github', 'gitlab', 'bitbucket')
        """
        pass

    @abstractmethod
    def validate_credentials(self) -> bool:
        """
        Check if required credentials are available and valid.

        Returns:
            True if credentials are configured, False otherwise
        """
        pass

    @abstractmethod
    def get_repository_url(self, owner: str, repo: str) -> str:
        """
        Construct the web URL for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Full URL to repository (e.g., 'https://github.com/owner/repo')
        """
        pass

    def __repr__(self) -> str:
        """String representation of the provider."""
        return f"{self.__class__.__name__}(platform='{self.get_platform_name()}')"
