"""PR acceptance ratio metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class PrAcceptanceRatioChecker(MetricChecker):
    """Evaluate PR acceptance ratio using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
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

        merged_count = vcs_data.total_merged_prs

        closed_without_merge = sum(
            1
            for pr in vcs_data.closed_prs
            if pr.get("merged") is False or pr.get("state") == "closed"
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


_CHECKER = PrAcceptanceRatioChecker()


def check_pr_acceptance_ratio(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


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
    checker=_CHECKER,
    on_error=_on_error,
)
