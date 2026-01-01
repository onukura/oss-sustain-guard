"""Contributor attraction metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_attraction(repo_data: dict[str, Any]) -> Metric:
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

    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
        return Metric(
            "Contributor Attraction",
            0,
            max_score,
            "Note: Commit history data not available.",
            "Medium",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Contributor Attraction",
            0,
            max_score,
            "Note: Commit history data not available.",
            "Medium",
        )

    history = target.get("history", {}).get("edges", [])
    if not history:
        return Metric(
            "Contributor Attraction",
            0,
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

    # Collect all contributors with their first commit date
    contributor_first_seen: dict[str, datetime] = {}
    now = datetime.now(timezone.utc)
    six_months_ago = now - timedelta(days=180)

    for edge in history:
        node = edge.get("node", {})
        author = node.get("author", {})
        user = author.get("user")
        authored_date_str = node.get("authoredDate")

        if not user or not authored_date_str:
            continue

        login = user.get("login")
        if not login or is_bot(login):  # Exclude bots
            continue

        try:
            authored_date = datetime.fromisoformat(
                authored_date_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
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
        message = f"Strong: {new_count} new contributors in last 6 months. Active community growth."
    elif new_count >= 3:
        score = 7
        risk = "Low"
        message = (
            f"Good: {new_count} new contributors in last 6 months. Healthy attraction."
        )
    elif new_count >= 1:
        score = 4
        risk = "Medium"
        message = f"Moderate: {new_count} new contributor(s) in last 6 months. Consider outreach efforts."
    else:
        score = 0
        risk = "Medium"
        message = (
            f"Observe: No new contributors in last 6 months. "
            f"Total: {total_contributors} contributor(s). Consider community engagement."
        )

    return Metric("Contributor Attraction", score, max_score, message, risk)


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_attraction(repo_data)


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
    checker=_check,
    on_error=_on_error,
)
