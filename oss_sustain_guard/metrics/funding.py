"""Funding signals metric."""

from typing import Any

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


def is_corporate_backed(repo_data: dict[str, Any] | VCSRepositoryData) -> bool:
    """
    Detects if a repository is corporate-backed (organization-owned).

    Args:
        repo_data: Repository data from VCS or GitHub GraphQL API

    Returns:
        True if owned by an Organization, False if owned by a User
    """
    if isinstance(repo_data, VCSRepositoryData):
        return repo_data.owner_type in ("Organization", "Group")
    owner = repo_data.get("owner", {})
    owner_type = owner.get("__typename", "")
    return owner_type == "Organization"


class FundingChecker(MetricChecker):
    """Evaluate funding signals using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
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
        owner_login = vcs_data.owner_login or "unknown"
        is_org_backed = is_corporate_backed(vcs_data)
        funding_links = vcs_data.funding_links
        has_funding_links = len(funding_links) > 0

        if is_org_backed:
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
            max_score = 10
            if has_funding_links:
                score = 8
                risk = "None"
                message = f"Community-funded: {len(funding_links)} funding link(s)."
            else:
                score = 0
                risk = "Low"
                message = (
                    "No funding sources detected for community projects. "
                    "Consider adding support links."
                )

        return Metric("Funding Signals", score, max_score, message, risk)


_CHECKER = FundingChecker()


def check_funding(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


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
    checker=_CHECKER,
    on_error=_on_error,
)
