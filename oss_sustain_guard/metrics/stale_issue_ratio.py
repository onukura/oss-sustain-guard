"""Stale issue ratio metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class StaleIssueRatioChecker(MetricChecker):
    """Evaluate stale issue ratio using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
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

        closed_issues = vcs_data.closed_issues

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

        for node in closed_issues:
            updated_at_str = node.get("updatedAt") or node.get("closedAt")

            if not updated_at_str:
                continue

            try:
                updated_at = datetime.fromisoformat(
                    updated_at_str.replace("Z", "+00:00")
                )
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
            message = (
                f"Observe: {stale_ratio:.1f}% of issues are stale. Consider review."
            )
        else:
            score = 2
            risk = "High"
            message = (
                f"Significant: {stale_ratio:.1f}% of issues are stale. "
                f"Backlog accumulation evident."
            )

        return Metric("Stale Issue Ratio", score, max_score, message, risk)


_CHECKER = StaleIssueRatioChecker()


def check_stale_issue_ratio(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Stale Issue Ratio",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="Stale Issue Ratio",
    checker=_CHECKER,
    on_error=_on_error,
)
