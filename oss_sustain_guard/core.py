"""
Core analysis logic for OSS Sustain Guard.
"""

import os
from typing import Any, NamedTuple

import httpx
from dotenv import load_dotenv
from rich.console import Console

from oss_sustain_guard.config import get_verify_ssl

# Load environment variables from .env file
load_dotenv()

# --- Constants ---

GITHUB_GRAPHQL_API = "https://api.github.com/graphql"
# Using a personal access token from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

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


# --- Helper Functions ---


def _query_github_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    """
    Executes a GraphQL query against the GitHub API.

    Raises:
        ValueError: If the GITHUB_TOKEN is not set.
        httpx.HTTPStatusError: If the API returns an error.
    """
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable is not set.")

    headers = {
        "Authorization": f"bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    with httpx.Client(verify=get_verify_ssl()) as client:
        response = client.post(
            GITHUB_GRAPHQL_API,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=10,
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


# --- GraphQL Query Templates ---


def _get_repository_query() -> str:
    """Returns the GraphQL query to fetch repository metrics."""
    return """
    query GetRepository($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        isArchived
        pushedAt
        owner {
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
                      }
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
    """
    max_score = 20

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

    # Count commits per author
    author_counts: dict[str, int] = {}
    for edge in history:
        node = edge.get("node", {})
        author = node.get("author", {})
        user = author.get("user")
        if user:
            login = user.get("login")
            if login:
                author_counts[login] = author_counts.get(login, 0) + 1

    total_commits = len(history)
    if total_commits == 0:
        return Metric(
            "Contributor Redundancy",
            0,
            max_score,
            "No commits found.",
            "Critical",
        )

    # Find the top contributor
    top_contributor_commits = max(author_counts.values()) if author_counts else 0
    percentage = (top_contributor_commits / total_commits) * 100
    num_contributors = len(author_counts)

    # Extract total commit count for BDFL model detection
    total_repo_commits = target.get("history", {}).get("totalCount", len(history))

    # Determine project maturity based on total commit count
    # BDFL (Benevolent Dictator For Life) model detection:
    # - Mature project (1000+ commits) with single-author > 90% = legitimate BDFL
    is_mature_bdfl = total_repo_commits >= 1000 and percentage >= 90
    is_mature_project = total_repo_commits >= 100

    # Scoring logic with BDFL model recognition
    if percentage >= 90:
        # Very high single-author concentration
        if is_mature_bdfl:
            # Mature BDFL model = proven track record
            score = 15
            risk = "Low"
            message = (
                f"BDFL model: {percentage:.0f}% by founder/leader. "
                f"Mature project ({total_repo_commits} commits). Proven stability."
            )
        elif is_mature_project:
            # Mature project but recently single-heavy = concern
            score = 5
            risk = "High"
            message = (
                f"High: {percentage:.0f}% of recent commits by single author. "
                f"{num_contributors} contributor(s), {total_repo_commits} total commits."
            )
        else:
            # New project with founder-heavy commit = acceptable
            score = 10
            risk = "Medium"
            message = (
                f"New project: {percentage:.0f}% by single author. "
                f"Expected for early-stage projects."
            )
    elif percentage >= 70:
        score = 10
        risk = "High"
        message = (
            f"High: {percentage:.0f}% of commits by single author. "
            f"{num_contributors} contributor(s) total."
        )
    elif percentage >= 50:
        score = 15
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
    """
    from datetime import datetime

    max_score = 20

    is_archived = repo_data.get("isArchived", False)
    if is_archived:
        # Archived repos are intentional, not risky if properly maintained during lifecycle
        return Metric(
            "Recent Activity",
            10,  # Not 0 - archived is intentional, but needs monitoring
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

    # Scoring logic with maturity consideration
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
            5,
            max_score,
            f"Last activity {days_since_last_push} days ago (1+ year). "
            f"May be in stable/maintenance mode.",
            "High",
        )
    elif days_since_last_push > 180:  # 6+ months
        return Metric(
            "Recent Activity",
            10,
            max_score,
            f"Last activity {days_since_last_push} days ago (6+ months).",
            "Medium",
        )
    elif days_since_last_push > 90:  # 3+ months
        return Metric(
            "Recent Activity",
            15,
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

    Scoring:
    - SUCCESS or NEUTRAL: 5/5 (CI passing)
    - FAILURE: 0/5 (CI issues detected)
    - IN_PROGRESS/QUEUED: 3/5 (Not yet completed)
    - No CI data: 0/5 (No CI configuration detected)
    """
    max_score = 5

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

    # Scoring logic based on CI conclusion (reference only)
    if conclusion in ("SUCCESS", "NEUTRAL"):
        score = max_score
        risk = "None"
        message = f"CI Status: {conclusion.lower()} (Latest check passed)."
    elif conclusion in ("FAILURE", "TIMED_OUT"):
        score = 0
        risk = "Medium"  # Downgraded from Critical
        message = f"CI Status: {conclusion.lower()} (Latest check failed)."
    elif status == "IN_PROGRESS":
        score = 3
        risk = "Low"
        message = "CI Status: Tests in progress (not yet complete)."
    elif status == "QUEUED":
        score = 3
        risk = "Low"
        message = "CI Status: Tests queued."
    else:
        # Unknown status
        score = 0
        risk = "Low"
        message = f"CI Status: Unknown ({conclusion or status})."

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
    - Funding less critical (corporate backing assumed)
    - Scoring: capped at 5/10 (not a primary concern)

    Considers:
    - Explicit funding links (GitHub Sponsors, etc.)
    - Organization ownership (indicates corporate backing)

    Scoring (Community-driven):
    - Funding links + Organization: 10/10 (Well-supported)
    - Funding links only: 8/10 (Community support)
    - No funding: 0/10 (Unsupported)

    Scoring (Corporate-backed):
    - Organization backing: 5/10 (Corporate backing sufficient)
    - No funding info: 0/10 (Not applicable for corporate)
    """
    owner = repo_data.get("owner", {})
    owner_login = owner.get("login", "unknown")
    is_org_backed = is_corporate_backed(repo_data)
    funding_links = repo_data.get("fundingLinks", [])
    has_funding_links = len(funding_links) > 0

    if is_org_backed:
        # Corporate-backed: Funding is not critical
        # Capped at 5/10 since corporate backing is primary indicator
        max_score = 5
        if has_funding_links:
            score = 5
            risk = "None"
            message = (
                f"Corporate backing sufficient: {owner_login} + "
                f"{len(funding_links)} funding link(s)."
            )
        else:
            score = 5
            risk = "None"
            message = f"Corporate backing: Organization maintained ({owner_login})."
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

    Scoring:
    - Critical alerts unresolved: 0/15 (Critical)
    - High alerts unresolved: 5/15 (High risk)
    - Security policy + no alerts: 15/15 (Excellent)
    - Security policy only: 12/15 (Good)
    - No security infrastructure: 8/15 (Moderate)
    """
    max_score = 15

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

    # Scoring logic
    if critical_count > 0:
        score = 0
        risk = "Critical"
        message = (
            f"Attention needed: {critical_count} unresolved CRITICAL vulnerability alert(s). "
            f"Review and action recommended."
        )
    elif high_count >= 3:
        score = 5
        risk = "High"
        message = (
            f"High: {high_count} unresolved HIGH vulnerability alert(s). "
            f"Review and patch recommended."
        )
    elif high_count > 0:
        score = 8
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
        score = 12
        risk = "None"
        message = "Good: No unresolved vulnerabilities detected."
    else:
        # No security policy, no alerts (may not be using Dependabot)
        score = 8
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

    Scoring:
    - Average response <24h: 5/5 (Excellent)
    - Average response <7d: 3/5 (Good)
    - Average response >30d: 0/5 (Poor)
    - No open issues: 5/5 (Low activity or well-maintained)
    """
    from datetime import datetime

    max_score = 5

    issues = repo_data.get("issues", {}).get("edges", [])

    if not issues:
        return Metric(
            "Issue Responsiveness",
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
            "Issue Responsiveness",
            2,
            max_score,
            "Unable to assess: No responded issues in recent history.",
            "Medium",
        )

    avg_response_time = sum(response_times) / len(response_times)

    # Scoring logic
    if avg_response_time < 24:  # <1 day
        score = max_score
        risk = "None"
        message = (
            f"Excellent: Average issue response time {avg_response_time:.1f} hours."
        )
    elif avg_response_time < 168:  # <7 days
        score = 3
        risk = "None"
        message = (
            f"Good: Average issue response time {avg_response_time:.1f} hours "
            f"({avg_response_time / 24:.1f} days)."
        )
    elif avg_response_time < 720:  # <30 days
        score = 1
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

    return Metric("Issue Responsiveness", score, max_score, message, risk)


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
        if not login:
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
        if not login:
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
    - Avg first review <24h & 2+ reviews: 10/10 (Excellent)
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
    if avg_review_time < 24 and avg_review_count >= 2:
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
            author_counts = {}
            for edge in history:
                node = edge.get("node", {})
                author = node.get("author", {})
                user = author.get("user")
                if user:
                    login = user.get("login")
                    if login:
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


# --- Main Analysis Function ---


def analyze_repository(owner: str, name: str) -> AnalysisResult:
    """
    Performs a full sustainability analysis on a given repository.

    Queries the GitHub GraphQL API to retrieve repository metrics,
    then calculates sustainability scores across multiple dimensions.

    Args:
        owner: GitHub repository owner (username or organization)
        name: GitHub repository name

    Returns:
        AnalysisResult containing repo_url, total_score, and list of metrics

    Raises:
        ValueError: If GITHUB_TOKEN is not set
        httpx.HTTPStatusError: If GitHub API returns an error
    """
    console = Console()
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

        # Calculate metrics with error handling for each metric
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
            console.print(
                f"  [yellow]⚠️  Recent activity check incomplete: {e}[/yellow]"
            )
            metrics.append(
                Metric(
                    "Recent Activity", 0, 20, f"Note: Analysis incomplete - {e}", "High"
                )
            )

        try:
            metrics.append(check_merge_velocity(repo_info))
        except Exception as e:
            console.print(
                f"  [yellow]⚠️  Change request resolution check incomplete: {e}[/yellow]"
            )
            metrics.append(
                Metric(
                    "Change Request Resolution",
                    0,
                    10,
                    f"Note: Analysis incomplete - {e}",
                    "High",
                )
            )

        try:
            metrics.append(check_ci_status(repo_info))
        except Exception as e:
            console.print(f"  [yellow]⚠️  Build health check incomplete: {e}[/yellow]")
            metrics.append(
                Metric("Build Health", 0, 5, f"Note: Analysis incomplete - {e}", "High")
            )

        try:
            metrics.append(check_funding(repo_info))
        except Exception as e:
            console.print(
                f"  [yellow]⚠️  Funding signals check incomplete: {e}[/yellow]"
            )
            metrics.append(
                Metric(
                    "Funding Signals", 0, 10, f"Note: Analysis incomplete - {e}", "High"
                )
            )

        try:
            metrics.append(check_release_cadence(repo_info))
        except Exception as e:
            console.print(f"  [yellow]⚠️  Release rhythm check incomplete: {e}[/yellow]")
            metrics.append(
                Metric(
                    "Release Rhythm", 0, 10, f"Note: Analysis incomplete - {e}", "High"
                )
            )

        try:
            metrics.append(check_security_posture(repo_info))
        except Exception as e:
            console.print(
                f"  [yellow]⚠️  Security signals check incomplete: {e}[/yellow]"
            )
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
            metrics.append(check_community_health(repo_info))
        except Exception as e:
            console.print(
                f"  [yellow]⚠️  Issue responsiveness check incomplete: {e}[/yellow]"
            )
            metrics.append(
                Metric(
                    "Issue Responsiveness",
                    0,
                    5,
                    f"Note: Analysis incomplete - {e}",
                    "High",
                )
            )

        # New CHAOSS metrics (Phase 4)
        try:
            metrics.append(check_attraction(repo_info))
        except Exception as e:
            console.print(
                f"  [yellow]⚠️  Contributor attraction check incomplete: {e}[/yellow]"
            )
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
            console.print(
                f"  [yellow]⚠️  Contributor retention check incomplete: {e}[/yellow]"
            )
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
            console.print(f"  [yellow]⚠️  Review health check incomplete: {e}[/yellow]")
            metrics.append(
                Metric(
                    "Review Health",
                    0,
                    10,
                    f"Note: Analysis incomplete - {e}",
                    "Medium",
                )
            )

        # Calculate raw total score
        raw_total = sum(m.score for m in metrics)
        max_possible = sum(m.max_score for m in metrics)

        # Normalize to 100-point scale
        # max_possible varies based on project type:
        # Community-driven: 20 + 10 + 20 + 10 + 5 + 10 + 10 + 15 + 5 = 105
        # Corporate-backed: 20 + 10 + 20 + 10 + 5 + 5 + 10 + 15 + 5 = 100
        total_score = int((raw_total / max_possible) * 100) if max_possible > 0 else 0

        console.print(
            f"Analysis complete for [bold cyan]{owner}/{name}[/bold cyan]. Score: {total_score}/100"
        )

        # Extract funding links and community status
        funding_links = repo_info.get("fundingLinks", [])
        is_community_driven = not is_corporate_backed(repo_info)

        # Compute metric models (CHAOSS-aligned aggregations)
        models = compute_metric_models(metrics)

        # Extract raw signals for transparency
        signals = extract_signals(metrics, repo_info)

        return AnalysisResult(
            repo_url=f"https://github.com/{owner}/{name}",
            total_score=total_score,
            metrics=metrics,
            funding_links=funding_links,
            is_community_driven=is_community_driven,
            models=models,
            signals=signals,
        )

    except Exception as e:
        console.print(f"  [bold red]❌ Unable to complete analysis: {e}[/bold red]")
        raise


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
