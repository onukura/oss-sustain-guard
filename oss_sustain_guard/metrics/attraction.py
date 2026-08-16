"""Contributor attraction metric."""

from typing import Any

from oss_sustain_guard.bot_detection import extract_login, is_bot
from oss_sustain_guard.config import get_excluded_users
from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class ContributorAttractionChecker(MetricChecker):
    """Evaluate contributor attraction using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Measures the project's ability to attract new contributors (CHAOSS Attraction metric).

        Analyzes recent commit history to identify first-time contributors
        in the last 6 months compared to earlier periods.

        Scoring:
        - 5+ new contributors in last 6 months: 10/10 (Strong attraction)
        - 3-4 new contributors: 7/10 (Good attraction)
        - 1-2 new contributors: 4/10 (Moderate attraction)
        - 0 new contributors: 0/10 (Needs attention)
        """
        from datetime import datetime, timedelta, timezone

        max_score = 10

        commits = vcs_data.commits
        if not commits:
            if vcs_data.default_branch is None:
                return Metric(
                    "Contributor Attraction",
                    0,
                    max_score,
                    "Note: Commit history data not available.",
                    "Medium",
                )
            return Metric(
                "Contributor Attraction",
                0,
                max_score,
                "No commit history available for analysis.",
                "Medium",
            )

        # Bot patterns to exclude
        excluded_users = get_excluded_users()

        def extract_author_info(
            commit: dict[str, Any],
        ) -> tuple[str | None, str | None, str | None]:
            """Extract login, email, and name from a commit."""
            login = extract_login(commit)
            author = commit.get("author", {})
            email = author.get("email") if isinstance(author, dict) else None
            name = author.get("name") if isinstance(author, dict) else None
            return login, email, name

        def extract_date(commit: dict[str, Any]) -> datetime | None:
            """Extract a commit timestamp from available fields."""
            date_str = commit.get("authoredDate") or commit.get("committedDate")
            if not date_str:
                return None
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None

        # Collect all contributors with their first commit date
        contributor_first_seen: dict[str, datetime] = {}
        now = datetime.now(timezone.utc)
        six_months_ago = now - timedelta(days=180)

        for commit in commits:
            login, email, name = extract_author_info(commit)
            if not login or is_bot(
                login, email=email, name=name, excluded_users=excluded_users
            ):  # Exclude bots
                continue
            authored_date = extract_date(commit)
            if not authored_date:
                continue

            # Track first appearance of each contributor
            if login not in contributor_first_seen:
                contributor_first_seen[login] = authored_date
            else:
                # Update if we found an earlier commit
                if authored_date < contributor_first_seen[login]:
                    contributor_first_seen[login] = authored_date

        # Count new contributors in the last 6 months
        new_contributors = [
            login
            for login, first_date in contributor_first_seen.items()
            if first_date >= six_months_ago
        ]

        new_count = len(new_contributors)
        total_contributors = len(contributor_first_seen)

        # Scoring logic
        if new_count >= 5:
            score = max_score
            risk = "None"
            message = (
                f"Strong: {new_count} new contributors in last 6 months. "
                f"Active community growth."
            )
        elif new_count >= 3:
            score = 7
            risk = "Low"
            message = (
                f"Good: {new_count} new contributors in last 6 months. "
                f"Healthy attraction."
            )
        elif new_count >= 1:
            score = 4
            risk = "Medium"
            message = (
                f"Moderate: {new_count} new contributor(s) in last 6 months. "
                f"Consider outreach efforts."
            )
        else:
            score = 0
            risk = "Medium"
            message = (
                f"Observe: No new contributors in last 6 months. "
                f"Total: {total_contributors} contributor(s). "
                f"Consider community engagement."
            )

        metadata = {
            "new_contributors": new_count,
            "total_contributors": total_contributors,
        }

        return Metric(
            "Contributor Attraction", score, max_score, message, risk, metadata
        )


_CHECKER = ContributorAttractionChecker()


def check_attraction(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Contributor Attraction",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="Contributor Attraction",
    checker=_CHECKER,
    on_error=_on_error,
)
