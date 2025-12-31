"""PR responsiveness metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


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


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_pr_responsiveness(repo_data)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "PR Responsiveness",
        0,
        5,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="PR Responsiveness",
    checker=_check,
    on_error=_on_error,
)
