"""Fork activity metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class ForkActivityChecker(MetricChecker):
    """Evaluate fork activity using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates active fork development as a signal of ecosystem health and fork divergence.

        Considers:
        - Total fork count
        - Active forks with recent commits (last 6 months)
        - Fork divergence (high active fork ratio)

        Active forking indicates:
        - Community interest and adoption
        - Potential future contributors
        - Fork/divergence pressure if too many active forks

        Scoring:
        - Low active fork ratio (<20%) with high total forks: 5/5 (Healthy ecosystem)
        - Moderate active fork ratio (20-40%): 3-4/5 (Monitor divergence)
        - High active fork ratio (>40%): 1-2/5 (Needs attention - divergence signal)
        - Few forks but some active: 2-3/5 (Growing)
        - No forks: 0/5 (New/niche)
        """
        from datetime import datetime, timedelta, timezone

        max_score = 10

        fork_count = vcs_data.total_forks
        forks = vcs_data.forks

        # No forks - new or niche project
        if fork_count == 0:
            return Metric(
                "Fork Activity",
                0,
                max_score,
                "Note: No forks yet. Project may be new or niche.",
                "Low",
            )

        # Analyze active development in forks (last 6 months)
        now = datetime.now(timezone.utc)
        six_months_ago = now - timedelta(days=180)
        active_fork_count = 0
        recently_created_forks = 0
        three_months_ago = now - timedelta(days=90)

        for node in forks:
            # Check fork creation date
            created_at_str = node.get("createdAt")
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                    if created_at >= three_months_ago:
                        recently_created_forks += 1
                except (ValueError, AttributeError):
                    pass

            # Check for active development (recent commits)
            pushed_at_str = node.get("pushedAt")
            if pushed_at_str:
                try:
                    pushed_at = datetime.fromisoformat(
                        pushed_at_str.replace("Z", "+00:00")
                    )
                    if pushed_at >= six_months_ago:
                        # Verify with commit date if available
                        default_branch = node.get("defaultBranchRef")
                        if default_branch:
                            target = default_branch.get("target", {})
                            history = target.get("history", {}).get("edges", [])
                            if history:
                                last_commit = history[0].get("node", {})
                                committed_date_str = last_commit.get(
                                    "committedDate"
                                ) or last_commit.get("authoredDate")
                                if committed_date_str:
                                    committed_date = datetime.fromisoformat(
                                        committed_date_str.replace("Z", "+00:00")
                                    )
                                    if committed_date >= six_months_ago:
                                        active_fork_count += 1
                                        continue
                        # Fallback: use push date if commit history unavailable
                        active_fork_count += 1
                except (ValueError, AttributeError, TypeError):
                    pass

        # Calculate active fork ratio (only for sample, approximate for total)
        # Note: We only fetch top 20 forks, so this is an approximation
        sample_size = len(forks)
        active_fork_ratio = (
            (active_fork_count / sample_size * 100) if sample_size > 0 else 0
        )

        # Scoring logic based on fork patterns (0-10 scale)
        if fork_count >= 100:
            # Large ecosystem - assess health and divergence
            if active_fork_ratio < 20:
                score = max_score  # 5/5 → 10/10
                risk = "None"
                message = f"Excellent: {fork_count} forks, ~{active_fork_count}/{sample_size} active. Healthy ecosystem with low divergence."
            elif active_fork_ratio < 40:
                score = 6  # 3/5 → 6/10
                risk = "Low"
                message = f"Monitor: {fork_count} forks, ~{active_fork_count}/{sample_size} active. Consider community alignment efforts."
            else:
                score = 2  # 1/5 → 2/10, high divergence signal
                risk = "Medium"
                message = f"Needs attention: {fork_count} forks, ~{active_fork_count}/{sample_size} active. Fork divergence appears elevated."
        elif fork_count >= 50:
            # Medium ecosystem
            if active_fork_ratio < 30:
                score = 8  # 4/5 → 8/10
                risk = "None"
                message = f"Good: {fork_count} forks, ~{active_fork_count}/{sample_size} active. Growing ecosystem."
            else:
                score = 4  # 2/5 → 4/10
                risk = "Low"
                message = f"Monitor: {fork_count} forks, ~{active_fork_count}/{sample_size} active. Watch for divergence."
        elif fork_count >= 10:
            # Smaller ecosystem
            if active_fork_count >= 2:
                score = 6  # 3/5 → 6/10
                risk = "None"
                message = f"Moderate: {fork_count} forks, {active_fork_count} active. Growing community interest."
            else:
                score = 4  # 2/5 → 4/10
                risk = "None"
                message = f"Early: {fork_count} forks, {active_fork_count} active. Small community."
        else:
            # Very small ecosystem
            if active_fork_count > 0:
                score = 4  # 2/5 → 4/10
                risk = "Low"
                message = f"Early: {fork_count} fork(s), {active_fork_count} active. Emerging interest."
            else:
                score = 2  # 1/5 → 2/10
                risk = "Low"
                message = f"Limited: {fork_count} fork(s), no recent activity detected."

        return Metric("Fork Activity", score, max_score, message, risk)


_CHECKER = ForkActivityChecker()


def check_fork_activity(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Fork Activity",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="Fork Activity",
    checker=_CHECKER,
    on_error=_on_error,
)
