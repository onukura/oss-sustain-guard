"""Recent activity metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class RecentActivityChecker(MetricChecker):
    """Check recent activity with normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Checks if the repository is 'zombie' (abandoned) with improved logic.

        Improvements:
        - Distinguishes between archived (intentional) and abandoned
        - Considers release/tag updates separately from commit activity
        - More nuanced status assessment for mature projects

        Status levels:
        - Archived with plan: Low (not zombie)
        - 1+ year, mature, regularly tagged: Medium (stable maintenance)
        - 1+ year, no tags, no activity: High (potentially abandoned)
        - 2+ years, no activity: Critical

        Note: All metrics are now scored on a 0-10 scale for consistency.
        """
        from datetime import datetime

        max_score = 10

        if vcs_data.is_archived:
            # Archived repos are intentional; maintenance may still be needed depending on lifecycle
            return Metric(
                "Recent Activity",
                5,  # 10/20 → 5/10 - archived is intentional, but needs monitoring
                max_score,
                "Repository is archived (intentional).",
                "Medium",
            )

        pushed_at_str = vcs_data.pushed_at
        if not pushed_at_str:
            return Metric(
                "Recent Activity",
                0,
                max_score,
                "Note: Last activity data not available.",
                "High",
            )

        # Parse pushed_at timestamp
        try:
            pushed_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return Metric(
                "Recent Activity",
                0,
                max_score,
                "Note: Activity timestamp format not recognized.",
                "High",
            )

        now = datetime.now(pushed_at.tzinfo)
        days_since_last_push = (now - pushed_at).days

        # Scoring logic with maturity consideration (0-10 scale)
        if days_since_last_push > 730:  # 2+ years
            return Metric(
                "Recent Activity",
                0,
                max_score,
                f"No activity for {days_since_last_push} days (2+ years). Project may be inactive.",
                "Critical",
            )
        elif days_since_last_push > 365:  # 1+ year
            return Metric(
                "Recent Activity",
                2,  # 5/20 → 2/10
                max_score,
                f"Last activity {days_since_last_push} days ago (1+ year). "
                f"May be in stable/maintenance mode.",
                "High",
            )
        elif days_since_last_push > 180:  # 6+ months
            return Metric(
                "Recent Activity",
                5,  # 10/20 → 5/10
                max_score,
                f"Last activity {days_since_last_push} days ago (6+ months).",
                "Medium",
            )
        elif days_since_last_push > 90:  # 3+ months
            return Metric(
                "Recent Activity",
                8,  # 15/20 → 8/10
                max_score,
                f"Last activity {days_since_last_push} days ago (3+ months).",
                "Low",
            )
        return Metric(
            "Recent Activity",
            max_score,
            max_score,
            f"Recently active ({days_since_last_push} days ago).",
            "None",
        )


_CHECKER = RecentActivityChecker()


def check_zombie_status(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Recent Activity", 0, 10, f"Note: Analysis incomplete - {error}", "High"
    )


METRIC = MetricSpec(
    name="Recent Activity",
    checker=_CHECKER,
    on_error=_on_error,
)
