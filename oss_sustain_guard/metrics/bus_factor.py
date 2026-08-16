"""Contributor redundancy metric."""

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


class ContributorRedundancyChecker(MetricChecker):
    """Evaluate contributor redundancy with VCS-agnostic data.

    IMPORTANT: This is an ESTIMATE based on public commit history only.
    Limitations include:
    - Cannot detect internal Git mirrors or private repositories
    - Ignores non-code contributions (docs, triage, community management)
    - No visibility into organizational knowledge transfer or succession plans
    - May not reflect full-time maintainer status or corporate backing

    Use this metric as a signal to investigate further, not as a definitive verdict.
    """

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Analyzes estimated 'Bus Factor' from public commit history.

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
        Note: This is an estimate; actual project redundancy may differ.
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

        # Count commits per author (excluding bots)
        author_counts: dict[str, int] = {}
        for commit in commits:
            login, email, name = extract_author_info(commit)
            if login and not is_bot(
                login, email=email, name=name, excluded_users=excluded_users
            ):
                author_counts[login] = author_counts.get(login, 0) + 1

        # Enhance with PR mergers data (who merges PRs might be different from who commits)
        # This helps identify maintainers who triage/review but don't commit directly
        if hasattr(vcs_data, "merged_prs") and vcs_data.merged_prs:
            for pr in vcs_data.merged_prs:
                merged_by = pr.get("mergedBy")
                if isinstance(merged_by, dict):
                    login = merged_by.get("login")
                    if login and not is_bot(
                        login, email=None, name=None, excluded_users=excluded_users
                    ):
                        # Weight merges same as commits for now to simply count active maintainers
                        # A better approach might be weighted (e.g., 1 merge = 1 contribution)
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
        # Note: All messages include "Estimated from public contributions" to be transparent about limitations
        if percentage >= 90:
            # Very high single-author concentration
            if is_mature_bdfl:
                # Mature BDFL model = proven track record
                score = 8  # 15/20 → 8/10
                risk = "Low"
                message = (
                    f"Estimated from public contributions: {percentage:.0f}% by founder/leader. "
                    f"Mature project ({total_repo_commits} commits). May have internal redundancy."
                )
            elif is_mature_project:
                # Mature project but recently single-heavy = concern
                score = 2  # 5/20 → 2/10
                risk = "High"
                message = (
                    f"Estimated from public contributions: {percentage:.0f}% by single author. "
                    f"{num_contributors} contributor(s), {total_repo_commits} total commits. "
                    f"Consider investigating project's internal structure."
                )
            else:
                # New project with founder-heavy commit = acceptable
                score = 5  # 10/20 → 5/10
                risk = "Medium"
                message = (
                    f"Estimated from public contributions: {percentage:.0f}% by single author. "
                    f"Expected for early-stage projects."
                )
        elif percentage >= 70:
            score = 5  # 10/20 → 5/10
            risk = "High"
            message = (
                f"Estimated from public contributions: {percentage:.0f}% by single author. "
                f"{num_contributors} contributor(s) total. Review project governance."
            )
        elif percentage >= 50:
            score = 8  # 15/20 → 8/10
            risk = "Medium"
            message = (
                f"Estimated from public contributions: {percentage:.0f}% by top contributor. "
                f"{num_contributors} contributor(s) total."
            )
        else:
            score = max_score
            risk = "None"
            message = (
                f"Estimated from public contributions: Healthy diversity with "
                f"{num_contributors} active contributors."
            )

        return Metric("Contributor Redundancy", score, max_score, message, risk)


_CHECKER = ContributorRedundancyChecker()


def check_bus_factor(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


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
