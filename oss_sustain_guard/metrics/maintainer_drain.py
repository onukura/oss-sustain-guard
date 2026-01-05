"""Maintainer retention metric."""

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


class MaintainerRetentionChecker(MetricChecker):
    """Check maintainer retention using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Checks for a recent drain in active maintainers with improved analysis.

        Improvements:
        - Excludes bot accounts (dependabot, renovate, github-actions, etc.)
        - Compares recent (last 25) vs older (25-50) commits
        - Time-series based assessment
        - Graduated status levels: 50%/70%/90% reduction

        Status levels:
        - 90%+ reduction: 15pt reduction (critical)
        - 70-89% reduction: 10pt reduction (high)
        - 50-69% reduction: 5pt reduction (medium)
        - <50% reduction: 0pt reduction (acceptable)
        """
        max_score = 10

        commits = vcs_data.commits
        if not commits:
            if vcs_data.default_branch is None:
                return Metric(
                    "Maintainer Retention",
                    max_score,
                    max_score,
                    "Note: Maintainer data not available for verification.",
                    "None",
                )
            return Metric(
                "Maintainer Retention",
                max_score,
                max_score,
                "Insufficient commit history to detect drain.",
                "None",
            )

        if len(commits) < 50:
            # If history is too short, cannot detect drain
            return Metric(
                "Maintainer Retention",
                max_score,
                max_score,
                "Insufficient commit history to detect drain.",
                "None",
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

        # Split into recent and older commits
        recent_commits = commits[:25]
        older_commits = commits[25:50]

        # Extract human contributors (exclude bots)
        recent_authors = set()
        for commit in recent_commits:
            login, email, name = extract_author_info(commit)
            if login and not is_bot(
                login, email=email, name=name, excluded_users=excluded_users
            ):
                recent_authors.add(login)

        older_authors = set()
        for commit in older_commits:
            login, email, name = extract_author_info(commit)
            if login and not is_bot(
                login, email=email, name=name, excluded_users=excluded_users
            ):
                older_authors.add(login)

        # If we have very few real contributors, cannot assess
        if not older_authors or not recent_authors:
            return Metric(
                "Maintainer Retention",
                max_score,
                max_score,
                "Insufficient human contributor data.",
                "None",
            )

        # Calculate drain ratio
        drain_ratio = len(recent_authors) / len(older_authors)
        reduction_percentage = (1 - drain_ratio) * 100

        # Scoring logic with graduated status levels
        if drain_ratio <= 0.1:  # 90%+ reduction
            score = 0
            risk = "Critical"
            message = (
                f"Needs support: {reduction_percentage:.0f}% reduction in maintainers. "
                f"From {len(older_authors)} → {len(recent_authors)} active contributors."
            )
        elif drain_ratio <= 0.3:  # 70-89% reduction
            score = 3
            risk = "High"
            message = (
                f"Needs attention: {reduction_percentage:.0f}% reduction in maintainers. "
                f"From {len(older_authors)} → {len(recent_authors)} contributors."
            )
        elif drain_ratio <= 0.5:  # 50-69% reduction
            score = 5
            risk = "Medium"
            message = (
                f"Monitor: {reduction_percentage:.0f}% reduction in maintainers. "
                f"From {len(older_authors)} → {len(recent_authors)} contributors."
            )
        else:
            score = max_score
            risk = "None"
            message = (
                f"Stable: {len(recent_authors)} active maintainers. "
                f"No significant drain detected."
            )

        return Metric("Maintainer Retention", score, max_score, message, risk)


_CHECKER = MaintainerRetentionChecker()


def check_maintainer_drain(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Maintainer Retention",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "High",
    )


METRIC = MetricSpec(
    name="Maintainer Retention",
    checker=_CHECKER,
    on_error=_on_error,
    error_log="  [yellow]⚠️  Maintainer retention check incomplete: {error}[/yellow]",
)
