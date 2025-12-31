"""Maintainer load distribution metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


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


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_single_maintainer_load(repo_data)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Maintainer Load Distribution",
        0,
        5,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="Maintainer Load Distribution",
    checker=_check,
    on_error=_on_error,
)
