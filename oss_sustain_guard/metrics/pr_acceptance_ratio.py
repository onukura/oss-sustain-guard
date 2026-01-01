"""PR acceptance ratio metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


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


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_pr_acceptance_ratio(repo_data)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "PR Acceptance Ratio",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="PR Acceptance Ratio",
    checker=_check,
    on_error=_on_error,
)
