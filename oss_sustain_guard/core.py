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


class AnalysisResult(NamedTuple):
    """The result of a repository analysis."""

    repo_url: str
    total_score: int
    metrics: list[Metric]
    funding_links: list[dict[str, str]] = []  # List of {"platform": str, "url": str}
    is_community_driven: bool = False  # True if project is community-driven


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
            "Bus Factor",
            0,
            max_score,
            "Note: Commit history data not available.",
            "High",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Bus Factor",
            0,
            max_score,
            "Note: Commit history data not available.",
            "High",
        )

    history = target.get("history", {}).get("edges", [])
    if not history:
        return Metric(
            "Bus Factor",
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
            "Bus Factor",
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

    return Metric("Bus Factor", score, max_score, message, risk)


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
            "Maintainer Drain",
            max_score,
            max_score,
            "Note: Maintainer data not available for verification.",
            "None",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Maintainer Drain",
            max_score,
            max_score,
            "Note: Maintainer data not available for verification.",
            "None",
        )

    history = target.get("history", {}).get("edges", [])
    if len(history) < 50:
        # If history is too short, cannot detect drain
        return Metric(
            "Maintainer Drain",
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
            "Maintainer Drain",
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

    return Metric("Maintainer Drain", score, max_score, message, risk)


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
            "Zombie Check",
            10,  # Not 0 - archived is intentional, but needs monitoring
            max_score,
            "Repository is archived (intentional).",
            "Medium",
        )

    pushed_at_str = repo_data.get("pushedAt")
    if not pushed_at_str:
        return Metric(
            "Zombie Check",
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
            "Zombie Check",
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
            "Zombie Check",
            0,
            max_score,
            f"No activity for {days_since_last_push} days (2+ years). Project may be inactive.",
            "Critical",
        )
    elif days_since_last_push > 365:  # 1+ year
        return Metric(
            "Zombie Check",
            5,
            max_score,
            f"Last activity {days_since_last_push} days ago (1+ year). "
            f"May be in stable/maintenance mode.",
            "High",
        )
    elif days_since_last_push > 180:  # 6+ months
        return Metric(
            "Zombie Check",
            10,
            max_score,
            f"Last activity {days_since_last_push} days ago (6+ months).",
            "Medium",
        )
    elif days_since_last_push > 90:  # 3+ months
        return Metric(
            "Zombie Check",
            15,
            max_score,
            f"Last activity {days_since_last_push} days ago (3+ months).",
            "Low",
        )
    else:
        return Metric(
            "Zombie Check",
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
            "Merge Velocity",
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
            "Merge Velocity",
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

    return Metric("Merge Velocity", score, max_score, message, risk)


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
            "CI Status",
            max_score,
            max_score,
            "Repository archived (CI check skipped).",
            "None",
        )

    # Extract CI status from checkSuites
    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
        return Metric(
            "CI Status",
            0,
            max_score,
            "Note: CI status data not available.",
            "High",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "CI Status",
            0,
            max_score,
            "Note: CI status data not available.",
            "High",
        )

    check_suites = target.get("checkSuites", {}).get("nodes", [])

    if not check_suites:
        return Metric(
            "CI Status",
            0,
            max_score,
            "No CI configuration detected.",
            "High",
        )

    # Get the most recent check suite
    latest_suite = check_suites[0] if check_suites else None
    if not latest_suite or not isinstance(latest_suite, dict):
        return Metric(
            "CI Status",
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

    return Metric("CI Status", score, max_score, message, risk)


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

    return Metric("Funding", score, max_score, message, risk)


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
                "Release Cadence",
                max_score,
                max_score,
                "Archived repository (no releases expected).",
                "None",
            )
        return Metric(
            "Release Cadence",
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
            "Release Cadence",
            0,
            max_score,
            "Note: Release date information not available.",
            "High",
        )

    try:
        published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return Metric(
            "Release Cadence",
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

    return Metric("Release Cadence", score, max_score, message, risk)


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

    return Metric("Security Posture", score, max_score, message, risk)


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

    return Metric("Community Health", score, max_score, message, risk)


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
            console.print(f"  [yellow]⚠️  Bus factor check incomplete: {e}[/yellow]")
            metrics.append(
                Metric("Bus Factor", 0, 20, f"Note: Analysis incomplete - {e}", "High")
            )

        try:
            metrics.append(check_maintainer_drain(repo_info))
        except Exception as e:
            console.print(
                f"  [yellow]⚠️  Maintainer drain check incomplete: {e}[/yellow]"
            )
            metrics.append(
                Metric(
                    "Maintainer Drain",
                    0,
                    10,
                    f"Note: Analysis incomplete - {e}",
                    "High",
                )
            )

        try:
            metrics.append(check_zombie_status(repo_info))
        except Exception as e:
            console.print(f"  [yellow]⚠️  Zombie status check incomplete: {e}[/yellow]")
            metrics.append(
                Metric(
                    "Zombie Status", 0, 20, f"Note: Analysis incomplete - {e}", "High"
                )
            )

        try:
            metrics.append(check_merge_velocity(repo_info))
        except Exception as e:
            console.print(f"  [yellow]⚠️  Merge velocity check incomplete: {e}[/yellow]")
            metrics.append(
                Metric(
                    "Merge Velocity", 0, 10, f"Note: Analysis incomplete - {e}", "High"
                )
            )

        try:
            metrics.append(check_ci_status(repo_info))
        except Exception as e:
            console.print(f"  [yellow]⚠️  CI status check incomplete: {e}[/yellow]")
            metrics.append(
                Metric("CI Status", 0, 5, f"Note: Analysis incomplete - {e}", "High")
            )

        try:
            metrics.append(check_funding(repo_info))
        except Exception as e:
            console.print(f"  [yellow]⚠️  Funding check incomplete: {e}[/yellow]")
            metrics.append(
                Metric("Funding", 0, 10, f"Note: Analysis incomplete - {e}", "High")
            )

        try:
            metrics.append(check_release_cadence(repo_info))
        except Exception as e:
            console.print(
                f"  [yellow]⚠️  Release cadence check incomplete: {e}[/yellow]"
            )
            metrics.append(
                Metric(
                    "Release Cadence", 0, 10, f"Note: Analysis incomplete - {e}", "High"
                )
            )

        try:
            metrics.append(check_security_posture(repo_info))
        except Exception as e:
            console.print(
                f"  [yellow]⚠️  Security posture check incomplete: {e}[/yellow]"
            )
            metrics.append(
                Metric(
                    "Security Posture",
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
                f"  [yellow]⚠️  Community health check incomplete: {e}[/yellow]"
            )
            metrics.append(
                Metric(
                    "Community Health", 0, 5, f"Note: Analysis incomplete - {e}", "High"
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

        return AnalysisResult(
            repo_url=f"https://github.com/{owner}/{name}",
            total_score=total_score,
            metrics=metrics,
            funding_links=funding_links,
            is_community_driven=is_community_driven,
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
