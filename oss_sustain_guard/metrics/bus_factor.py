"""Contributor redundancy metric."""

from typing import Any

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class ContributorRedundancyChecker(MetricChecker):
    """Evaluate contributor redundancy with VCS-agnostic data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Analyzes the 'Bus Factor' of a repository with improved logic.

        Considers:
        - Top contributor percentage (recent commits)
        - Project maturity (total commits)
        - Contributor diversity trend

        Status levels:
        - 90%+ single author: 20pt reduction (but not critical for new projects)
        - 70-89%: 10pt reduction
        - 50-69%: 5pt reduction
        - <50%: 0pt reduction (healthy)

        Note: All metrics are now scored on a 0-10 scale for consistency.
        """
        max_score = 10

        commits = vcs_data.commits
        if not commits:
            if vcs_data.default_branch is None:
                return Metric(
                    "Contributor Redundancy",
                    0,
                    max_score,
                    "Note: Commit history data not available.",
                    "High",
                )
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

        # Count commits per author (excluding bots)
        author_counts: dict[str, int] = {}
        for commit in commits:
            login = extract_login(commit)
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
        total_repo_commits = (
            vcs_data.total_commits if vcs_data.total_commits > 0 else len(commits)
        )

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
                    f"Needs attention: {percentage:.0f}% of recent commits by single author. "
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
                f"Needs attention: {percentage:.0f}% of commits by single author. "
                f"{num_contributors} contributor(s) total."
            )
        elif percentage >= 50:
            score = 8  # 15/20 → 8/10
            risk = "Medium"
            message = (
                f"Monitor: {percentage:.0f}% by top contributor. "
                f"{num_contributors} contributor(s) total."
            )
        else:
            score = max_score
            risk = "None"
            message = f"Healthy: {num_contributors} active contributors."

        return Metric("Contributor Redundancy", score, max_score, message, risk)


_CHECKER = ContributorRedundancyChecker()


def check_bus_factor(repo_data: dict[str, Any] | VCSRepositoryData) -> Metric:
    if isinstance(repo_data, VCSRepositoryData):
        return _CHECKER.check(repo_data, _LEGACY_CONTEXT)
    return _CHECKER.check_legacy(repo_data, _LEGACY_CONTEXT)


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
    checker=_CHECKER,
    on_error=_on_error,
    error_log="  [yellow]⚠️  Contributor redundancy check incomplete: {error}[/yellow]",
)
