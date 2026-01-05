"""Community health metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class CommunityHealthChecker(MetricChecker):
    """Evaluate community health using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates community engagement and responsiveness.

        Considers:
        - Issue response time (first comment on new issues)
        - Community activity level
        - Maintainer engagement

        Scoring (0-10 scale):
        - Average response <48h: 10/10 (Excellent)
        - Average response <7d: 6/10 (Good)
        - Average response 7-30d: 2/10 (Slow)
        - Average response >30d: 0/10 (Poor)
        - No open issues: 10/10 (Low activity or well-maintained)
        """
        from datetime import datetime

        max_score = 10

        issues = vcs_data.open_issues

        if not issues:
            return Metric(
                "Community Health",
                max_score,
                max_score,
                "No open issues. Well-maintained or low activity.",
                "None",
            )

        response_times: list[int] = []

        for issue in issues:
            created_at_str = issue.get("createdAt")
            comments = issue.get("comments", [])
            if isinstance(comments, dict):
                comment_edges = comments.get("edges")
                if isinstance(comment_edges, list):
                    comments = [
                        edge.get("node", {})
                        for edge in comment_edges
                        if isinstance(edge, dict)
                    ]
                else:
                    comments = []

            if not created_at_str or not comments:
                # Issue with no comments yet
                continue

            first_comment = comments[0] if comments else {}
            if not isinstance(first_comment, dict):
                continue
            first_comment_at_str = first_comment.get("createdAt")

            if not first_comment_at_str:
                continue

            try:
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
                first_comment_at = datetime.fromisoformat(
                    first_comment_at_str.replace("Z", "+00:00")
                )
                response_time_hours = (
                    first_comment_at - created_at
                ).total_seconds() / 3600
                response_times.append(int(response_time_hours))
            except (ValueError, AttributeError):
                pass

        if not response_times:
            return Metric(
                "Community Health",
                6,  # 3/5 → 6/10 - more generous: 6/10 for no data
                max_score,
                "Note: No recent issue responses to analyze (may indicate low issue volume).",
                "None",
            )

        avg_response_time = sum(response_times) / len(response_times)

        # Scoring logic (0-10 scale)
        if avg_response_time < 48:  # <2 days
            score = max_score
            risk = "None"
            message = (
                f"Excellent: Average issue response time {avg_response_time:.1f} hours."
            )
        elif avg_response_time < 168:  # <7 days
            score = 6  # 3/5 → 6/10
            risk = "None"
            message = (
                f"Good: Average issue response time {avg_response_time:.1f} hours "
                f"({avg_response_time / 24:.1f} days)."
            )
        elif avg_response_time < 720:  # <30 days
            score = 2  # 1/5 → 2/10
            risk = "Medium"
            message = (
                f"Needs attention: Average issue response time {avg_response_time:.1f} "
                f"hours ({avg_response_time / 24:.1f} days)."
            )
        else:
            score = 0
            risk = "High"
            message = (
                f"Observe: Average issue response time {avg_response_time:.1f} hours "
                f"({avg_response_time / 24:.1f} days). Community response could be improved."
            )

        return Metric("Community Health", score, max_score, message, risk)


_CHECKER = CommunityHealthChecker()


def check_community_health(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Community Health",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="Community Health",
    checker=_CHECKER,
    on_error=_on_error,
)
