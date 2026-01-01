"""Funding signals metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


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


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_funding(repo_data)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Funding Status",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="Funding Signals",
    checker=_check,
    on_error=_on_error,
)
