"""Maintainer load distribution metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class SingleMaintainerLoadChecker(MetricChecker):
    """Evaluate maintainer load distribution using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates maintainer workload distribution using Gini coefficient.

        Measures concentration of Issue/PR closing activity among contributors.
        High concentration (high Gini) indicates likelihood of single maintainer burnout.

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

        closer_counts: dict[str, int] = {}

        for pr in vcs_data.merged_prs:
            merged_by = pr.get("mergedBy")
            if isinstance(merged_by, dict):
                login = merged_by.get("login")
                if login:
                    closer_counts[login] = closer_counts.get(login, 0) + 1

        for issue in vcs_data.closed_issues:
            closed_by = issue.get("closedBy") or issue.get("closed_by")
            if isinstance(closed_by, dict):
                login = closed_by.get("login") or closed_by.get("username")
                if login:
                    closer_counts[login] = closer_counts.get(login, 0) + 1

        raw_data = vcs_data.raw_data or {}
        closed_issues = raw_data.get("closedIssues", {}).get("edges", [])
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


_CHECKER = SingleMaintainerLoadChecker()


def check_single_maintainer_load(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Maintainer Load Distribution",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="Maintainer Load Distribution",
    checker=_CHECKER,
    on_error=_on_error,
)
