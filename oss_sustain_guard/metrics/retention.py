"""Contributor retention metric."""

from typing import Any

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class ContributorRetentionChecker(MetricChecker):
    """Evaluate contributor retention using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Measures contributor retention (CHAOSS Retention metric).

        Analyzes whether contributors who were active 6+ months ago
        are still contributing in recent months.

        Scoring:
        - 80%+ retention: 10/10 (Excellent retention)
        - 60-79% retention: 7/10 (Good retention)
        - 40-59% retention: 4/10 (Moderate retention)
        - <40% retention: 0/10 (Needs attention)
        """
        from datetime import datetime, timedelta, timezone

        max_score = 10

        commits = vcs_data.commits
        if not commits:
            if vcs_data.default_branch is None:
                return Metric(
                    "Contributor Retention",
                    max_score // 2,
                    max_score,
                    "Note: Commit history data not available.",
                    "Medium",
                )
            return Metric(
                "Contributor Retention",
                max_score // 2,
                max_score,
                "No commit history available for analysis.",
                "Medium",
            )

        # Bot patterns to exclude (same as check_bus_factor)
        bot_keywords = [
            "bot",
            "action",
            "dependabot",
            "renovate",
            "github-actions",
            "ci-",
            "autorelease",
            "release-bot",
            "copilot",
            "actions-user",
        ]

        def is_bot(login: str) -> bool:
            """Check if login appears to be a bot."""
            lower = login.lower()
            return any(keyword in lower for keyword in bot_keywords)

        def extract_login(commit: dict[str, Any]) -> str | None:
            """Extract a stable contributor identifier from a commit."""
            author = commit.get("author")
            if not isinstance(author, dict):
                return None
            user = author.get("user")
            if isinstance(user, dict):
                login = user.get("login")
                if login:
                    return login
            for key in ("name", "email"):
                value = author.get(key)
                if value:
                    return value
            return None

        def extract_date(commit: dict[str, Any]) -> datetime | None:
            """Extract a commit timestamp from available fields."""
            date_str = commit.get("authoredDate") or commit.get("committedDate")
            if not date_str:
                return None
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None

        # Track contributors by time period
        now = datetime.now(timezone.utc)
        three_months_ago = now - timedelta(days=90)
        six_months_ago = now - timedelta(days=180)

        recent_contributors: set[str] = set()  # Last 3 months
        earlier_contributors: set[str] = set()  # 3-6 months ago

        for commit in commits:
            login = extract_login(commit)
            if not login or is_bot(login):  # Exclude bots
                continue
            authored_date = extract_date(commit)
            if not authored_date:
                continue

            # Categorize by time period
            if authored_date >= three_months_ago:
                recent_contributors.add(login)
            elif authored_date >= six_months_ago:
                earlier_contributors.add(login)

        # Calculate retention: how many earlier contributors are still active?
        if not earlier_contributors:
            return Metric(
                "Contributor Retention",
                max_score,
                max_score,
                "New project: Not enough history to assess retention.",
                "None",
            )

        retained_contributors = recent_contributors & earlier_contributors
        retention_rate = len(retained_contributors) / len(earlier_contributors)
        retention_percentage = retention_rate * 100

        # Scoring logic
        if retention_rate >= 0.8:
            score = max_score
            risk = "None"
            message = (
                f"Excellent: {retention_percentage:.0f}% contributor retention. "
                f"{len(retained_contributors)}/{len(earlier_contributors)} contributors "
                f"remain active."
            )
        elif retention_rate >= 0.6:
            score = 7
            risk = "Low"
            message = (
                f"Good: {retention_percentage:.0f}% contributor retention. "
                f"{len(retained_contributors)}/{len(earlier_contributors)} contributors "
                f"remain active."
            )
        elif retention_rate >= 0.4:
            score = 4
            risk = "Medium"
            message = (
                f"Moderate: {retention_percentage:.0f}% contributor retention. "
                f"{len(retained_contributors)}/{len(earlier_contributors)} contributors "
                f"remain active. Consider engagement efforts."
            )
        else:
            score = 0
            risk = "High"
            message = (
                f"Needs attention: {retention_percentage:.0f}% contributor retention. "
                f"Only {len(retained_contributors)}/{len(earlier_contributors)} earlier "
                f"contributors remain active."
            )

        return Metric("Contributor Retention", score, max_score, message, risk)


_CHECKER = ContributorRetentionChecker()


def check_retention(repo_data: dict[str, Any] | VCSRepositoryData) -> Metric:
    if isinstance(repo_data, VCSRepositoryData):
        return _CHECKER.check(repo_data, _LEGACY_CONTEXT)
    return _CHECKER.check_legacy(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Contributor Retention",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="Contributor Retention",
    checker=_CHECKER,
    on_error=_on_error,
)
