"""Review health metric."""

from typing import Any

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class ReviewHealthChecker(MetricChecker):
    """Evaluate review health using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates pull request review health (CHAOSS Review Health metric).

        Considers:
        - Time to first review on merged PRs
        - Review count per PR

        Scoring:
        - Avg first review <48h & 2+ reviews: 10/10 (Excellent)
        - Avg first review <7d & 1+ reviews: 7/10 (Good)
        - Avg first review >7d or 0 reviews: 0/10 (Needs improvement)
        """
        from datetime import datetime

        max_score = 10

        prs = vcs_data.merged_prs

        if not prs:
            return Metric(
                "Review Health",
                max_score // 2,
                max_score,
                "Note: No recent merged pull requests to analyze.",
                "None",
            )

        review_times: list[float] = []
        review_counts: list[int] = []

        for node in prs:
            created_at_str = node.get("createdAt")
            reviews = node.get("reviews", {})
            review_edges: list[dict[str, Any]] = []
            review_total = 0

            if isinstance(reviews, dict):
                review_edges = reviews.get("edges", [])
                review_total = reviews.get("totalCount", 0)
            elif isinstance(reviews, list):
                review_edges = reviews
                review_total = len(reviews)

            if not created_at_str:
                continue

            review_counts.append(review_total)

            # Calculate time to first review
            if review_edges:
                first_review = review_edges[0]
                if isinstance(first_review, dict):
                    if "node" in first_review and isinstance(
                        first_review["node"], dict
                    ):
                        first_review = first_review["node"]
                if not isinstance(first_review, dict):
                    continue
                first_review_at_str = first_review.get("createdAt")

                if first_review_at_str:
                    try:
                        created_at = datetime.fromisoformat(
                            created_at_str.replace("Z", "+00:00")
                        )
                        first_review_at = datetime.fromisoformat(
                            first_review_at_str.replace("Z", "+00:00")
                        )
                        review_time_hours = (
                            first_review_at - created_at
                        ).total_seconds() / 3600
                        review_times.append(review_time_hours)
                    except (ValueError, AttributeError):
                        pass

        if not review_times:
            return Metric(
                "Review Health",
                0,
                max_score,
                "Observe: No review activity detected in recent PRs.",
                "Medium",
            )

        avg_review_time = sum(review_times) / len(review_times) if review_times else 999
        avg_review_count = (
            sum(review_counts) / len(review_counts) if review_counts else 0
        )

        # Scoring logic
        if avg_review_time < 48 and avg_review_count >= 2:
            score = max_score
            risk = "None"
            message = (
                f"Excellent: Avg time to first review {avg_review_time:.1f}h. "
                f"Avg {avg_review_count:.1f} reviews per PR."
            )
        elif avg_review_time < 168 and avg_review_count >= 1:  # <7 days
            score = 7
            risk = "Low"
            message = (
                f"Good: Avg time to first review {avg_review_time:.1f}h "
                f"({avg_review_time / 24:.1f}d). Avg {avg_review_count:.1f} reviews per PR."
            )
        elif avg_review_time < 168:  # <7 days but low review count
            score = 4
            risk = "Medium"
            message = (
                f"Moderate: Avg time to first review {avg_review_time:.1f}h, "
                f"but low review count ({avg_review_count:.1f} per PR)."
            )
        else:
            score = 0
            risk = "Medium"
            message = (
                f"Observe: Slow review process (avg {avg_review_time / 24:.1f}d to first review). "
                f"Consider increasing reviewer engagement."
            )

        metadata = {
            "avg_review_time_hours": round(avg_review_time, 2),
            "avg_review_count": round(avg_review_count, 2),
        }

        return Metric("Review Health", score, max_score, message, risk, metadata)


_CHECKER = ReviewHealthChecker()


def check_review_health(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Review Health",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="Review Health",
    checker=_CHECKER,
    on_error=_on_error,
)
