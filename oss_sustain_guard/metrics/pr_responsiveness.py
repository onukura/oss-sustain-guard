"""PR responsiveness metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class PrResponsivenessChecker(MetricChecker):
    """Evaluate PR responsiveness using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
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

        closed_prs = vcs_data.closed_prs

        if not closed_prs:
            return Metric(
                "PR Responsiveness",
                max_score // 2,
                max_score,
                "Note: No closed PRs to analyze responsiveness.",
                "None",
            )

        response_times: list[float] = []

        for node in closed_prs:
            created_at_str = node.get("createdAt")
            reviews = node.get("reviews", [])
            if isinstance(reviews, dict):
                review_edges = reviews.get("edges")
                if isinstance(review_edges, list):
                    reviews = [
                        edge.get("node", {})
                        for edge in review_edges
                        if isinstance(edge, dict)
                    ]
                else:
                    reviews = []
            if not reviews:
                review_payload = node.get("review_edges")
                if isinstance(review_payload, list):
                    reviews = [
                        edge.get("node", {})
                        for edge in review_payload
                        if isinstance(edge, dict)
                    ]
                elif isinstance(review_payload, dict):
                    review_edges = review_payload.get("edges")
                    if isinstance(review_edges, list):
                        reviews = [
                            edge.get("node", {})
                            for edge in review_edges
                            if isinstance(edge, dict)
                        ]

            if not created_at_str or not reviews:
                continue

            first_review = reviews[0] if reviews else {}
            if not isinstance(first_review, dict):
                continue
            first_review_at_str = first_review.get("createdAt")

            if not first_review_at_str:
                continue

            try:
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
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
            message = f"Excellent: Avg PR first response {avg_response:.1f}h. Very responsive."
        elif avg_response < 168:  # 7 days
            score = 6
            risk = "Low"
            message = f"Good: Avg PR first response {avg_response / 24:.1f}d."
        else:
            score = 0
            risk = "Medium"
            message = (
                f"Observe: Avg PR first response {avg_response / 24:.1f}d. "
                f"Contributors may wait long."
            )

        return Metric("PR Responsiveness", score, max_score, message, risk)


_CHECKER = PrResponsivenessChecker()


def check_pr_responsiveness(
    repo_data: VCSRepositoryData,
) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "PR Responsiveness",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="PR Responsiveness",
    checker=_CHECKER,
    on_error=_on_error,
)
