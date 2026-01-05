"""Release rhythm metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class ReleaseCadenceChecker(MetricChecker):
    """Evaluate release cadence using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates the release frequency and recency.

        Improvements:
        - Distinguishes between "active development" and "stable maintenance"
        - Considers release frequency as a sign of ongoing support
        - Detects projects that commit but never release

        Scoring:
        - <3 months since last release: 10/10 (Active)
        - 3-6 months: 7/10 (Moderate)
        - 6-12 months: 4/10 (Slow)
        - >12 months: 0/10 (Abandoned)
        """
        from datetime import datetime

        max_score = 10

        releases = vcs_data.releases

        if not releases:
            # No releases detected - check if archived
            if vcs_data.is_archived:
                return Metric(
                    "Release Rhythm",
                    max_score,
                    max_score,
                    "Archived repository (no releases expected).",
                    "None",
                )
            return Metric(
                "Release Rhythm",
                0,
                max_score,
                "No releases found. Project may not be user-ready.",
                "High",
            )

        # Get the most recent release
        latest_release = releases[0]
        published_at_str = latest_release.get("publishedAt")
        tag_name = latest_release.get("tagName", "unknown")

        if not published_at_str:
            return Metric(
                "Release Rhythm",
                0,
                max_score,
                "Note: Release date information not available.",
                "High",
            )

        try:
            published_at = datetime.fromisoformat(
                published_at_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            return Metric(
                "Release Rhythm",
                0,
                max_score,
                "Note: Release date format not recognized.",
                "High",
            )

        now = datetime.now(published_at.tzinfo)
        days_since_release = (now - published_at).days

        # Scoring logic
        if days_since_release < 90:  # <3 months
            score = max_score
            risk = "None"
            message = (
                f"Active: Last release {days_since_release} days ago ({tag_name})."
            )
        elif days_since_release < 180:  # 3-6 months
            score = 7
            risk = "Low"
            message = (
                f"Moderate: Last release {days_since_release} days ago ({tag_name}). "
                f"Consider new release."
            )
        elif days_since_release < 365:  # 6-12 months
            score = 4
            risk = "Medium"
            message = (
                f"Slow: Last release {days_since_release} days ago ({tag_name}). "
                f"Release cycle appears stalled."
            )
        else:  # >12 months
            score = 0
            risk = "High"
            message = (
                f"Observe: Last release {days_since_release} days ago ({tag_name}). "
                f"No releases in over a year."
            )

        return Metric("Release Rhythm", score, max_score, message, risk)


_CHECKER = ReleaseCadenceChecker()


def check_release_cadence(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Release Rhythm",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="Release Rhythm",
    checker=_CHECKER,
    on_error=_on_error,
)
