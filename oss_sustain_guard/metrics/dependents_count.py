"""Downstream dependents metric."""

import os

from oss_sustain_guard.librariesio import query_librariesio_api
from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData


def check_dependents_count(
    repo_url: str, platform: str | None = None, package_name: str | None = None
) -> Metric | None:
    """
    Evaluates package adoption by counting downstream dependents.

    Uses Libraries.io API to determine how many other packages
    depend on this package. High dependents count indicates:
    - Wide adoption and trust
    - Core infrastructure importance
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

    Scoring (out of 10):
        - 10000+ dependents: 10/10 (Core infrastructure)
        - 1000+ dependents: 9/10 (Widely adopted)
        - 500+ dependents: 8/10 (Popular)
        - 100+ dependents: 6/10 (Established)
        - 50+ dependents: 5/10 (Growing adoption)
        - 10+ dependents: 3/10 (Early adoption)
        - 1+ dependents: 2/10 (Used by others)
        - 0 dependents: 0/10 (No downstream dependencies)

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
    package_info = query_librariesio_api(platform, package_name)

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
        message = f"Core infrastructure: 📦 {dependents_count:,} packages depend on this ({dependent_repos_count:,} repos). Essential to ecosystem."
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


class DependentsCountChecker(MetricChecker):
    """Evaluate downstream dependents using registry context."""

    def check(
        self, _vcs_data: VCSRepositoryData, context: MetricContext
    ) -> Metric | None:
        return check_dependents_count(
            context.repo_url,
            platform=context.platform,
            package_name=context.package_name,
        )


_CHECKER = DependentsCountChecker()


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Downstream Dependents",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="Downstream Dependents",
    checker=_CHECKER,
    on_error=_on_error,
)
