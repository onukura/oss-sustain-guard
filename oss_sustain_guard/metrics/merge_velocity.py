"""Change request resolution metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class MergeVelocityChecker(MetricChecker):
    """Evaluate merge velocity using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates the merge velocity (PR turnaround time) with relaxed thresholds.

        Improvements:
        - Graduated scoring based on actual merge times
        - OSS-realistic thresholds (accounting for volunteer teams)
        - Focuses on pathological slowness detection

        Status levels:
        - >2000 hours (83 days): Critical (severely slow)
        - 1000-2000 hours (42-83 days): High (very slow)
        - 500-1000 hours (21-42 days): Medium (slow but acceptable)
        - <500 hours (21 days): Low/Excellent (responsive)
        """
        from datetime import datetime

        max_score = 10

        pull_requests = vcs_data.merged_prs
        if not pull_requests:
            return Metric(
                "Change Request Resolution",
                max_score,
                max_score,
                "No merged PRs available for analysis.",
                "None",
            )

        merge_times: list[int] = []
        for node in pull_requests:
            created_at_str = node.get("createdAt")
            merged_at_str = node.get("mergedAt")

            if created_at_str and merged_at_str:
                try:
                    created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                    merged_at = datetime.fromisoformat(
                        merged_at_str.replace("Z", "+00:00")
                    )
                    merge_time_hours = (merged_at - created_at).total_seconds() / 3600
                    merge_times.append(int(merge_time_hours))
                except (ValueError, AttributeError):
                    pass

        if not merge_times:
            return Metric(
                "Change Request Resolution",
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
                f"Monitor: Average merge time {avg_merge_time:.0f} hours ({avg_merge_time / 24:.1f} days). "
                f"Slow but acceptable for volunteer-driven OSS."
            )
        else:  # <21 days
            score = max_score
            risk = "None"
            message = (
                f"Good: Average merge time {avg_merge_time:.0f} hours ({avg_merge_time / 24:.1f} days). "
                f"Responsive to PRs."
            )

        return Metric("Change Request Resolution", score, max_score, message, risk)


_CHECKER = MergeVelocityChecker()


def check_merge_velocity(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Change Request Resolution",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="Change Request Resolution",
    checker=_CHECKER,
    on_error=_on_error,
)
