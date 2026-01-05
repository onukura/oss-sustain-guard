"""PR merge speed metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class PrMergeSpeedChecker(MetricChecker):
    """Evaluate PR merge speed using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates PR Merge Speed - median time from PR creation to merge.

        Measures the efficiency of the pull request review and merge process.
        Faster merge times indicate responsive review cycles.

        Scoring:
        - Median <3 days: 5/5 (Excellent)
        - Median 3-7 days: 4/5 (Good)
        - Median 7-30 days: 2/5 (Moderate)
        - Median >30 days: 1/5 (Slow)

        CHAOSS Aligned: Code Development Efficiency
        """
        from datetime import datetime

        max_score = 10

        merged_prs = vcs_data.merged_prs

        if not merged_prs:
            return Metric(
                "PR Merge Speed",
                5,
                max_score,
                "Note: No merged PRs available for analysis.",
                "None",
            )

        merge_times: list[float] = []

        for node in merged_prs:
            created_at_str = node.get("createdAt")
            merged_at_str = node.get("mergedAt")

            if not created_at_str or not merged_at_str:
                continue

            try:
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
                merged_at = datetime.fromisoformat(merged_at_str.replace("Z", "+00:00"))
                merge_days = (merged_at - created_at).total_seconds() / 86400
                merge_times.append(merge_days)
            except (ValueError, AttributeError):
                pass

        if not merge_times:
            return Metric(
                "PR Merge Speed",
                5,
                max_score,
                "Note: Unable to calculate PR merge times.",
                "None",
            )

        # Calculate median (middle value)
        merge_times.sort()
        median_merge_days = (
            merge_times[len(merge_times) // 2]
            if len(merge_times) % 2 == 1
            else (
                merge_times[len(merge_times) // 2 - 1]
                + merge_times[len(merge_times) // 2]
            )
            / 2
        )

        # Scoring logic
        if median_merge_days < 3:
            score = max_score
            risk = "None"
            message = (
                f"Excellent: Median PR merge time {median_merge_days:.1f}d. "
                f"Responsive review cycle."
            )
        elif median_merge_days < 7:
            score = 8
            risk = "Low"
            message = f"Good: Median PR merge time {median_merge_days:.1f}d."
        elif median_merge_days < 30:
            score = 4
            risk = "Medium"
            message = f"Moderate: Median PR merge time {median_merge_days:.1f}d."
        else:
            score = 2
            risk = "High"
            message = (
                f"Observe: Median PR merge time {median_merge_days:.1f}d. "
                f"Review cycle is slow."
            )

        return Metric("PR Merge Speed", score, max_score, message, risk)


_CHECKER = PrMergeSpeedChecker()


def check_pr_merge_speed(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "PR Merge Speed",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="PR Merge Speed",
    checker=_CHECKER,
    on_error=_on_error,
)
