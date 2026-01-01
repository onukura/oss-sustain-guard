"""Maintainer retention metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_maintainer_drain(repo_data: dict[str, Any]) -> Metric:
    """
    Checks for a recent drain in active maintainers with improved analysis.

    Improvements:
    - Excludes bot accounts (dependabot, renovate, github-actions, etc.)
    - Compares recent (last 25) vs older (25-50) commits
    - Time-series based assessment
    - Graduated risk levels: 50%/70%/90% reduction

    Risk levels:
    - 90%+ reduction: 15pt reduction (critical)
    - 70-89% reduction: 10pt reduction (high)
    - 50-69% reduction: 5pt reduction (medium)
    - <50% reduction: 0pt reduction (acceptable)
    """
    max_score = 10

    # Extract commit history
    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
        return Metric(
            "Maintainer Retention",
            max_score,
            max_score,
            "Note: Maintainer data not available for verification.",
            "None",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Maintainer Retention",
            max_score,
            max_score,
            "Note: Maintainer data not available for verification.",
            "None",
        )

    history = target.get("history", {}).get("edges", [])
    if len(history) < 50:
        # If history is too short, cannot detect drain
        return Metric(
            "Maintainer Retention",
            max_score,
            max_score,
            "Insufficient commit history to detect drain.",
            "None",
        )

    # Bot patterns to exclude
    bot_keywords = [
        "bot",
        "action",
        "dependabot",
        "renovate",
        "github-actions",
        "ci-",
        "autorelease",
        "release-bot",
    ]

    def is_bot(login: str) -> bool:
        """Check if login appears to be a bot."""
        lower = login.lower()
        return any(keyword in lower for keyword in bot_keywords)

    # Split into recent and older commits
    recent_commits = history[:25]
    older_commits = history[25:50]

    # Extract human contributors (exclude bots)
    recent_authors = set()
    for edge in recent_commits:
        user = edge.get("node", {}).get("author", {}).get("user")
        if user:
            login = user.get("login")
            if login and not is_bot(login):
                recent_authors.add(login)

    older_authors = set()
    for edge in older_commits:
        user = edge.get("node", {}).get("author", {}).get("user")
        if user:
            login = user.get("login")
            if login and not is_bot(login):
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

    # Scoring logic with graduated risk levels
    if drain_ratio <= 0.1:  # 90%+ reduction
        score = 0
        risk = "Critical"
        message = (
            f"Critical: {reduction_percentage:.0f}% reduction in maintainers. "
            f"From {len(older_authors)} → {len(recent_authors)} active contributors."
        )
    elif drain_ratio <= 0.3:  # 70-89% reduction
        score = 3
        risk = "High"
        message = (
            f"High: {reduction_percentage:.0f}% reduction in maintainers. "
            f"From {len(older_authors)} → {len(recent_authors)} contributors."
        )
    elif drain_ratio <= 0.5:  # 50-69% reduction
        score = 5
        risk = "Medium"
        message = (
            f"Medium: {reduction_percentage:.0f}% reduction in maintainers. "
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


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_maintainer_drain(repo_data)


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
    checker=_check,
    on_error=_on_error,
    error_log="  [yellow]⚠️  Maintainer retention check incomplete: {error}[/yellow]",
)
