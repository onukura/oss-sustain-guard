"""Issue resolution duration metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class IssueResolutionDurationChecker(MetricChecker):
    """Evaluate issue resolution duration using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates Issue Resolution Duration (CHAOSS metric).

        Measures average time to close issues. Adjusts expectations based on
        project scale (stargazers count) to account for larger issue volumes.

        Scoring (Small/Medium projects <10K stars):
        - <7 days avg: 10/10 (Fast)
        - 7-30 days: 7/10 (Good)
        - 30-90 days: 4/10 (Moderate)
        - 90-180 days: 2/10 (Slow)
        - >180 days: 0/10 (Very slow)

        Scoring (Large projects 10K-100K stars):
        - <30 days avg: 10/10 (Fast)
        - 30-90 days: 7/10 (Good)
        - 90-180 days: 5/10 (Moderate)
        - 180-365 days: 3/10 (Acceptable)
        - >365 days: 0/10 (Needs attention)

        Scoring (Very large projects ≥100K stars):
        - <60 days avg: 10/10 (Fast)
        - 60-180 days: 7/10 (Good)
        - 180-365 days: 5/10 (Moderate)
        - 365-730 days: 3/10 (Acceptable)
        - >730 days: 0/10 (Needs attention)
        """
        from datetime import datetime

        max_score = 10

        closed_issues = vcs_data.closed_issues
        if not closed_issues:
            return Metric(
                "Issue Resolution Duration",
                7,  # More generous: 7/10 instead of 5/10
                max_score,
                "Note: No closed issues in recent history (may be addressing issues promptly).",
                "None",
            )

        resolution_times: list[float] = []

        for node in closed_issues:
            created_at_str = node.get("createdAt")
            closed_at_str = node.get("closedAt")

            if not created_at_str or not closed_at_str:
                continue

            try:
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
                closed_at = datetime.fromisoformat(closed_at_str.replace("Z", "+00:00"))
                resolution_days = (closed_at - created_at).total_seconds() / 86400
                resolution_times.append(resolution_days)
            except (ValueError, AttributeError):
                pass

        if not resolution_times:
            return Metric(
                "Issue Resolution Duration",
                max_score // 2,
                max_score,
                "Note: Unable to calculate issue resolution times.",
                "None",
            )

        avg_resolution = sum(resolution_times) / len(resolution_times)

        # Detect project scale for adjusted scoring
        stargazers_count = vcs_data.star_count
        is_very_large = stargazers_count >= 100000
        is_large = stargazers_count >= 10000

        # Scoring logic - adjusted for project scale
        if is_very_large:
            # Very large projects: Most lenient thresholds (massive issue volume)
            if avg_resolution < 60:
                score = max_score
                risk = "None"
                message = f"Excellent: Avg issue resolution {avg_resolution:.1f} days. Fast for very large-scale project."
            elif avg_resolution < 180:
                score = 7
                risk = "Low"
                message = f"Good: Avg issue resolution {avg_resolution:.1f} days."
            elif avg_resolution < 365:
                score = 5
                risk = "Medium"
                message = f"Moderate: Avg issue resolution {avg_resolution:.1f} days. Reasonable for very large project."
            elif avg_resolution < 730:
                score = 3
                risk = "Medium"
                message = f"Monitor: Avg issue resolution {avg_resolution:.1f} days. Acceptable given project scale."
            else:
                score = 0
                risk = "High"
                message = f"Observe: Avg issue resolution {avg_resolution:.1f} days. Consider improving."
        elif is_large:
            # Large projects: Lenient thresholds (higher issue volume)
            if avg_resolution < 30:
                score = max_score
                risk = "None"
                message = f"Excellent: Avg issue resolution {avg_resolution:.1f} days. Fast for large-scale project."
            elif avg_resolution < 90:
                score = 7
                risk = "Low"
                message = f"Good: Avg issue resolution {avg_resolution:.1f} days."
            elif avg_resolution < 180:
                score = 5
                risk = "Medium"
                message = f"Moderate: Avg issue resolution {avg_resolution:.1f} days. Acceptable for large project."
            elif avg_resolution < 365:
                score = 3
                risk = "Medium"
                message = f"Monitor: Avg issue resolution {avg_resolution:.1f} days. Consider improving."
            else:
                score = 0
                risk = "High"
                message = f"Observe: Avg issue resolution {avg_resolution:.1f} days. Significant backlog detected."
        else:
            # Small/Medium projects: Standard thresholds
            if avg_resolution < 7:
                score = max_score
                risk = "None"
                message = f"Excellent: Avg issue resolution {avg_resolution:.1f} days. Fast response."
            elif avg_resolution < 30:
                score = 7
                risk = "Low"
                message = f"Good: Avg issue resolution {avg_resolution:.1f} days."
            elif avg_resolution < 90:
                score = 4
                risk = "Medium"
                message = f"Moderate: Avg issue resolution {avg_resolution:.1f} days. Consider improving."
            elif avg_resolution < 180:
                score = 2
                risk = "High"
                message = f"Needs attention: Avg issue resolution {avg_resolution:.1f} days. Backlog appears to be growing."
            else:
                score = 0
                risk = "High"
                message = f"Observe: Avg issue resolution {avg_resolution:.1f} days. Significant backlog detected."

        return Metric("Issue Resolution Duration", score, max_score, message, risk)


_CHECKER = IssueResolutionDurationChecker()


def check_issue_resolution_duration(
    repo_data: VCSRepositoryData,
) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Issue Resolution Duration",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="Issue Resolution Duration",
    checker=_CHECKER,
    on_error=_on_error,
)
