"""Contributor redundancy metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_bus_factor(repo_data: dict[str, Any]) -> Metric:
    """
    Analyzes the 'Bus Factor' of a repository with improved logic.

    Considers:
    - Top contributor percentage (recent commits)
    - Project maturity (total commits)
    - Contributor diversity trend

    Risk levels:
    - 90%+ single author: 20pt reduction (but not critical for new projects)
    - 70-89%: 10pt reduction
    - 50-69%: 5pt reduction
    - <50%: 0pt reduction (healthy)

    Note: All metrics are now scored on a 0-10 scale for consistency.
    """
    max_score = 10

    # Extract commit history
    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
        return Metric(
            "Contributor Redundancy",
            0,
            max_score,
            "Note: Commit history data not available.",
            "High",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Contributor Redundancy",
            0,
            max_score,
            "Note: Commit history data not available.",
            "High",
        )

    history = target.get("history", {}).get("edges", [])
    if not history:
        return Metric(
            "Contributor Redundancy",
            0,
            max_score,
            "No commit history available for analysis.",
            "Critical",
        )

    # Bot patterns to exclude (same as check_maintainer_drain)
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

    # Count commits per author (excluding bots)
    author_counts: dict[str, int] = {}
    for edge in history:
        node = edge.get("node", {})
        author = node.get("author", {})
        user = author.get("user")
        if user:
            login = user.get("login")
            if login and not is_bot(login):
                author_counts[login] = author_counts.get(login, 0) + 1

    # Check if we have any human contributors
    if not author_counts:
        return Metric(
            "Contributor Redundancy",
            0,
            max_score,
            "No human contributors found (only bot commits).",
            "Critical",
        )

    # Calculate total commits by human contributors only
    total_commits = sum(author_counts.values())
    if total_commits == 0:
        return Metric(
            "Contributor Redundancy",
            0,
            max_score,
            "No commits found.",
            "Critical",
        )

    # Find the top contributor
    top_contributor_commits = max(author_counts.values())
    percentage = (top_contributor_commits / total_commits) * 100
    num_contributors = len(author_counts)

    # Extract total commit count for BDFL model detection
    total_repo_commits = target.get("history", {}).get("totalCount", len(history))

    # Determine project maturity based on total commit count
    # BDFL (Benevolent Dictator For Life) model detection:
    # - Mature project (1000+ commits) with single-author > 90% = legitimate BDFL
    is_mature_bdfl = total_repo_commits >= 1000 and percentage >= 90
    is_mature_project = total_repo_commits >= 100

    # Scoring logic with BDFL model recognition (0-10 scale)
    if percentage >= 90:
        # Very high single-author concentration
        if is_mature_bdfl:
            # Mature BDFL model = proven track record
            score = 8  # 15/20 → 8/10
            risk = "Low"
            message = (
                f"BDFL model: {percentage:.0f}% by founder/leader. "
                f"Mature project ({total_repo_commits} commits). Proven stability."
            )
        elif is_mature_project:
            # Mature project but recently single-heavy = concern
            score = 2  # 5/20 → 2/10
            risk = "High"
            message = (
                f"High: {percentage:.0f}% of recent commits by single author. "
                f"{num_contributors} contributor(s), {total_repo_commits} total commits."
            )
        else:
            # New project with founder-heavy commit = acceptable
            score = 5  # 10/20 → 5/10
            risk = "Medium"
            message = (
                f"New project: {percentage:.0f}% by single author. "
                f"Expected for early-stage projects."
            )
    elif percentage >= 70:
        score = 5  # 10/20 → 5/10
        risk = "High"
        message = (
            f"High: {percentage:.0f}% of commits by single author. "
            f"{num_contributors} contributor(s) total."
        )
    elif percentage >= 50:
        score = 8  # 15/20 → 8/10
        risk = "Medium"
        message = (
            f"Medium: {percentage:.0f}% by top contributor. "
            f"{num_contributors} contributor(s) total."
        )
    else:
        score = max_score
        risk = "None"
        message = f"Healthy: {num_contributors} active contributors."

    return Metric("Contributor Redundancy", score, max_score, message, risk)


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_bus_factor(repo_data)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Contributor Redundancy",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "High",
    )


METRIC = MetricSpec(
    name="Contributor Redundancy",
    checker=_check,
    on_error=_on_error,
    error_log="  [yellow]⚠️  Contributor redundancy check incomplete: {error}[/yellow]",
)
