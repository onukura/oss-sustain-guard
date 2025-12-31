"""
Core analysis logic for OSS Sustain Guard.
"""

import copy
import os
from typing import Any, NamedTuple

import httpx
from dotenv import load_dotenv
from rich.console import Console

from oss_sustain_guard.config import get_verify_ssl

# Load environment variables from .env file
load_dotenv()
console = Console()

# --- Constants ---

GITHUB_GRAPHQL_API = "https://api.github.com/graphql"
LIBRARIESIO_API_BASE = "https://libraries.io/api"
# Using a personal access token from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LIBRARIESIO_API_KEY = os.getenv(
    "LIBRARIESIO_API_KEY"
)  # Optional: for dependents analysis

# --- Global HTTP Client for Connection Pooling ---
# Reuse connections across multiple requests for better performance
_http_client: httpx.Client | None = None
_http_client_verify_ssl: bool | None = None  # Track SSL verification setting


def _get_http_client() -> httpx.Client:
    """Get or create a global HTTP client with connection pooling.

    Recreates the client if SSL verification setting has changed.
    """
    global _http_client, _http_client_verify_ssl
    current_verify_ssl = get_verify_ssl()

    # Recreate client if setting changed or client is closed/None
    if (
        _http_client is None
        or _http_client.is_closed
        or _http_client_verify_ssl != current_verify_ssl
    ):
        # Close existing client if necessary
        if _http_client is not None and not _http_client.is_closed:
            _http_client.close()

        _http_client = httpx.Client(
            verify=current_verify_ssl,
            timeout=10,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
        )
        _http_client_verify_ssl = current_verify_ssl
    return _http_client


def close_http_client():
    """Close the global HTTP client. Call this when shutting down."""
    global _http_client, _http_client_verify_ssl
    if _http_client is not None and not _http_client.is_closed:
        _http_client.close()
        _http_client = None
        _http_client_verify_ssl = None


# --- Data Structures ---


class Metric(NamedTuple):
    """A single sustainability metric."""

    name: str
    score: int
    max_score: int
    message: str
    risk: str  # "Critical", "High", "Medium", "Low", "None"


class MetricModel(NamedTuple):
    """A computed metric model (collection of metrics for specific purpose)."""

    name: str
    score: int
    max_score: int
    observation: str  # Supportive observation instead of "message"


class AnalysisResult(NamedTuple):
    """The result of a repository analysis."""

    repo_url: str
    total_score: int
    metrics: list[Metric]
    funding_links: list[dict[str, str]] = []  # List of {"platform": str, "url": str}
    is_community_driven: bool = False  # True if project is community-driven
    models: list[MetricModel] = []  # Optional metric models (CHAOSS-aligned)
    signals: dict[str, Any] = {}  # Optional raw signals for transparency
    dependency_scores: dict[
        str, int
    ] = {}  # Package name -> score mapping for dependencies
    ecosystem: str = ""  # Ecosystem name (python, javascript, rust, etc.)


# --- Helper Functions ---


def _query_github_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    """
    Executes a GraphQL query against the GitHub API.

    Raises:
        ValueError: If the GITHUB_TOKEN is not set.
        httpx.HTTPStatusError: If the API returns an error.
    """
    if not GITHUB_TOKEN:
        raise ValueError(
            "GITHUB_TOKEN environment variable is required.\n"
            "\n"
            "To get started:\n"
            "1. Create a GitHub Personal Access Token (classic):\n"
            "   → https://github.com/settings/tokens/new\n"
            "2. Select scopes: 'public_repo' (for public repositories)\n"
            "3. Set the token:\n"
            "   export GITHUB_TOKEN='your_token_here'  # Linux/macOS\n"
            "   or add to your .env file: GITHUB_TOKEN=your_token_here\n"
            "\n"
            "For detailed instructions, visit:\n"
            "https://onukura.github.io/oss-sustain-guard/GETTING_STARTED/#github-token-setup"
        )

    headers = {
        "Authorization": f"bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    client = _get_http_client()
    response = client.post(
        GITHUB_GRAPHQL_API,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30,  # Longer timeout for batch queries with complex data
    )
    response.raise_for_status()
    data = response.json()
    if "errors" in data:
        raise httpx.HTTPStatusError(
            f"GitHub API Errors: {data['errors']}",
            request=response.request,
            response=response,
        )
    return data.get("data", {})


def _query_librariesio_api(platform: str, package_name: str) -> dict[str, Any] | None:
    """
    Queries Libraries.io API for package information including dependents count.

    Args:
        platform: Package platform (e.g., 'pypi', 'npm', 'cargo', 'maven')
        package_name: Package name

    Returns:
        Package information dict or None if API key not set or request fails

    Note:
        Requires LIBRARIESIO_API_KEY environment variable.
        Get free API key at: https://libraries.io/api
    """
    api_key = os.getenv("LIBRARIESIO_API_KEY")
    if not api_key:
        return None

    url = f"{LIBRARIESIO_API_BASE}/{platform}/{package_name}"
    params = {"api_key": api_key}

    try:
        client = _get_http_client()
        response = client.get(url, params=params, timeout=10)
        if response.status_code == 404:
            console.print(f"Warning: Package {package_name} not found on Libraries.io.")
            return None
        response.raise_for_status()
        console.print(f"Info: Queried Libraries.io for {package_name} on {platform}.")
        return response.json()
    except httpx.RequestError:
        console.print("Warning: Libraries.io API request failed.")
        return None


# --- GraphQL Query Templates ---


def _get_repository_query() -> str:
    """Returns the GraphQL query to fetch repository metrics."""
    return """
    query GetRepository($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        isArchived
        pushedAt
        owner {
          __typename
          login
          ... on Organization {
            name
            login
          }
        }
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 100) {
                edges {
                  node {
                    authoredDate
                    author {
                      user {
                        login
                        company
                      }
                      email
                    }
                  }
                }
                totalCount
              }
              checkSuites(last: 1) {
                nodes {
                  conclusion
                  status
                }
              }
            }
          }
        }
        pullRequests(first: 50, states: MERGED, orderBy: {field: UPDATED_AT, direction: DESC}) {
          edges {
            node {
              mergedAt
              createdAt
              mergedBy {
                login
              }
              reviews(first: 10) {
                totalCount
                edges {
                  node {
                    createdAt
                  }
                }
              }
            }
          }
        }
        closedPullRequests: pullRequests(first: 50, states: CLOSED, orderBy: {field: UPDATED_AT, direction: DESC}) {
          totalCount
          edges {
            node {
              closedAt
              createdAt
              merged
              reviews(first: 1) {
                edges {
                  node {
                    createdAt
                  }
                }
              }
            }
          }
        }
        mergedPullRequestsCount: pullRequests(states: MERGED) {
          totalCount
        }
        releases(first: 10, orderBy: {field: CREATED_AT, direction: DESC}) {
          edges {
            node {
              publishedAt
              tagName
            }
          }
        }
        issues(first: 20, states: OPEN, orderBy: {field: CREATED_AT, direction: DESC}) {
          edges {
            node {
              createdAt
              comments(first: 1) {
                edges {
                  node {
                    createdAt
                  }
                }
              }
            }
          }
        }
        closedIssues: issues(first: 50, states: CLOSED, orderBy: {field: UPDATED_AT, direction: DESC}) {
          totalCount
          edges {
            node {
              createdAt
              closedAt
              updatedAt
              timelineItems(first: 1, itemTypes: CLOSED_EVENT) {
                edges {
                  node {
                    ... on ClosedEvent {
                      actor {
                        login
                      }
                    }
                  }
                }
              }
            }
          }
        }
        vulnerabilityAlerts(first: 10) {
          edges {
            node {
              securityVulnerability {
                severity
              }
              dismissedAt
            }
          }
        }
        isSecurityPolicyEnabled
        fundingLinks {
          platform
          url
        }
        # New fields for additional metrics
        hasWikiEnabled
        hasIssuesEnabled
        hasDiscussionsEnabled
        codeOfConduct {
          name
          url
        }
        licenseInfo {
          name
          spdxId
          url
        }
        stargazerCount
        forkCount
        watchers {
          totalCount
        }
        forks(first: 20, orderBy: {field: PUSHED_AT, direction: DESC}) {
          edges {
            node {
              createdAt
              pushedAt
              defaultBranchRef {
                target {
                  ... on Commit {
                    history(first: 1) {
                      edges {
                        node {
                          committedDate
                        }
                      }
                    }
                  }
                }
              }
              owner {
                login
              }
            }
          }
        }
        readmeUpperCase: object(expression: "HEAD:README.md") {
          ... on Blob {
            byteSize
            text
          }
        }
        readmeLowerCase: object(expression: "HEAD:readme.md") {
          ... on Blob {
            byteSize
            text
          }
        }
        readmeAllCaps: object(expression: "HEAD:README") {
          ... on Blob {
            byteSize
            text
          }
        }
        contributingFile: object(expression: "HEAD:CONTRIBUTING.md") {
          ... on Blob {
            byteSize
          }
        }
        description
        homepageUrl
      }
    }
    """


# --- Metric Calculation Functions ---


def check_bus_factor(repo_data: dict[str, Any]) -> Metric:
    """
    Analyzes the 'Bus Factor' of a repository with improved logic.

    Considers:
    - Top contributor percentage (recent commits)
    - Project maturity (total commits)
    - Contributor diversity trend

    Risk levels:
    - 90%+ single author: 20pt reduction (but not critical for new projects)
    - 70-89%: 10pt reduction
    - 50-69%: 5pt reduction
    - <50%: 0pt reduction (healthy)

    Note: All metrics are now scored on a 0-10 scale for consistency.
    """
    max_score = 10

    # Extract commit history
    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
        return Metric(
            "Contributor Redundancy",
            0,
            max_score,
            "Note: Commit history data not available.",
            "High",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Contributor Redundancy",
            0,
            max_score,
            "Note: Commit history data not available.",
            "High",
        )

    history = target.get("history", {}).get("edges", [])
    if not history:
        return Metric(
            "Contributor Redundancy",
            0,
            max_score,
            "No commit history available for analysis.",
            "Critical",
        )

    # Bot patterns to exclude (same as check_maintainer_drain)
    bot_keywords = [
        "bot",
        "action",
        "dependabot",
        "renovate",
        "github-actions",
        "ci-",
        "autorelease",
        "release-bot",
        "copilot",
        "actions-user",
    ]

    def is_bot(login: str) -> bool:
        """Check if login appears to be a bot."""
        lower = login.lower()
        return any(keyword in lower for keyword in bot_keywords)

    # Count commits per author (excluding bots)
    author_counts: dict[str, int] = {}
    for edge in history:
        node = edge.get("node", {})
        author = node.get("author", {})
        user = author.get("user")
        if user:
            login = user.get("login")
            if login and not is_bot(login):
                author_counts[login] = author_counts.get(login, 0) + 1

    # Check if we have any human contributors
    if not author_counts:
        return Metric(
            "Contributor Redundancy",
            0,
            max_score,
            "No human contributors found (only bot commits).",
            "Critical",
        )

    # Calculate total commits by human contributors only
    total_commits = sum(author_counts.values())
    if total_commits == 0:
        return Metric(
            "Contributor Redundancy",
            0,
            max_score,
            "No commits found.",
            "Critical",
        )

    # Find the top contributor
    top_contributor_commits = max(author_counts.values())
    percentage = (top_contributor_commits / total_commits) * 100
    num_contributors = len(author_counts)

    # Extract total commit count for BDFL model detection
    total_repo_commits = target.get("history", {}).get("totalCount", len(history))

    # Determine project maturity based on total commit count
    # BDFL (Benevolent Dictator For Life) model detection:
    # - Mature project (1000+ commits) with single-author > 90% = legitimate BDFL
    is_mature_bdfl = total_repo_commits >= 1000 and percentage >= 90
    is_mature_project = total_repo_commits >= 100

    # Scoring logic with BDFL model recognition (0-10 scale)
    if percentage >= 90:
        # Very high single-author concentration
        if is_mature_bdfl:
            # Mature BDFL model = proven track record
            score = 8  # 15/20 → 8/10
            risk = "Low"
            message = (
                f"BDFL model: {percentage:.0f}% by founder/leader. "
                f"Mature project ({total_repo_commits} commits). Proven stability."
            )
        elif is_mature_project:
            # Mature project but recently single-heavy = concern
            score = 2  # 5/20 → 2/10
            risk = "High"
            message = (
                f"High: {percentage:.0f}% of recent commits by single author. "
                f"{num_contributors} contributor(s), {total_repo_commits} total commits."
            )
        else:
            # New project with founder-heavy commit = acceptable
            score = 5  # 10/20 → 5/10
            risk = "Medium"
            message = (
                f"New project: {percentage:.0f}% by single author. "
                f"Expected for early-stage projects."
            )
    elif percentage >= 70:
        score = 5  # 10/20 → 5/10
        risk = "High"
        message = (
            f"High: {percentage:.0f}% of commits by single author. "
            f"{num_contributors} contributor(s) total."
        )
    elif percentage >= 50:
        score = 8  # 15/20 → 8/10
        risk = "Medium"
        message = (
            f"Medium: {percentage:.0f}% by top contributor. "
            f"{num_contributors} contributor(s) total."
        )
    else:
        score = max_score
        risk = "None"
        message = f"Healthy: {num_contributors} active contributors."

    return Metric("Contributor Redundancy", score, max_score, message, risk)


def check_maintainer_drain(repo_data: dict[str, Any]) -> Metric:
    """
    Checks for a recent drain in active maintainers with improved analysis.

    Improvements:
    - Excludes bot accounts (dependabot, renovate, github-actions, etc.)
    - Compares recent (last 25) vs older (25-50) commits
    - Time-series based assessment
    - Graduated risk levels: 50%/70%/90% reduction

    Risk levels:
    - 90%+ reduction: 15pt reduction (critical)
    - 70-89% reduction: 10pt reduction (high)
    - 50-69% reduction: 5pt reduction (medium)
    - <50% reduction: 0pt reduction (acceptable)
    """
    max_score = 10

    # Extract commit history
    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
        return Metric(
            "Maintainer Retention",
            max_score,
            max_score,
            "Note: Maintainer data not available for verification.",
            "None",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Maintainer Retention",
            max_score,
            max_score,
            "Note: Maintainer data not available for verification.",
            "None",
        )

    history = target.get("history", {}).get("edges", [])
    if len(history) < 50:
        # If history is too short, cannot detect drain
        return Metric(
            "Maintainer Retention",
            max_score,
            max_score,
            "Insufficient commit history to detect drain.",
            "None",
        )

    # Bot patterns to exclude
    bot_keywords = [
        "bot",
        "action",
        "dependabot",
        "renovate",
        "github-actions",
        "ci-",
        "autorelease",
        "release-bot",
    ]

    def is_bot(login: str) -> bool:
        """Check if login appears to be a bot."""
        lower = login.lower()
        return any(keyword in lower for keyword in bot_keywords)

    # Split into recent and older commits
    recent_commits = history[:25]
    older_commits = history[25:50]

    # Extract human contributors (exclude bots)
    recent_authors = set()
    for edge in recent_commits:
        user = edge.get("node", {}).get("author", {}).get("user")
        if user:
            login = user.get("login")
            if login and not is_bot(login):
                recent_authors.add(login)

    older_authors = set()
    for edge in older_commits:
        user = edge.get("node", {}).get("author", {}).get("user")
        if user:
            login = user.get("login")
            if login and not is_bot(login):
                older_authors.add(login)

    # If we have very few real contributors, cannot assess
    if not older_authors or not recent_authors:
        return Metric(
            "Maintainer Retention",
            max_score,
            max_score,
            "Insufficient human contributor data.",
            "None",
        )

    # Calculate drain ratio
    drain_ratio = len(recent_authors) / len(older_authors)
    reduction_percentage = (1 - drain_ratio) * 100

    # Scoring logic with graduated risk levels
    if drain_ratio < 0.1:  # 90% reduction
        score = 0
        risk = "Critical"
        message = (
            f"Critical: {reduction_percentage:.0f}% reduction in maintainers. "
            f"From {len(older_authors)} → {len(recent_authors)} active contributors."
        )
    elif drain_ratio < 0.3:  # 70% reduction
        score = 3
        risk = "High"
        message = (
            f"High: {reduction_percentage:.0f}% reduction in maintainers. "
            f"From {len(older_authors)} → {len(recent_authors)} contributors."
        )
    elif drain_ratio < 0.5:  # 50% reduction
        score = 5
        risk = "Medium"
        message = (
            f"Medium: {reduction_percentage:.0f}% reduction in maintainers. "
            f"From {len(older_authors)} → {len(recent_authors)} contributors."
        )
    else:
        score = max_score
        risk = "None"
        message = (
            f"Stable: {len(recent_authors)} active maintainers. "
            f"No significant drain detected."
        )

    return Metric("Maintainer Retention", score, max_score, message, risk)


def check_zombie_status(repo_data: dict[str, Any]) -> Metric:
    """
    Checks if the repository is 'zombie' (abandoned) with improved logic.

    Improvements:
    - Distinguishes between archived (intentional) and abandoned
    - Considers release/tag updates separately from commit activity
    - More nuanced risk assessment for mature projects

    Risk levels:
    - Archived with plan: Low (not zombie)
    - 1+ year, mature, regularly tagged: Medium (stable maintenance)
    - 1+ year, no tags, no activity: High (potentially abandoned)
    - 2+ years, no activity: Critical

    Note: All metrics are now scored on a 0-10 scale for consistency.
    """
    from datetime import datetime

    max_score = 10

    is_archived = repo_data.get("isArchived", False)
    if is_archived:
        # Archived repos are intentional, not risky if properly maintained during lifecycle
        return Metric(
            "Recent Activity",
            5,  # 10/20 → 5/10 - archived is intentional, but needs monitoring
            max_score,
            "Repository is archived (intentional).",
            "Medium",
        )

    pushed_at_str = repo_data.get("pushedAt")
    if not pushed_at_str:
        return Metric(
            "Recent Activity",
            0,
            max_score,
            "Note: Last activity data not available.",
            "High",
        )

    # Parse pushed_at timestamp
    try:
        pushed_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return Metric(
            "Recent Activity",
            0,
            max_score,
            "Note: Activity timestamp format not recognized.",
            "High",
        )

    now = datetime.now(pushed_at.tzinfo)
    days_since_last_push = (now - pushed_at).days

    # Scoring logic with maturity consideration (0-10 scale)
    if days_since_last_push > 730:  # 2+ years
        return Metric(
            "Recent Activity",
            0,
            max_score,
            f"No activity for {days_since_last_push} days (2+ years). Project may be inactive.",
            "Critical",
        )
    elif days_since_last_push > 365:  # 1+ year
        return Metric(
            "Recent Activity",
            2,  # 5/20 → 2/10
            max_score,
            f"Last activity {days_since_last_push} days ago (1+ year). "
            f"May be in stable/maintenance mode.",
            "High",
        )
    elif days_since_last_push > 180:  # 6+ months
        return Metric(
            "Recent Activity",
            5,  # 10/20 → 5/10
            max_score,
            f"Last activity {days_since_last_push} days ago (6+ months).",
            "Medium",
        )
    elif days_since_last_push > 90:  # 3+ months
        return Metric(
            "Recent Activity",
            8,  # 15/20 → 8/10
            max_score,
            f"Last activity {days_since_last_push} days ago (3+ months).",
            "Low",
        )
    else:
        return Metric(
            "Recent Activity",
            max_score,
            max_score,
            f"Recently active ({days_since_last_push} days ago).",
            "None",
        )


def check_merge_velocity(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates the merge velocity (PR turnaround time) with relaxed thresholds.

    Improvements:
    - Graduated scoring based on actual merge times
    - OSS-realistic thresholds (accounting for volunteer teams)
    - Focuses on pathological slowness detection

    Risk levels:
    - >2000 hours (83 days): Critical (severely slow)
    - 1000-2000 hours (42-83 days): High (very slow)
    - 500-1000 hours (21-42 days): Medium (slow but acceptable)
    - <500 hours (21 days): Low/Excellent (responsive)
    """
    from datetime import datetime

    max_score = 10

    pull_requests = repo_data.get("pullRequests", {}).get("edges", [])
    if not pull_requests:
        return Metric(
            "Change Request Resolution",
            max_score,
            max_score,
            "No merged PRs available for analysis.",
            "None",
        )

    merge_times: list[int] = []
    for edge in pull_requests:
        node = edge.get("node", {})
        created_at_str = node.get("createdAt")
        merged_at_str = node.get("mergedAt")

        if created_at_str and merged_at_str:
            try:
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
                merged_at = datetime.fromisoformat(merged_at_str.replace("Z", "+00:00"))
                merge_time_hours = (merged_at - created_at).total_seconds() / 3600
                merge_times.append(int(merge_time_hours))
            except (ValueError, AttributeError):
                pass

    if not merge_times:
        return Metric(
            "Change Request Resolution",
            max_score,
            max_score,
            "Unable to analyze merge velocity.",
            "None",
        )

    avg_merge_time = sum(merge_times) / len(merge_times)

    # Scoring logic with OSS-realistic thresholds
    if avg_merge_time > 2000:  # 83+ days
        score = 0
        risk = "Critical"
        message = (
            f"Observe: Average merge time {avg_merge_time:.0f} hours ({avg_merge_time / 24:.1f} days). "
            f"Consider reviewing PR review process."
        )
    elif avg_merge_time > 1000:  # 42-83 days
        score = 2
        risk = "High"
        message = (
            f"Note: Average merge time {avg_merge_time:.0f} hours ({avg_merge_time / 24:.1f} days). "
            f"Review cycle is quite slow."
        )
    elif avg_merge_time > 500:  # 21-42 days
        score = 6
        risk = "Medium"
        message = (
            f"Medium: Average merge time {avg_merge_time:.0f} hours ({avg_merge_time / 24:.1f} days). "
            f"Slow but acceptable for volunteer-driven OSS."
        )
    else:  # <21 days
        score = max_score
        risk = "None"
        message = (
            f"Good: Average merge time {avg_merge_time:.0f} hours ({avg_merge_time / 24:.1f} days). "
            f"Responsive to PRs."
        )

    return Metric("Change Request Resolution", score, max_score, message, risk)


def check_ci_status(repo_data: dict[str, Any]) -> Metric:
    """
    Verifies the status of recent CI builds by checking checkSuites.

    Note: CI Status is now a reference metric with reduced weight.

    Scoring (0-10 scale):
    - SUCCESS or NEUTRAL: 10/10 (CI passing)
    - FAILURE: 0/10 (CI issues detected)
    - IN_PROGRESS/QUEUED: 6/10 (Not yet completed)
    - No CI data: 0/10 (No CI configuration detected)
    """
    max_score = 10

    # Check if repository is archived
    is_archived = repo_data.get("isArchived", False)
    if is_archived:
        return Metric(
            "Build Health",
            max_score,
            max_score,
            "Repository archived (CI check skipped).",
            "None",
        )

    # Extract CI status from checkSuites
    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
        return Metric(
            "Build Health",
            0,
            max_score,
            "Note: CI status data not available.",
            "High",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Build Health",
            0,
            max_score,
            "Note: CI status data not available.",
            "High",
        )

    check_suites = target.get("checkSuites", {}).get("nodes", [])

    if not check_suites:
        return Metric(
            "Build Health",
            0,
            max_score,
            "No CI configuration detected.",
            "High",
        )

    # Get the most recent check suite
    latest_suite = check_suites[0] if check_suites else None
    if not latest_suite or not isinstance(latest_suite, dict):
        return Metric(
            "Build Health",
            0,
            max_score,
            "No recent CI checks.",
            "High",
        )

    conclusion = latest_suite.get("conclusion") or ""
    status = latest_suite.get("status") or ""

    # Ensure we have strings before calling upper()
    if not isinstance(conclusion, str):
        conclusion = ""
    if not isinstance(status, str):
        status = ""

    conclusion = conclusion.upper()
    status = status.upper()

    # Scoring logic based on CI conclusion (0-10 scale)
    if conclusion in ("SUCCESS", "NEUTRAL"):
        score = max_score
        risk = "None"
        message = f"CI Status: {conclusion.lower()} (Latest check passed)."
    elif conclusion in ("FAILURE", "TIMED_OUT"):
        score = 0
        risk = "Medium"  # Downgraded from Critical
        message = f"CI Status: {conclusion.lower()} (Latest check failed)."
    elif conclusion in ("SKIPPED", "STALE"):
        # SKIPPED is not a failure - give partial credit
        score = 6  # 3/5 → 6/10
        risk = "Low"
        message = f"CI Status: {conclusion.lower()} (Check skipped but CI configured)."
    elif status == "IN_PROGRESS":
        score = 6  # 3/5 → 6/10
        risk = "Low"
        message = "CI Status: Tests in progress (not yet complete)."
    elif status == "QUEUED":
        score = 6  # 3/5 → 6/10
        risk = "Low"
        message = "CI Status: Tests queued."
    elif conclusion == "" and status == "":
        # CI exists but no conclusion yet - give partial credit
        score = 6  # 3/5 → 6/10
        risk = "Low"
        message = "CI Status: Configured (no recent runs detected)."
    else:
        # Unknown status - still give some credit if CI exists
        score = 4  # 2/5 → 4/10
        risk = "Low"
        message = f"CI Status: Unknown ({conclusion or status or 'no data'})."

    return Metric("Build Health", score, max_score, message, risk)


def is_corporate_backed(repo_data: dict[str, Any]) -> bool:
    """
    Detects if a repository is corporate-backed (organization-owned).

    Args:
        repo_data: Repository data from GitHub GraphQL API

    Returns:
        True if owned by an Organization, False if owned by a User
    """
    owner = repo_data.get("owner", {})
    owner_type = owner.get("__typename", "")
    return owner_type == "Organization"


def check_funding(repo_data: dict[str, Any]) -> Metric:
    """
    Checks for funding links and Organization backing.

    For Community-driven projects:
    - Funding links important (indicates sustainability)
    - Scoring: up to 10/10

    For Corporate-backed projects:
    - Corporate backing is primary sustainability indicator
    - Scoring: 10/10 for org-backed (funding sources not expected)

    Considers:
    - Explicit funding links (GitHub Sponsors, etc.)
    - Organization ownership (indicates corporate backing)

    Scoring (Community-driven):
    - Funding links + Organization: 10/10 (Well-supported)
    - Funding links only: 8/10 (Community support)
    - No funding: 0/10 (Unsupported)

    Scoring (Corporate-backed):
    - Organization backing: 10/10 (Corporate sustainability model)
    - Funding links optional (different model than community projects)
    """
    owner = repo_data.get("owner", {})
    owner_login = owner.get("login", "unknown")
    is_org_backed = is_corporate_backed(repo_data)
    funding_links = repo_data.get("fundingLinks", [])
    has_funding_links = len(funding_links) > 0

    if is_org_backed:
        # Corporate-backed: Organization backing is sufficient sustainability signal
        max_score = 10
        if has_funding_links:
            score = 10
            risk = "None"
            message = (
                f"Well-supported: {owner_login} organization + "
                f"{len(funding_links)} funding link(s)."
            )
        else:
            score = 10
            risk = "None"
            message = f"Well-supported: Organization maintained by {owner_login}."
    else:
        # Community-driven: Funding is important
        max_score = 10
        if has_funding_links:
            score = 8
            risk = "None"
            message = f"Community-funded: {len(funding_links)} funding link(s)."
        else:
            score = 0
            risk = "Low"
            message = "No funding sources detected (risk for community projects)."

    return Metric("Funding Signals", score, max_score, message, risk)


def check_release_cadence(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates the release frequency and recency.

    Improvements:
    - Distinguishes between "active development" and "stable maintenance"
    - Considers release frequency as a sign of ongoing support
    - Detects projects that commit but never release

    Scoring:
    - <3 months since last release: 10/10 (Active)
    - 3-6 months: 7/10 (Moderate)
    - 6-12 months: 4/10 (Slow)
    - >12 months: 0/10 (Abandoned)
    """
    from datetime import datetime

    max_score = 10

    releases = repo_data.get("releases", {}).get("edges", [])

    if not releases:
        # No releases detected - check if archived
        is_archived = repo_data.get("isArchived", False)
        if is_archived:
            return Metric(
                "Release Rhythm",
                max_score,
                max_score,
                "Archived repository (no releases expected).",
                "None",
            )
        return Metric(
            "Release Rhythm",
            0,
            max_score,
            "No releases found. Project may not be user-ready.",
            "High",
        )

    # Get the most recent release
    latest_release = releases[0].get("node", {})
    published_at_str = latest_release.get("publishedAt")
    tag_name = latest_release.get("tagName", "unknown")

    if not published_at_str:
        return Metric(
            "Release Rhythm",
            0,
            max_score,
            "Note: Release date information not available.",
            "High",
        )

    try:
        published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return Metric(
            "Release Rhythm",
            0,
            max_score,
            "Note: Release date format not recognized.",
            "High",
        )

    now = datetime.now(published_at.tzinfo)
    days_since_release = (now - published_at).days

    # Scoring logic
    if days_since_release < 90:  # <3 months
        score = max_score
        risk = "None"
        message = f"Active: Last release {days_since_release} days ago ({tag_name})."
    elif days_since_release < 180:  # 3-6 months
        score = 7
        risk = "Low"
        message = (
            f"Moderate: Last release {days_since_release} days ago ({tag_name}). "
            f"Consider new release."
        )
    elif days_since_release < 365:  # 6-12 months
        score = 4
        risk = "Medium"
        message = (
            f"Slow: Last release {days_since_release} days ago ({tag_name}). "
            f"Release cycle appears stalled."
        )
    else:  # >12 months
        score = 0
        risk = "High"
        message = (
            f"Observe: Last release {days_since_release} days ago ({tag_name}). "
            f"No releases in over a year."
        )

    return Metric("Release Rhythm", score, max_score, message, risk)


def check_security_posture(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates the security posture of the repository.

    Considers:
    - Presence of security policy (SECURITY.md)
    - Unresolved vulnerability alerts (Critical/High)
    - Overall security awareness

    Scoring (0-10 scale):
    - Critical alerts unresolved: 0/10 (Critical)
    - High alerts unresolved (3+): 3/10 (High risk)
    - High alerts unresolved (1-2): 5/10 (Medium risk)
    - Security policy + no alerts: 10/10 (Excellent)
    - No alerts: 8/10 (Good)
    - No security infrastructure: 5/10 (Moderate)
    """
    max_score = 10

    has_security_policy = repo_data.get("isSecurityPolicyEnabled", False)
    vulnerability_alerts = repo_data.get("vulnerabilityAlerts", {}).get("edges", [])

    # Count unresolved alerts by severity
    critical_count = 0
    high_count = 0

    for edge in vulnerability_alerts:
        node = edge.get("node", {})
        dismissed_at = node.get("dismissedAt")
        if dismissed_at:
            # Alert was dismissed/resolved
            continue

        severity = node.get("securityVulnerability", {}).get("severity", "").upper()
        if severity == "CRITICAL":
            critical_count += 1
        elif severity == "HIGH":
            high_count += 1

    # Scoring logic (0-10 scale)
    if critical_count > 0:
        score = 0
        risk = "Critical"
        message = (
            f"Attention needed: {critical_count} unresolved CRITICAL vulnerability alert(s). "
            f"Review and action recommended."
        )
    elif high_count >= 3:
        score = 3  # 5/15 → 3/10
        risk = "High"
        message = (
            f"High: {high_count} unresolved HIGH vulnerability alert(s). "
            f"Review and patch recommended."
        )
    elif high_count > 0:
        score = 5  # 8/15 → 5/10
        risk = "Medium"
        message = (
            f"Medium: {high_count} unresolved HIGH vulnerability alert(s). "
            f"Monitor and address."
        )
    elif has_security_policy:
        score = max_score
        risk = "None"
        message = "Excellent: Security policy enabled, no unresolved alerts."
    elif vulnerability_alerts:
        # Has alerts infrastructure but all resolved
        score = 8  # 12/15 → 8/10
        risk = "None"
        message = "Good: No unresolved vulnerabilities detected."
    else:
        # No security policy, no alerts (may not be using Dependabot)
        score = 5  # 8/15 → 5/10
        risk = "None"
        message = "Moderate: No security policy detected. Consider adding SECURITY.md."

    return Metric("Security Signals", score, max_score, message, risk)


def check_community_health(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates community engagement and responsiveness.

    Considers:
    - Issue response time (first comment on new issues)
    - Community activity level
    - Maintainer engagement

    Scoring (0-10 scale):
    - Average response <48h: 10/10 (Excellent)
    - Average response <7d: 6/10 (Good)
    - Average response 7-30d: 2/10 (Slow)
    - Average response >30d: 0/10 (Poor)
    - No open issues: 10/10 (Low activity or well-maintained)
    """
    from datetime import datetime

    max_score = 10

    issues = repo_data.get("issues", {}).get("edges", [])

    if not issues:
        return Metric(
            "Community Health",
            max_score,
            max_score,
            "No open issues. Well-maintained or low activity.",
            "None",
        )

    response_times: list[int] = []

    for edge in issues:
        node = edge.get("node", {})
        created_at_str = node.get("createdAt")
        comments = node.get("comments", {}).get("edges", [])

        if not created_at_str or not comments:
            # Issue with no comments yet
            continue

        first_comment = comments[0].get("node", {})
        first_comment_at_str = first_comment.get("createdAt")

        if not first_comment_at_str:
            continue

        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            first_comment_at = datetime.fromisoformat(
                first_comment_at_str.replace("Z", "+00:00")
            )
            response_time_hours = (first_comment_at - created_at).total_seconds() / 3600
            response_times.append(int(response_time_hours))
        except (ValueError, AttributeError):
            pass

    if not response_times:
        return Metric(
            "Community Health",
            6,  # 3/5 → 6/10 - more generous: 6/10 for no data
            max_score,
            "Note: No recent issue responses to analyze (may indicate low issue volume).",
            "None",
        )

    avg_response_time = sum(response_times) / len(response_times)

    # Scoring logic (0-10 scale)
    if avg_response_time < 48:  # <2 days
        score = max_score
        risk = "None"
        message = (
            f"Excellent: Average issue response time {avg_response_time:.1f} hours."
        )
    elif avg_response_time < 168:  # <7 days
        score = 6  # 3/5 → 6/10
        risk = "None"
        message = (
            f"Good: Average issue response time {avg_response_time:.1f} hours "
            f"({avg_response_time / 24:.1f} days)."
        )
    elif avg_response_time < 720:  # <30 days
        score = 2  # 1/5 → 2/10
        risk = "Medium"
        message = (
            f"Slow: Average issue response time {avg_response_time:.1f} hours "
            f"({avg_response_time / 24:.1f} days)."
        )
    else:
        score = 0
        risk = "High"
        message = (
            f"Observe: Average issue response time {avg_response_time:.1f} hours "
            f"({avg_response_time / 24:.1f} days). Community response could be improved."
        )

    return Metric("Community Health", score, max_score, message, risk)


def check_attraction(repo_data: dict[str, Any]) -> Metric:
    """
    Measures the project's ability to attract new contributors (CHAOSS Attraction metric).

    Analyzes recent commit history to identify first-time contributors
    in the last 6 months compared to earlier periods.

    Scoring:
    - 5+ new contributors in last 6 months: 10/10 (Strong attraction)
    - 3-4 new contributors: 7/10 (Good attraction)
    - 1-2 new contributors: 4/10 (Moderate attraction)
    - 0 new contributors: 0/10 (Needs attention)
    """
    from datetime import datetime, timedelta, timezone

    max_score = 10

    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
        return Metric(
            "Contributor Attraction",
            0,
            max_score,
            "Note: Commit history data not available.",
            "Medium",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Contributor Attraction",
            0,
            max_score,
            "Note: Commit history data not available.",
            "Medium",
        )

    history = target.get("history", {}).get("edges", [])
    if not history:
        return Metric(
            "Contributor Attraction",
            0,
            max_score,
            "No commit history available for analysis.",
            "Medium",
        )

    # Bot patterns to exclude (same as check_bus_factor)
    bot_keywords = [
        "bot",
        "action",
        "dependabot",
        "renovate",
        "github-actions",
        "ci-",
        "autorelease",
        "release-bot",
        "copilot",
        "actions-user",
    ]

    def is_bot(login: str) -> bool:
        """Check if login appears to be a bot."""
        lower = login.lower()
        return any(keyword in lower for keyword in bot_keywords)

    # Collect all contributors with their first commit date
    contributor_first_seen: dict[str, datetime] = {}
    now = datetime.now(timezone.utc)
    six_months_ago = now - timedelta(days=180)

    for edge in history:
        node = edge.get("node", {})
        author = node.get("author", {})
        user = author.get("user")
        authored_date_str = node.get("authoredDate")

        if not user or not authored_date_str:
            continue

        login = user.get("login")
        if not login or is_bot(login):  # Exclude bots
            continue

        try:
            authored_date = datetime.fromisoformat(
                authored_date_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            continue

        # Track first appearance of each contributor
        if login not in contributor_first_seen:
            contributor_first_seen[login] = authored_date
        else:
            # Update if we found an earlier commit
            if authored_date < contributor_first_seen[login]:
                contributor_first_seen[login] = authored_date

    # Count new contributors in the last 6 months
    new_contributors = [
        login
        for login, first_date in contributor_first_seen.items()
        if first_date >= six_months_ago
    ]

    new_count = len(new_contributors)
    total_contributors = len(contributor_first_seen)

    # Scoring logic
    if new_count >= 5:
        score = max_score
        risk = "None"
        message = f"Strong: {new_count} new contributors in last 6 months. Active community growth."
    elif new_count >= 3:
        score = 7
        risk = "Low"
        message = (
            f"Good: {new_count} new contributors in last 6 months. Healthy attraction."
        )
    elif new_count >= 1:
        score = 4
        risk = "Medium"
        message = f"Moderate: {new_count} new contributor(s) in last 6 months. Consider outreach efforts."
    else:
        score = 0
        risk = "Medium"
        message = (
            f"Observe: No new contributors in last 6 months. "
            f"Total: {total_contributors} contributor(s). Consider community engagement."
        )

    return Metric("Contributor Attraction", score, max_score, message, risk)


def check_retention(repo_data: dict[str, Any]) -> Metric:
    """
    Measures contributor retention (CHAOSS Retention metric).

    Analyzes whether contributors who were active 6+ months ago
    are still contributing in recent months.

    Scoring:
    - 80%+ retention: 10/10 (Excellent retention)
    - 60-79% retention: 7/10 (Good retention)
    - 40-59% retention: 4/10 (Moderate retention)
    - <40% retention: 0/10 (Needs attention)
    """
    from datetime import datetime, timedelta, timezone

    max_score = 10

    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
        return Metric(
            "Contributor Retention",
            max_score // 2,
            max_score,
            "Note: Commit history data not available.",
            "Medium",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Contributor Retention",
            max_score // 2,
            max_score,
            "Note: Commit history data not available.",
            "Medium",
        )

    history = target.get("history", {}).get("edges", [])
    if not history:
        return Metric(
            "Contributor Retention",
            max_score // 2,
            max_score,
            "No commit history available for analysis.",
            "Medium",
        )

    # Bot patterns to exclude (same as check_bus_factor)
    bot_keywords = [
        "bot",
        "action",
        "dependabot",
        "renovate",
        "github-actions",
        "ci-",
        "autorelease",
        "release-bot",
        "copilot",
        "actions-user",
    ]

    def is_bot(login: str) -> bool:
        """Check if login appears to be a bot."""
        lower = login.lower()
        return any(keyword in lower for keyword in bot_keywords)

    # Track contributors by time period
    now = datetime.now(timezone.utc)
    three_months_ago = now - timedelta(days=90)
    six_months_ago = now - timedelta(days=180)

    recent_contributors: set[str] = set()  # Last 3 months
    earlier_contributors: set[str] = set()  # 3-6 months ago

    for edge in history:
        node = edge.get("node", {})
        author = node.get("author", {})
        user = author.get("user")
        authored_date_str = node.get("authoredDate")

        if not user or not authored_date_str:
            continue

        login = user.get("login")
        if not login or is_bot(login):  # Exclude bots
            continue

        try:
            authored_date = datetime.fromisoformat(
                authored_date_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            continue

        # Categorize by time period
        if authored_date >= three_months_ago:
            recent_contributors.add(login)
        elif authored_date >= six_months_ago:
            earlier_contributors.add(login)

    # Calculate retention: how many earlier contributors are still active?
    if not earlier_contributors:
        return Metric(
            "Contributor Retention",
            max_score,
            max_score,
            "New project: Not enough history to assess retention.",
            "None",
        )

    retained_contributors = recent_contributors & earlier_contributors
    retention_rate = len(retained_contributors) / len(earlier_contributors)
    retention_percentage = retention_rate * 100

    # Scoring logic
    if retention_rate >= 0.8:
        score = max_score
        risk = "None"
        message = (
            f"Excellent: {retention_percentage:.0f}% contributor retention. "
            f"{len(retained_contributors)}/{len(earlier_contributors)} contributors remain active."
        )
    elif retention_rate >= 0.6:
        score = 7
        risk = "Low"
        message = (
            f"Good: {retention_percentage:.0f}% contributor retention. "
            f"{len(retained_contributors)}/{len(earlier_contributors)} contributors remain active."
        )
    elif retention_rate >= 0.4:
        score = 4
        risk = "Medium"
        message = (
            f"Moderate: {retention_percentage:.0f}% contributor retention. "
            f"{len(retained_contributors)}/{len(earlier_contributors)} contributors remain active. "
            f"Consider engagement efforts."
        )
    else:
        score = 0
        risk = "High"
        message = (
            f"Needs attention: {retention_percentage:.0f}% contributor retention. "
            f"Only {len(retained_contributors)}/{len(earlier_contributors)} earlier contributors remain active."
        )

    return Metric("Contributor Retention", score, max_score, message, risk)


def check_review_health(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates pull request review health (CHAOSS Review Health metric).

    Considers:
    - Time to first review on merged PRs
    - Review count per PR

    Scoring:
    - Avg first review <48h & 2+ reviews: 10/10 (Excellent)
    - Avg first review <7d & 1+ reviews: 7/10 (Good)
    - Avg first review >7d or 0 reviews: 0/10 (Needs improvement)
    """
    from datetime import datetime

    max_score = 10

    prs = repo_data.get("pullRequests", {}).get("edges", [])

    if not prs:
        return Metric(
            "Review Health",
            max_score // 2,
            max_score,
            "Note: No recent merged pull requests to analyze.",
            "None",
        )

    review_times: list[float] = []
    review_counts: list[int] = []

    for edge in prs:
        node = edge.get("node", {})
        created_at_str = node.get("createdAt")
        reviews = node.get("reviews", {})
        review_edges = reviews.get("edges", [])
        review_total = reviews.get("totalCount", 0)

        if not created_at_str:
            continue

        review_counts.append(review_total)

        # Calculate time to first review
        if review_edges:
            first_review = review_edges[0].get("node", {})
            first_review_at_str = first_review.get("createdAt")

            if first_review_at_str:
                try:
                    created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                    first_review_at = datetime.fromisoformat(
                        first_review_at_str.replace("Z", "+00:00")
                    )
                    review_time_hours = (
                        first_review_at - created_at
                    ).total_seconds() / 3600
                    review_times.append(review_time_hours)
                except (ValueError, AttributeError):
                    pass

    if not review_times and not review_counts:
        return Metric(
            "Review Health",
            0,
            max_score,
            "Observe: No review activity detected in recent PRs.",
            "Medium",
        )

    avg_review_time = sum(review_times) / len(review_times) if review_times else 999
    avg_review_count = sum(review_counts) / len(review_counts) if review_counts else 0

    # Scoring logic
    if avg_review_time < 48 and avg_review_count >= 2:
        score = max_score
        risk = "None"
        message = (
            f"Excellent: Avg time to first review {avg_review_time:.1f}h. "
            f"Avg {avg_review_count:.1f} reviews per PR."
        )
    elif avg_review_time < 168 and avg_review_count >= 1:  # <7 days
        score = 7
        risk = "Low"
        message = (
            f"Good: Avg time to first review {avg_review_time:.1f}h "
            f"({avg_review_time / 24:.1f}d). Avg {avg_review_count:.1f} reviews per PR."
        )
    elif avg_review_time < 168:  # <7 days but low review count
        score = 4
        risk = "Medium"
        message = (
            f"Moderate: Avg time to first review {avg_review_time:.1f}h, "
            f"but low review count ({avg_review_count:.1f} per PR)."
        )
    else:
        score = 0
        risk = "Medium"
        message = (
            f"Observe: Slow review process (avg {avg_review_time / 24:.1f}d to first review). "
            f"Consider increasing reviewer engagement."
        )

    return Metric("Review Health", score, max_score, message, risk)


# --- New Metrics (Phase 5) ---


def check_documentation_presence(repo_data: dict[str, Any]) -> Metric:
    """
    Checks for presence of essential documentation files.

    Evaluates:
    - README.md existence and size
    - CONTRIBUTING.md existence
    - Wiki enabled
    - Homepage/documentation link
    - Description presence

    Scoring:
    - All docs present: 10/10
    - README + some docs: 7/10
    - Only README: 4/10
    - No documentation: 0/10
    """
    max_score = 10

    # Check README (multiple patterns for case sensitivity)
    readme_upper = repo_data.get("readmeUpperCase")  # README.md
    readme_lower = repo_data.get("readmeLowerCase")  # readme.md
    readme_all_caps = repo_data.get("readmeAllCaps")  # README

    # Use whichever README pattern exists
    readme = readme_upper or readme_lower or readme_all_caps

    # Check if README exists and handle symlinks
    has_readme = False
    if readme is not None:
        byte_size = readme.get("byteSize", 0)
        # If byte_size is small (< 100), it might be a symlink - check text content
        if byte_size > 100:
            has_readme = True
        elif byte_size > 0:
            # Small file - might be a symlink, check if text looks like a path
            text = readme.get("text", "")
            if text and "/" in text and not text.startswith("#"):
                # Looks like a symlink path (e.g., "packages/next/README.md")
                # In this case, consider README as present since GitHub resolves it
                has_readme = True
            elif text and len(text.strip()) >= 10:
                # Small but valid README content
                has_readme = True

    # Check CONTRIBUTING.md
    contributing = repo_data.get("contributingFile")
    has_contributing = contributing is not None

    # Check Wiki
    has_wiki = repo_data.get("hasWikiEnabled", False)

    # Check Homepage URL
    homepage = repo_data.get("homepageUrl")
    has_homepage = bool(homepage and len(homepage) > 5)

    # Check Description
    description = repo_data.get("description")
    has_description = bool(description and len(description) > 10)

    # Count documentation signals
    doc_signals = sum(
        [has_readme, has_contributing, has_wiki, has_homepage, has_description]
    )

    # Scoring logic
    if doc_signals >= 4:
        score = max_score
        risk = "None"
        message = f"Excellent: {doc_signals}/5 documentation signals present."
    elif doc_signals >= 3:
        score = 7
        risk = "Low"
        message = f"Good: {doc_signals}/5 documentation signals present."
    elif has_readme and doc_signals >= 2:
        score = 5
        risk = "Low"
        message = (
            f"Moderate: README present with {doc_signals}/5 documentation signals."
        )
    elif has_readme:
        score = 4
        risk = "Medium"
        message = "Basic: Only README detected. Consider adding CONTRIBUTING.md."
    else:
        score = 0
        risk = "High"
        message = "Observe: No README or documentation found. Add documentation to help contributors."

    return Metric("Documentation Presence", score, max_score, message, risk)


def check_code_of_conduct(repo_data: dict[str, Any]) -> Metric:
    """
    Checks for presence of a Code of Conduct.

    A Code of Conduct signals a welcoming, inclusive community.

    Scoring (0-10 scale):
    - GitHub recognized CoC: 10/10
    - No CoC: 0/10 (but low risk - informational)
    """
    max_score = 10

    code_of_conduct = repo_data.get("codeOfConduct")

    if code_of_conduct and code_of_conduct.get("name"):
        coc_name = code_of_conduct.get("name", "Unknown")
        score = max_score
        risk = "None"
        message = f"Excellent: Code of Conduct present ({coc_name})."
    else:
        score = 0
        risk = "Low"
        message = (
            "Note: No Code of Conduct detected. Consider adding one for inclusivity."
        )

    return Metric("Code of Conduct", score, max_score, message, risk)


def check_pr_acceptance_ratio(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates the Change Request Acceptance Ratio (CHAOSS metric).

    Measures: merged PRs / (merged PRs + closed-without-merge PRs)

    A high ratio indicates openness to external contributions.

    Scoring:
    - 80%+ acceptance: 10/10 (Very welcoming)
    - 60-79%: 7/10 (Good)
    - 40-59%: 4/10 (Moderate - may be selective)
    - <40%: 0/10 (Needs attention)
    """
    max_score = 10

    # Get merged count
    merged_prs = repo_data.get("mergedPullRequestsCount", {})
    merged_count = merged_prs.get("totalCount", 0)

    # Get closed PRs (includes both merged and closed-without-merge)
    closed_prs = repo_data.get("closedPullRequests", {})
    closed_edges = closed_prs.get("edges", [])

    # Count closed-without-merge
    closed_without_merge = sum(
        1 for edge in closed_edges if edge.get("node", {}).get("merged") is False
    )

    total_resolved = merged_count + closed_without_merge

    if total_resolved == 0:
        return Metric(
            "PR Acceptance Ratio",
            max_score // 2,
            max_score,
            "Note: No resolved pull requests to analyze.",
            "None",
        )

    acceptance_ratio = merged_count / total_resolved
    percentage = acceptance_ratio * 100

    # Scoring logic
    if acceptance_ratio >= 0.8:
        score = max_score
        risk = "None"
        message = (
            f"Excellent: {percentage:.0f}% PR acceptance rate. "
            f"Very welcoming to contributions ({merged_count} merged)."
        )
    elif acceptance_ratio >= 0.6:
        score = 7
        risk = "Low"
        message = (
            f"Good: {percentage:.0f}% PR acceptance rate. "
            f"Open to external contributions ({merged_count} merged)."
        )
    elif acceptance_ratio >= 0.4:
        score = 4
        risk = "Medium"
        message = (
            f"Moderate: {percentage:.0f}% PR acceptance rate. "
            f"May be selective about contributions."
        )
    else:
        score = 0
        risk = "Medium"
        message = (
            f"Observe: {percentage:.0f}% PR acceptance rate. "
            f"High rejection rate may discourage contributors."
        )

    return Metric("PR Acceptance Ratio", score, max_score, message, risk)


def check_issue_resolution_duration(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates Issue Resolution Duration (CHAOSS metric).

    Measures average time to close issues. Adjusts expectations based on
    project scale (stargazers count) to account for larger issue volumes.

    Scoring (Small/Medium projects <10K stars):
    - <7 days avg: 10/10 (Fast)
    - 7-30 days: 7/10 (Good)
    - 30-90 days: 4/10 (Moderate)
    - 90-180 days: 2/10 (Slow)
    - >180 days: 0/10 (Very slow)

    Scoring (Large projects 10K-100K stars):
    - <30 days avg: 10/10 (Fast)
    - 30-90 days: 7/10 (Good)
    - 90-180 days: 5/10 (Moderate)
    - 180-365 days: 3/10 (Acceptable)
    - >365 days: 0/10 (Needs attention)

    Scoring (Very large projects ≥100K stars):
    - <60 days avg: 10/10 (Fast)
    - 60-180 days: 7/10 (Good)
    - 180-365 days: 5/10 (Moderate)
    - 365-730 days: 3/10 (Acceptable)
    - >730 days: 0/10 (Needs attention)
    """
    from datetime import datetime

    max_score = 10

    closed_issues = repo_data.get("closedIssues", {})
    edges = closed_issues.get("edges", [])

    if not edges:
        return Metric(
            "Issue Resolution Duration",
            7,  # More generous: 7/10 instead of 5/10
            max_score,
            "Note: No closed issues in recent history (may be addressing issues promptly).",
            "None",
        )

    resolution_times: list[float] = []

    for edge in edges:
        node = edge.get("node", {})
        created_at_str = node.get("createdAt")
        closed_at_str = node.get("closedAt")

        if not created_at_str or not closed_at_str:
            continue

        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            closed_at = datetime.fromisoformat(closed_at_str.replace("Z", "+00:00"))
            resolution_days = (closed_at - created_at).total_seconds() / 86400
            resolution_times.append(resolution_days)
        except (ValueError, AttributeError):
            pass

    if not resolution_times:
        return Metric(
            "Issue Resolution Duration",
            max_score // 2,
            max_score,
            "Note: Unable to calculate issue resolution times.",
            "None",
        )

    avg_resolution = sum(resolution_times) / len(resolution_times)

    # Detect project scale for adjusted scoring
    stargazers_count = repo_data.get("stargazerCount", 0)
    is_very_large = stargazers_count >= 100000
    is_large = stargazers_count >= 10000

    # Scoring logic - adjusted for project scale
    if is_very_large:
        # Very large projects: Most lenient thresholds (massive issue volume)
        if avg_resolution < 60:
            score = max_score
            risk = "None"
            message = f"Excellent: Avg issue resolution {avg_resolution:.1f} days. Fast for very large-scale project."
        elif avg_resolution < 180:
            score = 7
            risk = "Low"
            message = f"Good: Avg issue resolution {avg_resolution:.1f} days."
        elif avg_resolution < 365:
            score = 5
            risk = "Medium"
            message = f"Moderate: Avg issue resolution {avg_resolution:.1f} days. Reasonable for very large project."
        elif avg_resolution < 730:
            score = 3
            risk = "Medium"
            message = f"Monitor: Avg issue resolution {avg_resolution:.1f} days. Acceptable given project scale."
        else:
            score = 0
            risk = "High"
            message = f"Observe: Avg issue resolution {avg_resolution:.1f} days. Consider improving."
    elif is_large:
        # Large projects: Lenient thresholds (higher issue volume)
        if avg_resolution < 30:
            score = max_score
            risk = "None"
            message = f"Excellent: Avg issue resolution {avg_resolution:.1f} days. Fast for large-scale project."
        elif avg_resolution < 90:
            score = 7
            risk = "Low"
            message = f"Good: Avg issue resolution {avg_resolution:.1f} days."
        elif avg_resolution < 180:
            score = 5
            risk = "Medium"
            message = f"Moderate: Avg issue resolution {avg_resolution:.1f} days. Acceptable for large project."
        elif avg_resolution < 365:
            score = 3
            risk = "Medium"
            message = f"Monitor: Avg issue resolution {avg_resolution:.1f} days. Consider improving."
        else:
            score = 0
            risk = "High"
            message = f"Observe: Avg issue resolution {avg_resolution:.1f} days. Significant backlog detected."
    else:
        # Small/Medium projects: Standard thresholds
        if avg_resolution < 7:
            score = max_score
            risk = "None"
            message = f"Excellent: Avg issue resolution {avg_resolution:.1f} days. Fast response."
        elif avg_resolution < 30:
            score = 7
            risk = "Low"
            message = f"Good: Avg issue resolution {avg_resolution:.1f} days."
        elif avg_resolution < 90:
            score = 4
            risk = "Medium"
            message = f"Moderate: Avg issue resolution {avg_resolution:.1f} days. Consider improving."
        elif avg_resolution < 180:
            score = 2
            risk = "High"
            message = f"Slow: Avg issue resolution {avg_resolution:.1f} days. Issues backlogging."
        else:
            score = 0
            risk = "High"
            message = f"Observe: Avg issue resolution {avg_resolution:.1f} days. Significant backlog detected."

    return Metric("Issue Resolution Duration", score, max_score, message, risk)


def check_organizational_diversity(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates Organizational Diversity (CHAOSS metric).

    Measures diversity of contributor affiliations based on:
    - Email domains (heuristic)
    - Company field from GitHub profiles

    A diverse contributor base reduces single-organization dependency risk.

    Scoring:
    - 5+ organizations: 10/10 (Highly diverse)
    - 3-4 organizations: 7/10 (Good diversity)
    - 2 organizations: 4/10 (Moderate)
    - Single organization: 0/10 (Single-org risk)
    """
    max_score = 10

    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
        return Metric(
            "Organizational Diversity",
            max_score // 2,
            max_score,
            "Note: Commit history data not available.",
            "None",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Organizational Diversity",
            max_score // 2,
            max_score,
            "Note: Commit history data not available.",
            "None",
        )

    history = target.get("history", {}).get("edges", [])
    if not history:
        return Metric(
            "Organizational Diversity",
            max_score // 2,
            max_score,
            "Note: No commit history for analysis.",
            "None",
        )

    # Bot patterns to exclude (same as check_bus_factor)
    bot_keywords = [
        "bot",
        "action",
        "dependabot",
        "renovate",
        "github-actions",
        "ci-",
        "autorelease",
        "release-bot",
        "copilot",
        "actions-user",
    ]

    def is_bot(login: str) -> bool:
        """Check if login appears to be a bot."""
        lower = login.lower()
        return any(keyword in lower for keyword in bot_keywords)

    # Collect organization signals
    organizations: set[str] = set()
    email_domains: set[str] = set()

    for edge in history:
        node = edge.get("node", {})
        author = node.get("author", {})

        # Check company field
        user = author.get("user")
        if user:
            login = user.get("login")
            # Skip bots
            if login and is_bot(login):
                continue

            company = user.get("company")
            if company and len(company) > 1:
                # Normalize company name
                company_clean = company.strip().lower().replace("@", "")
                if company_clean:
                    organizations.add(company_clean)

        # Check email domain
        email = author.get("email")
        if email and "@" in email:
            domain = email.split("@")[-1].lower()
            # Filter out common free email providers
            free_providers = {
                "gmail.com",
                "yahoo.com",
                "hotmail.com",
                "outlook.com",
                "users.noreply.github.com",
                "localhost",
            }
            if domain not in free_providers and "." in domain:
                email_domains.add(domain)

    # Combine signals (prefer organizations, fall back to domains)
    total_orgs = len(organizations)
    total_domains = len(email_domains)
    diversity_score = max(total_orgs, total_domains)

    # Scoring logic
    if diversity_score >= 5:
        score = max_score
        risk = "None"
        message = f"Excellent: {diversity_score} organizations/domains detected. Highly diverse."
    elif diversity_score >= 3:
        score = 7
        risk = "Low"
        message = (
            f"Good: {diversity_score} organizations/domains detected. Good diversity."
        )
    elif diversity_score >= 2:
        score = 4
        risk = "Medium"
        message = f"Moderate: {diversity_score} organizations/domains detected. Consider expanding."
    elif diversity_score == 1:
        score = 2
        risk = "High"
        message = "Observe: Single organization dominates. Dependency risk exists."
    else:
        score = max_score // 2
        risk = "None"
        message = "Note: Unable to determine organizational diversity (personal project likely)."

    return Metric("Organizational Diversity", score, max_score, message, risk)


def check_fork_activity(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates active fork development as a signal of ecosystem health and fork risk.

    Considers:
    - Total fork count
    - Active forks with recent commits (last 6 months)
    - Fork divergence risk (high active fork ratio)

    Active forking indicates:
    - Community interest and adoption
    - Potential future contributors
    - Fork/divergence risk if too many active forks

    Scoring:
    - Low active fork ratio (<20%) with high total forks: 5/5 (Healthy ecosystem)
    - Moderate active fork ratio (20-40%): 3-4/5 (Monitor divergence)
    - High active fork ratio (>40%): 1-2/5 (Needs attention - fork risk)
    - Few forks but some active: 2-3/5 (Growing)
    - No forks: 0/5 (New/niche)
    """
    from datetime import datetime, timedelta, timezone

    max_score = 10

    fork_count = repo_data.get("forkCount", 0)
    fork_edges = repo_data.get("forks", {}).get("edges", [])

    # No forks - new or niche project
    if fork_count == 0:
        return Metric(
            "Active Fork Analysis",
            0,
            max_score,
            "Note: No forks yet. Project may be new or niche.",
            "Low",
        )

    # Analyze active development in forks (last 6 months)
    now = datetime.now(timezone.utc)
    six_months_ago = now - timedelta(days=180)
    active_fork_count = 0
    recently_created_forks = 0
    three_months_ago = now - timedelta(days=90)

    for edge in fork_edges:
        node = edge.get("node", {})

        # Check fork creation date
        created_at_str = node.get("createdAt")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
                if created_at >= three_months_ago:
                    recently_created_forks += 1
            except (ValueError, AttributeError):
                pass

        # Check for active development (recent commits)
        pushed_at_str = node.get("pushedAt")
        if pushed_at_str:
            try:
                pushed_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
                if pushed_at >= six_months_ago:
                    # Verify with commit date if available
                    default_branch = node.get("defaultBranchRef")
                    if default_branch:
                        target = default_branch.get("target", {})
                        history = target.get("history", {}).get("edges", [])
                        if history:
                            last_commit = history[0].get("node", {})
                            committed_date_str = last_commit.get("committedDate")
                            if committed_date_str:
                                committed_date = datetime.fromisoformat(
                                    committed_date_str.replace("Z", "+00:00")
                                )
                                if committed_date >= six_months_ago:
                                    active_fork_count += 1
                    elif pushed_at >= six_months_ago:
                        # Fallback: use push date if commit history unavailable
                        active_fork_count += 1
            except (ValueError, AttributeError, TypeError):
                pass

    # Calculate active fork ratio (only for sample, approximate for total)
    # Note: We only fetch top 20 forks, so this is an approximation
    sample_size = len(fork_edges)
    active_fork_ratio = (
        (active_fork_count / sample_size * 100) if sample_size > 0 else 0
    )

    # Scoring logic based on fork patterns (0-10 scale)
    if fork_count >= 100:
        # Large ecosystem - assess health and divergence risk
        if active_fork_ratio < 20:
            score = max_score  # 5/5 → 10/10
            risk = "None"
            message = f"Excellent: {fork_count} forks, ~{active_fork_count}/{sample_size} active. Healthy ecosystem with low divergence risk."
        elif active_fork_ratio < 40:
            score = 6  # 3/5 → 6/10
            risk = "Low"
            message = f"Monitor: {fork_count} forks, ~{active_fork_count}/{sample_size} active. Consider community alignment efforts."
        else:
            score = 2  # 1/5 → 2/10, high divergence risk
            risk = "Medium"
            message = f"Needs attention: {fork_count} forks, ~{active_fork_count}/{sample_size} active. High fork divergence risk detected."
    elif fork_count >= 50:
        # Medium ecosystem
        if active_fork_ratio < 30:
            score = 8  # 4/5 → 8/10
            risk = "None"
            message = f"Good: {fork_count} forks, ~{active_fork_count}/{sample_size} active. Growing ecosystem."
        else:
            score = 4  # 2/5 → 4/10
            risk = "Low"
            message = f"Monitor: {fork_count} forks, ~{active_fork_count}/{sample_size} active. Watch for divergence."
    elif fork_count >= 10:
        # Smaller ecosystem
        if active_fork_count >= 2:
            score = 6  # 3/5 → 6/10
            risk = "None"
            message = f"Moderate: {fork_count} forks, {active_fork_count} active. Growing community interest."
        else:
            score = 4  # 2/5 → 4/10
            risk = "None"
            message = f"Early: {fork_count} forks, {active_fork_count} active. Small community."
    else:
        # Very small ecosystem
        if active_fork_count > 0:
            score = 4  # 2/5 → 4/10
            risk = "Low"
            message = f"Early: {fork_count} fork(s), {active_fork_count} active. Emerging interest."
        else:
            score = 2  # 1/5 → 2/10
            risk = "Low"
            message = f"Limited: {fork_count} fork(s), no recent activity detected."

    return Metric("Active Fork Analysis", score, max_score, message, risk)


def check_project_popularity(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates project popularity using GitHub signals.

    Considers:
    - Star count (primary indicator)
    - Watcher count
    - Fork count (as adoption signal)

    Note: Popularity doesn't guarantee sustainability,
    but indicates community interest and potential support.

    Scoring:
    - 1000+ stars: 10/10 (Very popular)
    - 500-999 stars: 8/10 (Popular)
    - 100-499 stars: 6/10 (Growing)
    - 50-99 stars: 4/10 (Emerging)
    - 10-49 stars: 2/10 (Early)
    - <10 stars: 0/10 (New/niche)
    """
    max_score = 10

    star_count = repo_data.get("stargazerCount", 0)
    watcher_count = repo_data.get("watchers", {}).get("totalCount", 0)

    # Primary scoring based on stars
    if star_count >= 1000:
        score = max_score
        risk = "None"
        message = (
            f"Excellent: ⭐ {star_count} stars, {watcher_count} watchers. Very popular."
        )
    elif star_count >= 500:
        score = 8
        risk = "None"
        message = f"Popular: ⭐ {star_count} stars, {watcher_count} watchers."
    elif star_count >= 100:
        score = 6
        risk = "None"
        message = f"Growing: ⭐ {star_count} stars, {watcher_count} watchers. Active interest."
    elif star_count >= 50:
        score = 4
        risk = "Low"
        message = f"Emerging: ⭐ {star_count} stars. Building community."
    elif star_count >= 10:
        score = 2
        risk = "Low"
        message = f"Early: ⭐ {star_count} stars. New or niche project."
    else:
        score = 0
        risk = "Low"
        message = f"Note: ⭐ {star_count} stars. Very new or specialized project."

    return Metric("Project Popularity", score, max_score, message, risk)


def check_license_clarity(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates license clarity and OSI approval status.

    A clear, OSI-approved license is essential for:
    - Legal clarity
    - Enterprise adoption
    - Community trust

    Scoring:
    - OSI-approved license (MIT, Apache, GPL, etc.): 5/5
    - Other recognized license: 3/5
    - No license detected: 0/5 (High risk for users)
    """
    max_score = 10

    license_info = repo_data.get("licenseInfo")

    if not license_info:
        return Metric(
            "License Clarity",
            0,
            max_score,
            "Attention: No license detected. Add a license for legal clarity.",
            "High",
        )

    license_name = license_info.get("name", "Unknown")
    spdx_id = license_info.get("spdxId")

    # Common OSI-approved licenses
    osi_approved = {
        "MIT",
        "Apache-2.0",
        "GPL-2.0",
        "GPL-3.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "MPL-2.0",
        "LGPL-2.1",
        "LGPL-3.0",
        "EPL-2.0",
        "AGPL-3.0",
        "Unlicense",
        "CC0-1.0",
    }

    if spdx_id and spdx_id in osi_approved:
        score = max_score
        risk = "None"
        message = f"Excellent: {license_name} (OSI-approved). Clear licensing."
    elif spdx_id:
        score = 6
        risk = "Low"
        message = (
            f"Good: {license_name} detected. Verify compatibility for your use case."
        )
    else:
        score = 4
        risk = "Medium"
        message = (
            f"Note: {license_name} detected but not recognized. Review license terms."
        )

    return Metric("License Clarity", score, max_score, message, risk)


def check_pr_responsiveness(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates responsiveness to pull requests (first reaction time).

    Distinct from Review Health - focuses on initial engagement speed.

    Fast initial response encourages contributors to stay engaged.

    Scoring:
    - Avg first response <24h: 5/5 (Excellent)
    - Avg first response <7d: 3/5 (Good)
    - Avg first response >7d: 0/5 (Needs improvement)
    """
    from datetime import datetime

    max_score = 10

    # Check closed PRs for first response time
    closed_prs = repo_data.get("closedPullRequests", {}).get("edges", [])

    if not closed_prs:
        return Metric(
            "PR Responsiveness",
            max_score // 2,
            max_score,
            "Note: No closed PRs to analyze responsiveness.",
            "None",
        )

    response_times: list[float] = []

    for edge in closed_prs:
        node = edge.get("node", {})
        created_at_str = node.get("createdAt")
        reviews = node.get("reviews", {}).get("edges", [])

        if not created_at_str or not reviews:
            continue

        first_review = reviews[0].get("node", {})
        first_review_at_str = first_review.get("createdAt")

        if not first_review_at_str:
            continue

        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            first_review_at = datetime.fromisoformat(
                first_review_at_str.replace("Z", "+00:00")
            )
            response_hours = (first_review_at - created_at).total_seconds() / 3600
            response_times.append(response_hours)
        except (ValueError, AttributeError):
            pass

    if not response_times:
        return Metric(
            "PR Responsiveness",
            2,
            max_score,
            "Note: Unable to measure PR response times.",
            "None",
        )

    avg_response = sum(response_times) / len(response_times)

    # Scoring logic
    if avg_response < 24:
        score = max_score
        risk = "None"
        message = (
            f"Excellent: Avg PR first response {avg_response:.1f}h. Very responsive."
        )
    elif avg_response < 168:  # 7 days
        score = 6
        risk = "Low"
        message = f"Good: Avg PR first response {avg_response / 24:.1f}d."
    else:
        score = 0
        risk = "Medium"
        message = f"Observe: Avg PR first response {avg_response / 24:.1f}d. Contributors may wait long."

    return Metric("PR Responsiveness", score, max_score, message, risk)


def check_stale_issue_ratio(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates Stale Issue Ratio - percentage of issues not updated in 90+ days.

    Measures how well the project manages its issue backlog.
    High stale issue ratio indicates potential burnout or backlog accumulation.

    Scoring:
    - <15% stale: 5/5 (Healthy backlog management)
    - 15-30% stale: 3/5 (Acceptable)
    - 30-50% stale: 2/5 (Needs attention)
    - >50% stale: 1/5 (Significant backlog challenge)

    CHAOSS Aligned: Issue aging and backlog management
    """
    from datetime import datetime, timedelta

    max_score = 10

    # Check closed issues for stale ratio
    closed_issues = repo_data.get("closedIssues", {}).get("edges", [])

    if not closed_issues:
        return Metric(
            "Stale Issue Ratio",
            max_score // 2,
            max_score,
            "Note: No closed issues in recent history.",
            "None",
        )

    stale_count = 0
    current_time = datetime.now(datetime.now().astimezone().tzinfo)
    stale_threshold = current_time - timedelta(days=90)

    for edge in closed_issues:
        node = edge.get("node", {})
        updated_at_str = node.get("updatedAt") or node.get("closedAt")

        if not updated_at_str:
            continue

        try:
            updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            if updated_at < stale_threshold:
                stale_count += 1
        except (ValueError, AttributeError):
            pass

    total_issues = len(closed_issues)
    if total_issues == 0:
        return Metric(
            "Stale Issue Ratio",
            5,
            max_score,
            "Note: Unable to calculate stale issue ratio.",
            "None",
        )

    stale_ratio = (stale_count / total_issues) * 100

    # Scoring logic
    if stale_ratio < 15:
        score = max_score
        risk = "None"
        message = (
            f"Healthy: {stale_ratio:.1f}% of issues are stale (90+ days inactive)."
        )
    elif stale_ratio < 30:
        score = 6
        risk = "Low"
        message = f"Acceptable: {stale_ratio:.1f}% of issues are stale."
    elif stale_ratio < 50:
        score = 4
        risk = "Medium"
        message = f"Observe: {stale_ratio:.1f}% of issues are stale. Consider review."
    else:
        score = 2
        risk = "High"
        message = f"Significant: {stale_ratio:.1f}% of issues are stale. Backlog accumulation evident."

    return Metric("Stale Issue Ratio", score, max_score, message, risk)


def check_pr_merge_speed(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates PR Merge Speed - median time from PR creation to merge.

    Measures the efficiency of the pull request review and merge process.
    Faster merge times indicate responsive review cycles.

    Scoring:
    - Median <3 days: 5/5 (Excellent)
    - Median 3-7 days: 4/5 (Good)
    - Median 7-30 days: 2/5 (Moderate)
    - Median >30 days: 1/5 (Slow)

    CHAOSS Aligned: Code Development Efficiency
    """
    from datetime import datetime

    max_score = 10

    # Check merged PRs
    merged_prs = repo_data.get("pullRequests", {}).get("edges", [])

    if not merged_prs:
        return Metric(
            "PR Merge Speed",
            5,
            max_score,
            "Note: No merged PRs available for analysis.",
            "None",
        )

    merge_times: list[float] = []

    for edge in merged_prs:
        node = edge.get("node", {})
        created_at_str = node.get("createdAt")
        merged_at_str = node.get("mergedAt")

        if not created_at_str or not merged_at_str:
            continue

        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            merged_at = datetime.fromisoformat(merged_at_str.replace("Z", "+00:00"))
            merge_days = (merged_at - created_at).total_seconds() / 86400
            merge_times.append(merge_days)
        except (ValueError, AttributeError):
            pass

    if not merge_times:
        return Metric(
            "PR Merge Speed",
            5,
            max_score,
            "Note: Unable to calculate PR merge times.",
            "None",
        )

    # Calculate median (middle value)
    merge_times.sort()
    median_merge_days = (
        merge_times[len(merge_times) // 2]
        if len(merge_times) % 2 == 1
        else (
            merge_times[len(merge_times) // 2 - 1] + merge_times[len(merge_times) // 2]
        )
        / 2
    )

    # Scoring logic
    if median_merge_days < 3:
        score = max_score
        risk = "None"
        message = f"Excellent: Median PR merge time {median_merge_days:.1f}d. Responsive review cycle."
    elif median_merge_days < 7:
        score = 8
        risk = "Low"
        message = f"Good: Median PR merge time {median_merge_days:.1f}d."
    elif median_merge_days < 30:
        score = 4
        risk = "Medium"
        message = f"Moderate: Median PR merge time {median_merge_days:.1f}d."
    else:
        score = 2
        risk = "High"
        message = f"Observe: Median PR merge time {median_merge_days:.1f}d. Review cycle is slow."

    return Metric("PR Merge Speed", score, max_score, message, risk)


def check_single_maintainer_load(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates maintainer workload distribution using Gini coefficient.

    Measures concentration of Issue/PR closing activity among contributors.
    High concentration (high Gini) indicates risk of single maintainer burnout.

    The Gini coefficient ranges from 0 (perfect equality) to 1 (maximum inequality).
    Lower values indicate more distributed workload across maintainers.

    Scoring:
    - Gini < 0.3: 5/5 (Well distributed - healthy team)
    - Gini 0.3-0.5: 3/5 (Moderate - some concentration)
    - Gini 0.5-0.7: 2/5 (High concentration - monitor)
    - Gini > 0.7: 1/5 (Very high concentration - needs support)

    CHAOSS Aligned: Contributor Diversity and Bus Factor
    """
    max_score = 10

    # Collect PR and Issue closers
    closer_counts: dict[str, int] = {}

    # Count PR closers (merged PRs)
    merged_prs = repo_data.get("pullRequests", {}).get("edges", [])
    for edge in merged_prs:
        node = edge.get("node", {})
        merged_by = node.get("mergedBy")
        if merged_by and isinstance(merged_by, dict):
            login = merged_by.get("login")
            if login:
                closer_counts[login] = closer_counts.get(login, 0) + 1

    # Count Issue closers (from timeline events)
    closed_issues = repo_data.get("closedIssues", {}).get("edges", [])
    for edge in closed_issues:
        node = edge.get("node", {})
        timeline_items = node.get("timelineItems", {}).get("edges", [])

        for timeline_edge in timeline_items:
            timeline_node = timeline_edge.get("node", {})
            actor = timeline_node.get("actor")
            if actor and isinstance(actor, dict):
                login = actor.get("login")
                if login:
                    closer_counts[login] = closer_counts.get(login, 0) + 1
                    break  # Only count the first closer

    if not closer_counts:
        return Metric(
            "Maintainer Load Distribution",
            max_score // 2,
            max_score,
            "Note: No Issue/PR closing activity to analyze.",
            "None",
        )

    # Calculate Gini coefficient
    # Sort counts in ascending order
    counts = sorted(closer_counts.values())
    n = len(counts)

    if n == 1:
        # Single maintainer - maximum concentration
        gini = 1.0
    else:
        # Calculate Gini coefficient using the formula:
        # Gini = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n + 1) / n
        total = sum(counts)
        weighted_sum = sum((i + 1) * count for i, count in enumerate(counts))
        gini = (2 * weighted_sum) / (n * total) - (n + 1) / n

    # Scoring logic based on Gini coefficient
    if gini < 0.3:
        score = max_score
        risk = "None"
        message = (
            f"Healthy: Workload well distributed (Gini {gini:.2f}). "
            f"{n} contributors share Issue/PR closing duties."
        )
    elif gini < 0.5:
        score = 6
        risk = "Low"
        message = (
            f"Moderate: Some workload concentration (Gini {gini:.2f}). "
            f"{n} contributors with varying activity levels."
        )
    elif gini < 0.7:
        score = 4
        risk = "Medium"
        message = (
            f"Observe: High workload concentration (Gini {gini:.2f}). "
            f"Consider expanding maintainer team from {n} contributors."
        )
    else:
        score = 2
        risk = "High"
        message = (
            f"Needs support: Very high workload concentration (Gini {gini:.2f}). "
            f"Single maintainer burden evident among {n} contributor(s)."
        )

    return Metric("Maintainer Load Distribution", score, max_score, message, risk)


def check_dependents_count(
    repo_url: str, platform: str | None = None, package_name: str | None = None
) -> Metric | None:
    """
    Evaluates package adoption by counting downstream dependents.

    Uses Libraries.io API to determine how many other packages
    depend on this package. High dependents count indicates:
    - Wide adoption and trust
    - Critical infrastructure importance
    - Strong motivation for maintenance

    Note:
        Requires LIBRARIESIO_API_KEY environment variable.
        Get free API key at: https://libraries.io/api

    Args:
        repo_url: GitHub repository URL
        platform: Package platform (e.g., 'Pypi', 'NPM', 'Cargo')
        package_name: Package name on the registry

    Returns:
        Metric with dependents count analysis, or None if API not configured

    Scoring:
        - 10000+ dependents: 20/20 (Critical infrastructure)
        - 1000+ dependents: 18/20 (Widely adopted)
        - 500+ dependents: 15/20 (Popular)
        - 100+ dependents: 12/20 (Established)
        - 50+ dependents: 9/20 (Growing adoption)
        - 10+ dependents: 6/20 (Early adoption)
        - 1+ dependents: 3/20 (Used by others)
        - 0 dependents: 0/20 (No downstream dependencies)

    Note: Docstring shows old 20-point scale but function now uses 10-point scale internally.
    """
    max_score = 10

    # Check if Libraries.io API is configured (check environment at runtime)
    api_key = os.getenv("LIBRARIESIO_API_KEY")
    if not api_key:
        return None  # Skip metric if API key not available

    # If platform or package_name not provided, cannot query
    if not platform or not package_name:
        return None

    # Query Libraries.io API
    package_info = _query_librariesio_api(platform, package_name)

    if not package_info:
        # API call failed or package not found
        return Metric(
            "Downstream Dependents",
            0,
            max_score,
            f"ℹ️  Package not found on {platform} registry via Libraries.io.",
            "Low",
        )

    dependents_count = package_info.get("dependents_count", 0)
    dependent_repos_count = package_info.get("dependent_repos_count", 0)

    # Score based on dependents count (scaled to 10-point system)
    if dependents_count >= 10000:
        score = max_score  # 20/20 → 10/10
        risk = "None"
        message = f"Critical infrastructure: 📦 {dependents_count:,} packages depend on this ({dependent_repos_count:,} repos). Essential to ecosystem."
    elif dependents_count >= 1000:
        score = 9  # 18/20 → 9/10
        risk = "None"
        message = f"Widely adopted: 📦 {dependents_count:,} packages depend on this ({dependent_repos_count:,} repos)."
    elif dependents_count >= 500:
        score = 8  # 15/20 → 8/10 (rounded up)
        risk = "None"
        message = f"Popular: 📦 {dependents_count:,} packages depend on this ({dependent_repos_count:,} repos)."
    elif dependents_count >= 100:
        score = 6  # 12/20 → 6/10
        risk = "Low"
        message = f"Established: 📦 {dependents_count} packages depend on this ({dependent_repos_count} repos)."
    elif dependents_count >= 50:
        score = 5  # 9/20 → 5/10 (rounded up)
        risk = "Low"
        message = f"Growing adoption: 📦 {dependents_count} packages depend on this ({dependent_repos_count} repos)."
    elif dependents_count >= 10:
        score = 3  # 6/20 → 3/10
        risk = "Low"
        message = f"Early adoption: 📦 {dependents_count} packages depend on this ({dependent_repos_count} repos)."
    elif dependents_count >= 1:
        score = 2  # 3/20 → 2/10 (rounded up)
        risk = "Low"
        message = f"Used by others: 📦 {dependents_count} package(s) depend on this ({dependent_repos_count} repo(s))."
    else:
        score = 0
        risk = "Low"
        message = "ℹ️  No downstream dependencies detected. May be early-stage or application-focused."

    return Metric("Downstream Dependents", score, max_score, message, risk)


# --- Scoring System ---

# Metric weight definitions for different profiles
# All metrics are scored on a 0-10 scale
# Weights are integers (1+) that determine relative importance
# Higher weight = more important to overall score
# Total score = Sum(metric_score × weight) / Sum(10 × weight) × 100

# Scoring profiles for different use cases
# Each profile adjusts metric weights based on specific priorities
DEFAULT_SCORING_PROFILES = {
    "balanced": {
        "name": "Balanced",
        "description": "Balanced view across all sustainability dimensions",
        "weights": {
            # Maintainer Health (25% emphasis)
            "Contributor Redundancy": 3,
            "Maintainer Retention": 2,
            "Contributor Attraction": 2,
            "Contributor Retention": 2,
            "Organizational Diversity": 2,
            "Maintainer Load Distribution": 2,
            # Development Activity (20% emphasis)
            "Recent Activity": 3,
            "Release Rhythm": 2,
            "Build Health": 2,
            "Change Request Resolution": 2,
            # Community Engagement (25% emphasis)
            "Issue Responsiveness": 2,
            "PR Acceptance Ratio": 2,
            "Review Health": 2,
            "Issue Resolution Duration": 2,
            "Stale Issue Ratio": 2,
            "PR Merge Speed": 2,
            # Project Maturity (15% emphasis)
            "Documentation Presence": 2,
            "Code of Conduct": 1,
            "License Clarity": 1,
            "Project Popularity": 2,
            "Fork Activity": 1,
            # Security & Funding (15% emphasis)
            "Security Signals": 2,
            "Funding Signals": 2,
            # PR Responsiveness
            "PR Responsiveness": 1,
        },
    },
    "security_first": {
        "name": "Security First",
        "description": "Prioritizes security and risk mitigation",
        "weights": {
            # Maintainer Health (20% emphasis)
            "Contributor Redundancy": 2,
            "Maintainer Retention": 2,
            "Contributor Attraction": 1,
            "Contributor Retention": 1,
            "Organizational Diversity": 2,
            "Maintainer Load Distribution": 1,
            # Development Activity (15% emphasis)
            "Recent Activity": 2,
            "Release Rhythm": 2,
            "Build Health": 3,
            "Change Request Resolution": 1,
            # Community Engagement (20% emphasis)
            "Issue Responsiveness": 2,
            "PR Acceptance Ratio": 1,
            "Review Health": 2,
            "Issue Resolution Duration": 1,
            "Stale Issue Ratio": 1,
            "PR Merge Speed": 2,
            # Project Maturity (15% emphasis)
            "Documentation Presence": 2,
            "Code of Conduct": 1,
            "License Clarity": 2,
            "Project Popularity": 1,
            "Fork Activity": 1,
            # Security & Funding (30% emphasis) - INCREASED
            "Security Signals": 4,
            "Funding Signals": 3,
            # PR Responsiveness
            "PR Responsiveness": 1,
        },
    },
    "contributor_experience": {
        "name": "Contributor Experience",
        "description": "Focuses on community engagement and contributor-friendliness",
        "weights": {
            # Maintainer Health (15% emphasis)
            "Contributor Redundancy": 1,
            "Maintainer Retention": 1,
            "Contributor Attraction": 2,
            "Contributor Retention": 2,
            "Organizational Diversity": 1,
            "Maintainer Load Distribution": 1,
            # Development Activity (15% emphasis)
            "Recent Activity": 2,
            "Release Rhythm": 1,
            "Build Health": 1,
            "Change Request Resolution": 2,
            # Community Engagement (45% emphasis) - DOUBLED
            "Issue Responsiveness": 4,
            "PR Acceptance Ratio": 4,
            "Review Health": 3,
            "Issue Resolution Duration": 3,
            "Stale Issue Ratio": 2,
            "PR Merge Speed": 3,
            # Project Maturity (15% emphasis)
            "Documentation Presence": 2,
            "Code of Conduct": 2,
            "License Clarity": 1,
            "Project Popularity": 1,
            "Fork Activity": 1,
            # Security & Funding (10% emphasis)
            "Security Signals": 1,
            "Funding Signals": 1,
            # PR Responsiveness
            "PR Responsiveness": 3,
        },
    },
    "long_term_stability": {
        "name": "Long-term Stability",
        "description": "Emphasizes maintainer health and sustainable development",
        "weights": {
            # Maintainer Health (35% emphasis) - HIGHEST
            "Contributor Redundancy": 4,
            "Maintainer Retention": 3,
            "Contributor Attraction": 2,
            "Contributor Retention": 3,
            "Organizational Diversity": 3,
            "Maintainer Load Distribution": 3,
            # Development Activity (25% emphasis)
            "Recent Activity": 3,
            "Release Rhythm": 3,
            "Build Health": 2,
            "Change Request Resolution": 2,
            # Community Engagement (15% emphasis)
            "Issue Responsiveness": 1,
            "PR Acceptance Ratio": 1,
            "Review Health": 2,
            "Issue Resolution Duration": 1,
            "Stale Issue Ratio": 1,
            "PR Merge Speed": 1,
            # Project Maturity (15% emphasis)
            "Documentation Presence": 2,
            "Code of Conduct": 1,
            "License Clarity": 1,
            "Project Popularity": 1,
            "Fork Activity": 1,
            # Security & Funding (10% emphasis)
            "Security Signals": 1,
            "Funding Signals": 2,
            # PR Responsiveness
            "PR Responsiveness": 1,
        },
    },
}

SCORING_PROFILES = copy.deepcopy(DEFAULT_SCORING_PROFILES)


def apply_profile_overrides(profile_overrides: dict[str, dict[str, object]]) -> None:
    """
    Apply external scoring profile overrides on top of defaults.

    Args:
        profile_overrides: Profile definitions loaded from config.

    Raises:
        ValueError: If profile definitions are missing metrics or include invalid values.
    """
    global SCORING_PROFILES
    if not profile_overrides:
        SCORING_PROFILES = copy.deepcopy(DEFAULT_SCORING_PROFILES)
        return

    required_metrics = set(DEFAULT_SCORING_PROFILES["balanced"]["weights"].keys())
    merged = copy.deepcopy(DEFAULT_SCORING_PROFILES)

    for profile_key, profile_data in profile_overrides.items():
        if not isinstance(profile_data, dict):
            raise ValueError(
                f"Profile '{profile_key}' should be a table with name, description, and weights."
            )

        weights = profile_data.get("weights")
        if weights is None:
            if profile_key not in merged:
                raise ValueError(
                    f"Profile '{profile_key}' needs a weights table to be defined."
                )
            weights = merged[profile_key]["weights"]
        else:
            if not isinstance(weights, dict):
                raise ValueError(
                    f"Profile '{profile_key}' weights should be a table of metric names to integers."
                )

            missing_metrics = required_metrics - weights.keys()
            if missing_metrics:
                missing_list = ", ".join(sorted(missing_metrics))
                raise ValueError(
                    f"Profile '{profile_key}' is missing metrics: {missing_list}."
                )

            unknown_metrics = set(weights.keys()) - required_metrics
            if unknown_metrics:
                unknown_list = ", ".join(sorted(unknown_metrics))
                raise ValueError(
                    f"Profile '{profile_key}' includes unknown metrics: {unknown_list}."
                )

            invalid_weights = {
                metric: value
                for metric, value in weights.items()
                if type(value) is not int or value < 1
            }
            if invalid_weights:
                invalid_list = ", ".join(
                    f"{metric}={value}" for metric, value in invalid_weights.items()
                )
                raise ValueError(
                    "Profile weights must be integers greater than or equal to 1. "
                    f"Invalid values: {invalid_list}."
                )

        profile_name = profile_data.get(
            "name", merged.get(profile_key, {}).get("name", profile_key)
        )
        profile_description = profile_data.get(
            "description", merged.get(profile_key, {}).get("description", "")
        )
        merged[profile_key] = {
            "name": profile_name,
            "description": profile_description,
            "weights": weights,
        }

    SCORING_PROFILES = merged


def compute_weighted_total_score(
    metrics: list[Metric], profile: str = "balanced"
) -> int:
    """
    Computes a weighted total score based on individual metric weights.

    New scoring system (v2.0):
    - All metrics are scored on a 0-10 scale
    - Each metric has a weight (integer ≥ 1) defined per profile
    - Total score = Sum(metric_score × weight) / Sum(10 × weight) × 100
    - Result is normalized to 0-100 scale

    This approach provides:
    - Transparency: Users see individual scores (0-10) and weights
    - Flexibility: Easy to add new metrics - just assign a score and weight
    - Consistency: No confusion about why max_score differs per metric

    Profiles:
    - balanced: Balanced view (default)
    - security_first: Prioritizes security
    - contributor_experience: Focuses on community
    - long_term_stability: Emphasizes maintainer health

    Args:
        metrics: List of computed Metric instances
        profile: Scoring profile name (default: "balanced")

    Returns:
        Total score on 0-100 scale

    Raises:
        ValueError: If profile is not recognized
    """
    if profile not in SCORING_PROFILES:
        raise ValueError(
            f"Unknown profile '{profile}'. Available: {', '.join(SCORING_PROFILES.keys())}"
        )

    profile_config = SCORING_PROFILES[profile]
    weights = profile_config["weights"]

    # Calculate weighted sum
    weighted_score_sum = 0.0
    weighted_max_sum = 0.0

    for m in metrics:
        metric_weight = weights.get(m.name, 1)  # Default weight = 1 if not specified
        weighted_score_sum += m.score * metric_weight
        weighted_max_sum += 10 * metric_weight  # All metrics are now 0-10 scale

    # Normalize to 0-100 scale
    if weighted_max_sum > 0:
        total_score = (weighted_score_sum / weighted_max_sum) * 100
    else:
        total_score = 0.0

    return int(round(total_score))


def compare_scoring_profiles(metrics: list[Metric]) -> dict[str, dict[str, Any]]:
    """
    Compares scores across all available scoring profiles.

    Useful for understanding how different priorities affect the total score
    and identifying which profile best matches your use case.

    Args:
        metrics: List of computed Metric instances

    Returns:
        Dictionary with profile names as keys, containing:
        - name: Profile display name
        - description: Profile description
        - total_score: Total score (0-100) for this profile
        - weights: Metric weights used in this profile
    """
    comparison: dict[str, dict[str, Any]] = {}

    # Calculate total score for each profile
    for profile_key, profile_config in SCORING_PROFILES.items():
        total_score = compute_weighted_total_score(metrics, profile_key)

        comparison[profile_key] = {
            "name": profile_config["name"],
            "description": profile_config["description"],
            "total_score": total_score,
            "weights": profile_config["weights"],
        }

    return comparison


def get_metric_weights(profile: str = "balanced") -> dict[str, int]:
    """
    Returns the metric weights for a given profile.

    Args:
        profile: Scoring profile name (default: "balanced")

    Returns:
        Dictionary mapping metric names to their weights

    Raises:
        ValueError: If profile is not recognized
    """
    if profile not in SCORING_PROFILES:
        raise ValueError(
            f"Unknown profile '{profile}'. Available: {', '.join(SCORING_PROFILES.keys())}"
        )

    return SCORING_PROFILES[profile]["weights"]


# --- Metric Model Calculation Functions ---


def compute_metric_models(metrics: list[Metric]) -> list[MetricModel]:
    """
    Computes CHAOSS-aligned metric models from individual metrics.

    Models provide aggregated views for specific use cases:
    - Risk Model: focuses on project stability and security
    - Sustainability Model: focuses on long-term viability
    - Community Engagement Model: focuses on responsiveness and activity

    Args:
        metrics: List of computed individual metrics

    Returns:
        List of MetricModel instances
    """
    # Create a lookup dict for easy metric access
    metric_dict = {m.name: m for m in metrics}

    models = []

    # Risk Model: weights Contributor Redundancy, Security Signals,
    # Change Request Resolution, Issue Responsiveness
    risk_metrics = [
        ("Contributor Redundancy", 0.4),
        ("Security Signals", 0.3),
        ("Change Request Resolution", 0.2),
        ("Issue Responsiveness", 0.1),
    ]
    risk_score = 0
    risk_max = 0
    risk_observations = []

    for metric_name, weight in risk_metrics:
        if metric_name in metric_dict:
            m = metric_dict[metric_name]
            risk_score += m.score * weight
            risk_max += m.max_score * weight
            if m.score < m.max_score * 0.7:  # Below 70%
                risk_observations.append(f"{metric_name} needs attention")

    if not risk_observations:
        risk_obs = "All risk indicators are healthy."
    else:
        risk_obs = "; ".join(risk_observations[:2]) + "."  # Limit to 2

    models.append(
        MetricModel(
            name="Risk Model",
            score=int(risk_score),
            max_score=int(risk_max),
            observation=risk_obs,
        )
    )

    # Sustainability Model: weights Funding Signals, Maintainer Retention,
    # Release Rhythm, Recent Activity
    sustainability_metrics = [
        ("Funding Signals", 0.3),
        ("Maintainer Retention", 0.25),
        ("Release Rhythm", 0.25),
        ("Recent Activity", 0.2),
    ]
    sus_score = 0
    sus_max = 0
    sus_observations = []

    for metric_name, weight in sustainability_metrics:
        if metric_name in metric_dict:
            m = metric_dict[metric_name]
            sus_score += m.score * weight
            sus_max += m.max_score * weight
            if m.score >= m.max_score * 0.8:  # Above 80%
                sus_observations.append(f"{metric_name} is strong")

    if not sus_observations:
        sus_obs = "Sustainability signals need monitoring."
    else:
        sus_obs = "; ".join(sus_observations[:2]) + "."

    models.append(
        MetricModel(
            name="Sustainability Model",
            score=int(sus_score),
            max_score=int(sus_max),
            observation=sus_obs,
        )
    )

    # Community Engagement Model: weights Contributor Attraction,
    # Contributor Retention, Review Health, Issue Responsiveness
    engagement_metrics = [
        ("Contributor Attraction", 0.3),
        ("Contributor Retention", 0.3),
        ("Review Health", 0.25),
        ("Issue Responsiveness", 0.15),
    ]
    eng_score = 0
    eng_max = 0
    eng_observations = []

    for metric_name, weight in engagement_metrics:
        if metric_name in metric_dict:
            m = metric_dict[metric_name]
            eng_score += m.score * weight
            eng_max += m.max_score * weight
            if m.score >= m.max_score * 0.8:  # Above 80%
                eng_observations.append(f"{metric_name} is strong")

    if eng_max > 0:  # Only add model if we have at least one engagement metric
        if not eng_observations:
            eng_obs = "Community engagement signals need monitoring."
        else:
            eng_obs = "; ".join(eng_observations[:2]) + "."

        models.append(
            MetricModel(
                name="Community Engagement Model",
                score=int(eng_score),
                max_score=int(eng_max),
                observation=eng_obs,
            )
        )

    # Project Maturity Model (new): Documentation, Governance, Adoption
    maturity_metrics = [
        ("Documentation Presence", 0.30),
        ("Code of Conduct", 0.15),
        ("License Clarity", 0.20),
        ("Project Popularity", 0.20),
        ("Fork Activity", 0.15),
    ]
    mat_score = 0
    mat_max = 0
    mat_observations = []

    for metric_name, weight in maturity_metrics:
        if metric_name in metric_dict:
            m = metric_dict[metric_name]
            mat_score += m.score * weight
            mat_max += m.max_score * weight
            if m.score >= m.max_score * 0.8:  # Above 80%
                mat_observations.append(f"{metric_name} is strong")

    if mat_max > 0:
        if not mat_observations:
            mat_obs = "Project maturity signals need attention."
        else:
            mat_obs = "; ".join(mat_observations[:2]) + "."

        models.append(
            MetricModel(
                name="Project Maturity Model",
                score=int(mat_score),
                max_score=int(mat_max),
                observation=mat_obs,
            )
        )

    # Contributor Experience Model (new): PR handling and responsiveness
    exp_metrics = [
        ("PR Acceptance Ratio", 0.30),
        ("PR Responsiveness", 0.25),
        ("Issue Resolution Duration", 0.25),
        ("Review Health", 0.20),
    ]
    exp_score = 0
    exp_max = 0
    exp_observations = []

    for metric_name, weight in exp_metrics:
        if metric_name in metric_dict:
            m = metric_dict[metric_name]
            exp_score += m.score * weight
            exp_max += m.max_score * weight
            if m.score >= m.max_score * 0.8:
                exp_observations.append(f"{metric_name} is excellent")

    if exp_max > 0:
        if not exp_observations:
            exp_obs = "Contributor experience could be improved."
        else:
            exp_obs = "; ".join(exp_observations[:2]) + "."

        models.append(
            MetricModel(
                name="Contributor Experience Model",
                score=int(exp_score),
                max_score=int(exp_max),
                observation=exp_obs,
            )
        )

    return models


def extract_signals(metrics: list[Metric], repo_data: dict[str, Any]) -> dict[str, Any]:
    """
    Extracts raw signal values for transparency and debugging.

    Args:
        metrics: List of computed metrics
        repo_data: Raw repository data from GitHub API

    Returns:
        Dictionary of signal key-value pairs
    """
    signals = {}

    # Extract some key signals (non-sensitive)
    metric_dict = {m.name: m for m in metrics}

    if "Funding Signals" in metric_dict:
        funding_links = repo_data.get("fundingLinks", [])
        signals["funding_link_count"] = len(funding_links)

    if "Recent Activity" in metric_dict:
        pushed_at = repo_data.get("pushedAt")
        if pushed_at:
            from datetime import datetime

            try:
                pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
                now = datetime.now(pushed.tzinfo)
                signals["last_activity_days"] = (now - pushed).days
            except (ValueError, AttributeError):
                pass

    # Add contributor count if available
    default_branch = repo_data.get("defaultBranchRef")
    if default_branch:
        target = default_branch.get("target")
        if target:
            history = target.get("history", {}).get("edges", [])

            # Bot patterns to exclude (same as check_bus_factor)
            bot_keywords = [
                "bot",
                "action",
                "dependabot",
                "renovate",
                "github-actions",
                "ci-",
                "autorelease",
                "release-bot",
                "copilot",
                "actions-user",
            ]

            def is_bot(login: str) -> bool:
                """Check if login appears to be a bot."""
                lower = login.lower()
                return any(keyword in lower for keyword in bot_keywords)

            author_counts = {}
            for edge in history:
                node = edge.get("node", {})
                author = node.get("author", {})
                user = author.get("user")
                if user:
                    login = user.get("login")
                    if login and not is_bot(login):  # Exclude bots
                        author_counts[login] = author_counts.get(login, 0) + 1
            if author_counts:
                signals["contributor_count"] = len(author_counts)

    # Add new contributor metrics (Phase 4)
    if "Contributor Attraction" in metric_dict:
        m = metric_dict["Contributor Attraction"]
        # Extract new contributor count from message if available
        if "new contributor" in m.message.lower():
            import re

            match = re.search(r"(\d+) new contributor", m.message)
            if match:
                signals["new_contributors_6mo"] = int(match.group(1))

    if "Contributor Retention" in metric_dict:
        m = metric_dict["Contributor Retention"]
        # Extract retention percentage from message
        if "%" in m.message:
            import re

            match = re.search(r"(\d+)%", m.message)
            if match:
                signals["contributor_retention_rate"] = int(match.group(1))

    if "Review Health" in metric_dict:
        m = metric_dict["Review Health"]
        # Extract average review time from message
        if "Avg time to first review" in m.message:
            import re

            match = re.search(r"(\d+\.?\d*)h", m.message)
            if match:
                signals["avg_review_time_hours"] = float(match.group(1))

    return signals


# --- Batch Analysis Functions ---


def _get_batch_repository_query(repo_list: list[tuple[str, str]]) -> str:
    """Generate a GraphQL query for multiple repositories using aliases.

    Args:
        repo_list: List of (owner, name) tuples.

    Returns:
        GraphQL query string with aliases for each repository.
    """
    query_parts = ["query GetMultipleRepositories {"]

    for idx, (owner, name) in enumerate(repo_list):
        alias = f"repo{idx}"
        # Use the same comprehensive query as single repository analysis
        query_parts.append(f"""
  {alias}: repository(owner: "{owner}", name: "{name}") {{
    isArchived
    pushedAt
    owner {{
      __typename
      login
      ... on Organization {{
        name
        login
      }}
    }}
    defaultBranchRef {{
      target {{
        ... on Commit {{
          history(first: 100) {{
            edges {{
              node {{
                authoredDate
                author {{
                  user {{
                    login
                    company
                  }}
                  email
                }}
              }}
            }}
            totalCount
          }}
          checkSuites(last: 1) {{
            nodes {{
              conclusion
              status
            }}
          }}
        }}
      }}
    }}
    pullRequests(first: 50, states: MERGED, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
      edges {{
        node {{
          mergedAt
          createdAt
          mergedBy {{
            login
          }}
          reviews(first: 10) {{
            totalCount
            edges {{
              node {{
                createdAt
              }}
            }}
          }}
        }}
      }}
    }}
    closedPullRequests: pullRequests(first: 50, states: CLOSED, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
      totalCount
      edges {{
        node {{
          closedAt
          createdAt
          merged
          reviews(first: 1) {{
            edges {{
              node {{
                createdAt
              }}
            }}
          }}
        }}
      }}
    }}
    mergedPullRequestsCount: pullRequests(states: MERGED) {{
      totalCount
    }}
    releases(first: 10, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
      edges {{
        node {{
          publishedAt
          tagName
        }}
      }}
    }}
    issues(first: 20, states: OPEN, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
      edges {{
        node {{
          createdAt
          comments(first: 1) {{
            edges {{
              node {{
                createdAt
              }}
            }}
          }}
        }}
      }}
    }}
    closedIssues: issues(first: 50, states: CLOSED, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
      totalCount
      edges {{
        node {{
          createdAt
          closedAt
          updatedAt
          timelineItems(first: 1, itemTypes: CLOSED_EVENT) {{
            edges {{
              node {{
                ... on ClosedEvent {{
                  actor {{
                    login
                  }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    vulnerabilityAlerts(first: 10) {{
      edges {{
        node {{
          securityVulnerability {{
            severity
          }}
          dismissedAt
        }}
      }}
    }}
    isSecurityPolicyEnabled
    fundingLinks {{
      platform
      url
    }}
    hasWikiEnabled
    hasIssuesEnabled
    hasDiscussionsEnabled
    codeOfConduct {{
      name
      url
    }}
    licenseInfo {{
      name
      spdxId
      url
    }}
    stargazerCount
    forkCount
    watchers {{
      totalCount
    }}
    forks(first: 20, orderBy: {{field: PUSHED_AT, direction: DESC}}) {{
      edges {{
        node {{
          createdAt
          pushedAt
          defaultBranchRef {{
            target {{
              ... on Commit {{
                history(first: 1) {{
                  edges {{
                    node {{
                      committedDate
                    }}
                  }}
                }}
              }}
            }}
          }}
          owner {{
            login
          }}
        }}
      }}
    }}
    readmeUpperCase: object(expression: "HEAD:README.md") {{
      ... on Blob {{
        byteSize
      }}
    }}
    readmeLowerCase: object(expression: "HEAD:readme.md") {{
      ... on Blob {{
        byteSize
      }}
    }}
    readmeAllCaps: object(expression: "HEAD:README") {{
      ... on Blob {{
        byteSize
      }}
    }}
    contributingFile: object(expression: "HEAD:CONTRIBUTING.md") {{
      ... on Blob {{
        byteSize
      }}
    }}
    description
    homepageUrl
  }}""")

    query_parts.append("}")
    return "\n".join(query_parts)


def analyze_repositories_batch(
    repo_list: list[tuple[str, str]],
    platform: str | None = None,
) -> dict[tuple[str, str], AnalysisResult | None]:
    """Analyze multiple repositories in a single GraphQL query.

    Args:
        repo_list: List of (owner, name) tuples.
        platform: Optional package platform for dependents analysis.

    Returns:
        Dictionary mapping (owner, name) to AnalysisResult or None.
    """
    if not repo_list:
        return {}

    # GitHub GraphQL has limits on query complexity
    # Use smaller batch size (3) to avoid timeouts with large queries
    batch_size = 3
    results: dict[tuple[str, str], AnalysisResult | None] = {}

    for i in range(0, len(repo_list), batch_size):
        batch = repo_list[i : i + batch_size]

        try:
            query = _get_batch_repository_query(batch)
            response = _query_github_graphql(query, {})

            # Process each repository in the batch
            for idx, (owner, name) in enumerate(batch):
                alias = f"repo{idx}"
                repo_info = response.get(alias)

                if repo_info is None:
                    console.print(
                        f"  [yellow]⚠️  No data returned for {owner}/{name}[/yellow]"
                    )
                    results[(owner, name)] = None
                    continue

                # Analyze the repository using the retrieved data
                try:
                    result = _analyze_repository_data(
                        owner, name, repo_info, platform=platform
                    )
                    results[(owner, name)] = result
                except Exception as e:
                    # Show error for debugging
                    console.print(
                        f"  [yellow]⚠️  Analysis error for {owner}/{name}: {e}[/yellow]"
                    )
                    results[(owner, name)] = None

        except Exception as e:
            # Batch query failed - fall back to individual queries
            console.print(
                f"  [yellow]⚠️  Batch query failed ({e}), trying individual queries...[/yellow]"
            )
            for owner, name in batch:
                try:
                    # Fall back to single repository analysis
                    result = analyze_repository(owner, name, platform=platform)
                    results[(owner, name)] = result
                except Exception:
                    # If individual query also fails, mark as None
                    results[(owner, name)] = None

    return results


def _analyze_repository_data(
    owner: str,
    name: str,
    repo_info: dict[str, Any],
    platform: str | None = None,
    package_name: str | None = None,
) -> AnalysisResult:
    """Analyze repository data (extracted from GraphQL response).

    This is the core analysis logic separated from the GraphQL query.
    """
    metrics = []
    try:
        metrics.append(check_bus_factor(repo_info))
    except Exception as e:
        console.print(
            f"  [yellow]⚠️  Contributor redundancy check incomplete: {e}[/yellow]"
        )
        metrics.append(
            Metric(
                "Contributor Redundancy",
                0,
                20,
                f"Note: Analysis incomplete - {e}",
                "High",
            )
        )

    try:
        metrics.append(check_maintainer_drain(repo_info))
    except Exception as e:
        console.print(
            f"  [yellow]⚠️  Maintainer retention check incomplete: {e}[/yellow]"
        )
        metrics.append(
            Metric(
                "Maintainer Retention",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "High",
            )
        )

    try:
        metrics.append(check_zombie_status(repo_info))
    except Exception as e:
        # Silently capture error in metric message
        metrics.append(
            Metric("Recent Activity", 0, 20, f"Note: Analysis incomplete - {e}", "High")
        )

    try:
        metrics.append(check_merge_velocity(repo_info))
    except Exception as e:
        # Silently capture error in metric message
        metrics.append(
            Metric(
                "Change Request Resolution",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    try:
        metrics.append(check_issue_resolution_duration(repo_info))
    except Exception as e:
        # Silently capture error in metric message
        metrics.append(
            Metric(
                "Issue Resolution Time",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "Low",
            )
        )

    try:
        metrics.append(check_funding(repo_info))
    except Exception as e:
        # Silently capture error in metric message
        metrics.append(
            Metric(
                "Funding Status",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "Low",
            )
        )

    try:
        metrics.append(check_release_cadence(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "Release Rhythm",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    try:
        metrics.append(check_security_posture(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "Security Signals",
                0,
                15,
                f"Note: Analysis incomplete - {e}",
                "High",
            )
        )

    try:
        metrics.append(check_attraction(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "Contributor Attraction",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    try:
        metrics.append(check_retention(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "Contributor Retention",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    try:
        metrics.append(check_review_health(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "Review Health",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    try:
        metrics.append(check_documentation_presence(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "Documentation Presence",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "Low",
            )
        )

    try:
        metrics.append(check_code_of_conduct(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "Code of Conduct",
                0,
                5,
                f"Note: Analysis incomplete - {e}",
                "Low",
            )
        )

    try:
        metrics.append(check_pr_acceptance_ratio(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "PR Acceptance Ratio",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    try:
        metrics.append(check_organizational_diversity(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "Organizational Diversity",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    try:
        metrics.append(check_fork_activity(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "Fork Activity",
                0,
                5,
                f"Note: Analysis incomplete - {e}",
                "Low",
            )
        )

    try:
        metrics.append(check_project_popularity(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "Project Popularity",
                0,
                10,
                f"Note: Analysis incomplete - {e}",
                "Low",
            )
        )

    try:
        metrics.append(check_license_clarity(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "License Clarity",
                0,
                5,
                f"Note: Analysis incomplete - {e}",
                "Low",
            )
        )

    try:
        metrics.append(check_pr_responsiveness(repo_info))
    except Exception as e:
        metrics.append(
            Metric(
                "PR Responsiveness",
                0,
                5,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    try:
        metrics.append(check_community_health(repo_info))
    except Exception as e:
        # Silently capture error in metric message
        metrics.append(
            Metric(
                "Community Health",
                0,
                5,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    try:
        metrics.append(check_ci_status(repo_info))
    except Exception as e:
        # Silently capture error in metric message
        metrics.append(
            Metric(
                "CI/CD Status",
                0,
                5,
                f"Note: Analysis incomplete - {e}",
                "Low",
            )
        )

    try:
        metrics.append(check_stale_issue_ratio(repo_info))
    except Exception as e:
        # Silently capture error in metric message
        metrics.append(
            Metric(
                "Stale Issue Ratio",
                0,
                5,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    try:
        metrics.append(check_pr_merge_speed(repo_info))
    except Exception as e:
        # Silently capture error in metric message
        metrics.append(
            Metric(
                "PR Merge Speed",
                0,
                5,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    try:
        metrics.append(check_single_maintainer_load(repo_info))
    except Exception as e:
        # Silently capture error in metric message
        metrics.append(
            Metric(
                "Maintainer Load Distribution",
                0,
                5,
                f"Note: Analysis incomplete - {e}",
                "Medium",
            )
        )

    # Dependents analysis (if platform and package_name provided)
    if platform and package_name:
        try:
            repo_url = f"https://github.com/{owner}/{name}"
            metrics.append(check_dependents_count(repo_url, platform, package_name))
        except Exception as e:
            # Silently capture error in metric message
            metrics.append(
                Metric(
                    "Downstream Dependents",
                    0,
                    10,
                    f"Note: Analysis incomplete - {e}",
                    "Low",
                )
            )

    # Calculate total score using category-weighted scoring system
    total_score = compute_weighted_total_score(metrics, profile="balanced")

    # Extract funding information directly from repo data
    funding_links = repo_info.get("fundingLinks", [])

    # Determine if project is community-driven
    # Projects with funding links are considered community-driven (seeking support)
    # Projects owned by Users (not Organizations) are also community-driven
    has_funding = len(funding_links) > 0
    is_user_owned = repo_info.get("owner", {}).get("__typename", "") == "User"
    is_community = has_funding or is_user_owned

    # Generate CHAOSS metric models
    models: list[MetricModel] = compute_metric_models(metrics)

    # Extract raw signals for transparency (placeholder for now)
    signals: dict[str, Any] = {}

    repo_url = f"https://github.com/{owner}/{name}"

    # Note: Progress display is handled by CLI layer, not here
    # Individual completion messages would interfere with progress bar

    return AnalysisResult(
        repo_url=repo_url,
        total_score=total_score,
        metrics=metrics,
        funding_links=funding_links if is_community else [],
        is_community_driven=is_community,
        models=models,
        signals=signals,
    )


# --- Main Analysis Function ---


def analyze_repository(
    owner: str,
    name: str,
    platform: str | None = None,
    package_name: str | None = None,
) -> AnalysisResult:
    """
    Performs a full sustainability analysis on a given repository.

    Queries the GitHub GraphQL API to retrieve repository metrics,
    then calculates sustainability scores across multiple dimensions.

    Args:
        owner: GitHub repository owner (username or organization)
        name: GitHub repository name
        platform: Optional package platform (e.g., 'Pypi', 'NPM', 'Cargo')
                  for dependents analysis via Libraries.io
        package_name: Optional package name on the registry for dependents analysis

    Returns:
        AnalysisResult containing repo_url, total_score, and list of metrics

    Raises:
        ValueError: If GITHUB_TOKEN is not set
        httpx.HTTPStatusError: If GitHub API returns an error
    """

    console.print(f"Analyzing [bold cyan]{owner}/{name}[/bold cyan]...")

    try:
        # Execute the GraphQL query
        query = _get_repository_query()
        variables = {"owner": owner, "name": name}
        repo_data = _query_github_graphql(query, variables)

        # Extract repository data from response
        if "repository" not in repo_data:
            raise ValueError(f"Repository {owner}/{name} not found or is inaccessible.")

        repo_info = repo_data["repository"]

        # Use the shared analysis logic
        return _analyze_repository_data(owner, name, repo_info, platform, package_name)

    except httpx.HTTPStatusError as e:
        console.print(f"[red]HTTP Error: {e}[/red]")
        raise
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise
    except Exception as e:
        console.print(f"[red]Unexpected error during analysis: {e}[/red]")
        raise


def analyze_dependencies(
    dependency_graph,
    database: dict[str, Any],
) -> dict[str, int]:
    """
    Analyze dependency packages and retrieve their scores.

    Args:
        dependency_graph: DependencyGraph object from dependency_graph module.
        database: Cached package database keyed by "ecosystem:package_name".

    Returns:
        Dictionary mapping package names to their scores.
    """
    scores: dict[str, int] = {}
    ecosystem = dependency_graph.ecosystem

    # Analyze direct dependencies
    for dep in dependency_graph.direct_dependencies:
        db_key = f"{ecosystem}:{dep.name}"
        if db_key in database:
            try:
                pkg_data = database[db_key]
                score = pkg_data.get("total_score", 0)
                scores[dep.name] = score
            except (KeyError, TypeError):
                # Skip if data format is unexpected
                pass

    return scores


if __name__ == "__main__":
    # Example usage:
    # Ensure you have a GITHUB_TOKEN in your environment.
    # $ export GITHUB_TOKEN="your_github_pat"
    # $ python src/oss_guard/core.py
    try:
        result = analyze_repository("psf", "requests")
        console = Console()
        console.print(result)
    except (ValueError, httpx.HTTPStatusError) as e:
        console = Console()
        console.print(f"[bold red]Error:[/bold red] {e}")
