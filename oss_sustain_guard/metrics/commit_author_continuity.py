"""Commit author continuity metric.

Published as "Maintainer Retention" (a.k.a. "Maintainer Drain") until v0.26.0.
Renamed and reworked in response to issue #11: the old implementation compared
the distinct author count of the last 25 commits against the previous 25, with
no notion of elapsed time. A dormant project whose 50-commit sample spanned
years therefore scored as "Stable: N active maintainers", and because a departing
lead maintainer's commits vanish from the recent slice, the surviving drive-by
contributors could push the ratio *up* — the signal was inverted for exactly the
situation it was meant to detect.

This version:
- compares fixed calendar windows instead of commit slices,
- penalizes the absence of any maintainer activity in the recent window,
- tracks the continuity of principal committers rather than a head count,
- accepts PR merges as maintainer activity, since merge rights imply write access.

The signal is still derived from public commit and merge history, so it is a
proxy for maintainer activity, not evidence of formal maintainer status.
"""

from datetime import datetime, timedelta, timezone
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

METRIC_NAME = "Commit Author Continuity"

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")

# Calendar windows, counted back from now.
RECENT_WINDOW_DAYS = 180
PREVIOUS_WINDOW_DAYS = 180

# Below this, the previous window is too thin to say who was carrying the project.
MIN_PREVIOUS_COMMITS = 5

# Principal committers are the fewest top authors that together account for this
# share of the previous window's human commits (bus-factor style core team).
PRINCIPAL_COMMIT_SHARE = 0.5

# Losing every principal committer while commit volume holds up at this ratio
# reads as a handover, not a drain.
HANDOVER_VOLUME_RATIO = 0.5

# Idle longer than this and the loss of maintainers is no longer recoverable-looking.
ABANDONED_AFTER_DAYS = 365


def _parse_date(value: Any) -> datetime | None:
    """Parse an ISO timestamp, tolerating the trailing 'Z' GitHub returns."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _commit_date(commit: dict[str, Any]) -> datetime | None:
    """Extract a commit timestamp (GitHub uses authoredDate, GitLab committedDate)."""
    return _parse_date(commit.get("authoredDate")) or _parse_date(
        commit.get("committedDate")
    )


def _build_identity_map(commits: list[dict[str, Any]]) -> dict[str, str]:
    """Map email-derived identities onto the platform login of the same person.

    extract_login() falls back to the author email for commits with no linked
    account, so one person can otherwise be counted twice — once as a login and
    once as an email — which splits their commit share.
    """
    email_to_login: dict[str, str] = {}
    for commit in commits:
        author = commit.get("author")
        if not isinstance(author, dict):
            continue
        user = author.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        email = author.get("email")
        if login and email:
            email_to_login.setdefault(email, login)
    return email_to_login


def _human_author(
    commit: dict[str, Any],
    identity_map: dict[str, str],
    excluded_users: list[str] | None,
) -> str | None:
    """Return the canonical identifier of a commit's human author, or None."""
    login = extract_login(commit)
    if not login:
        return None
    author = commit.get("author")
    if not isinstance(author, dict):
        author = {}
    if is_bot(
        login,
        email=author.get("email"),
        name=author.get("name"),
        excluded_users=excluded_users,
    ):
        return None
    return identity_map.get(login, login)


def _principal_committers(counts: dict[str, int], total_commits: int) -> list[str]:
    """Fewest top authors covering more than PRINCIPAL_COMMIT_SHARE of a window.

    The comparison is strict so that co-leads with an even split are both
    counted, rather than the tie being broken arbitrarily.
    """
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    threshold = total_commits * PRINCIPAL_COMMIT_SHARE
    principal: list[str] = []
    cumulative = 0
    for login, count in ranked:
        principal.append(login)
        cumulative += count
        if cumulative > threshold:
            break
    return principal


class CommitAuthorContinuityChecker(MetricChecker):
    """Check whether the people carrying a project are still carrying it.

    IMPORTANT: This is an ESTIMATE based on public commit and merge history.
    Limitations include:
    - Commit authorship is a proxy for maintainer activity, not a role check
    - Maintainers who only triage, review, or answer issues are invisible here
    - Release managers working from mirrors or private forks are not visible
    - The commit sample is capped, so long-lived projects are seen only partially

    Use this metric as a signal to investigate further, not as a definitive verdict.
    """

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Compares maintainer activity across two 180-day windows.

        Status levels:
        - No maintainer activity for 1+ year: 0/10 (Critical)
        - No maintainer activity in the recent window: 3/10 (High)
        - No principal committer retained, volume collapsed: 0/10 (Critical)
        - No principal committer retained, volume held up: 5/10 (Medium, handover)
        - Under 50% retained: 4/10 (Medium)
        - 50-79% retained: 7/10 (Low)
        - 80%+ retained: 10/10 (None)

        Insufficient history yields the full score, matching the other metrics:
        an unobservable project is not the same as an unhealthy one.
        """
        max_score = 10

        commits = vcs_data.commits
        if not commits:
            if vcs_data.default_branch is None:
                return Metric(
                    METRIC_NAME,
                    max_score,
                    max_score,
                    "Note: Commit history not available for verification.",
                    "None",
                )
            return Metric(
                METRIC_NAME,
                max_score,
                max_score,
                "No commit history available for analysis.",
                "None",
            )

        now = datetime.now(timezone.utc)
        recent_start = now - timedelta(days=RECENT_WINDOW_DAYS)
        previous_start = recent_start - timedelta(days=PREVIOUS_WINDOW_DAYS)

        excluded_users = get_excluded_users()
        identity_map = _build_identity_map(commits)

        recent_authors: set[str] = set()
        previous_counts: dict[str, int] = {}
        recent_commits = 0
        previous_commits = 0
        oldest_sampled: datetime | None = None
        last_activity: datetime | None = None

        for commit in commits:
            committed_at = _commit_date(commit)
            if committed_at is None:
                continue
            if oldest_sampled is None or committed_at < oldest_sampled:
                oldest_sampled = committed_at

            author = _human_author(commit, identity_map, excluded_users)
            if author is None or committed_at > now:
                continue
            if last_activity is None or committed_at > last_activity:
                last_activity = committed_at

            if committed_at >= recent_start:
                recent_authors.add(author)
                recent_commits += 1
            elif committed_at >= previous_start:
                previous_counts[author] = previous_counts.get(author, 0) + 1
                previous_commits += 1

        # Merging a PR requires write access, so mergers count as maintainer
        # activity even when they stop authoring commits themselves.
        recent_mergers: set[str] = set()
        for pull_request in vcs_data.merged_prs or []:
            merged_by = pull_request.get("mergedBy")
            login = merged_by.get("login") if isinstance(merged_by, dict) else None
            if not login or is_bot(login, excluded_users=excluded_users):
                continue
            merged_at = _parse_date(pull_request.get("mergedAt"))
            if merged_at is None or merged_at > now:
                continue
            if last_activity is None or merged_at > last_activity:
                last_activity = merged_at
            if merged_at >= recent_start:
                recent_mergers.add(identity_map.get(login, login))

        recent_maintainers = recent_authors | recent_mergers
        recent_label = f"{recent_start:%Y-%m-%d} to {now:%Y-%m-%d}"
        previous_label = f"{previous_start:%Y-%m-%d} to {recent_start:%Y-%m-%d}"

        if last_activity is None:
            return Metric(
                METRIC_NAME,
                max_score,
                max_score,
                "Note: Commit timestamps not available for verification.",
                "None",
            )

        if not recent_maintainers:
            days_idle = (now - last_activity).days
            metadata = {
                "days_since_last_activity": days_idle,
                "last_activity": last_activity.date().isoformat(),
                "recent_window": recent_label,
            }
            if days_idle >= ABANDONED_AFTER_DAYS:
                return Metric(
                    METRIC_NAME,
                    0,
                    max_score,
                    f"Needs support: no human commit or merge for {days_idle} days "
                    f"(last activity {last_activity:%Y-%m-%d}).",
                    "Critical",
                    metadata,
                )
            return Metric(
                METRIC_NAME,
                3,
                max_score,
                f"Needs attention: no human commit or merge in {recent_label} "
                f"(last activity {last_activity:%Y-%m-%d}, {days_idle} days ago).",
                "High",
                metadata,
            )

        if previous_commits < MIN_PREVIOUS_COMMITS:
            metadata = {
                "recent_maintainers": len(recent_maintainers),
                "recent_commits": recent_commits,
                "previous_commits": previous_commits,
                "recent_window": recent_label,
            }
            # An author cap of 100 commits means a busy project's sample can end
            # well inside the comparison window; that is a blind spot, not a drain.
            if oldest_sampled is not None and oldest_sampled > previous_start:
                return Metric(
                    METRIC_NAME,
                    max_score,
                    max_score,
                    f"Active: {len(recent_maintainers)} human maintainer(s) in "
                    f"{recent_label}. Commit sample starts "
                    f"{oldest_sampled:%Y-%m-%d}, so continuity against "
                    f"{previous_label} could not be assessed.",
                    "None",
                    metadata,
                )
            return Metric(
                METRIC_NAME,
                max_score,
                max_score,
                f"Active: {len(recent_maintainers)} human maintainer(s) in "
                f"{recent_label}. Too little activity in {previous_label} "
                f"({previous_commits} commit(s)) to assess continuity.",
                "None",
                metadata,
            )

        principal = _principal_committers(previous_counts, previous_commits)
        retained = sorted(set(principal) & recent_maintainers)
        continuity = len(retained) / len(principal)

        metadata = {
            "continuity_rate": int(round(continuity * 100)),
            "principal_committers": len(principal),
            "retained_committers": len(retained),
            "recent_maintainers": len(recent_maintainers),
            "recent_commits": recent_commits,
            "previous_commits": previous_commits,
            "recent_window": recent_label,
            "previous_window": previous_label,
        }
        retention_label = (
            f"{len(retained)}/{len(principal)} principal committer(s) from "
            f"{previous_label}"
        )

        if continuity >= 0.8:
            score = max_score
            risk = "None"
            message = (
                f"Stable: {retention_label} are still active in {recent_label}. "
                f"Estimated from public commit and merge history."
            )
        elif continuity >= 0.5:
            score = 7
            risk = "Low"
            message = (
                f"Monitor: only {retention_label} remain active in {recent_label}."
            )
        elif continuity > 0:
            score = 4
            risk = "Medium"
            message = (
                f"Needs attention: only {retention_label} remain active in "
                f"{recent_label}."
            )
        elif recent_commits >= previous_commits * HANDOVER_VOLUME_RATIO:
            score = 5
            risk = "Medium"
            message = (
                f"Handover: none of the {len(principal)} principal committer(s) from "
                f"{previous_label} remain, but commit volume held up "
                f"({previous_commits} → {recent_commits}). "
                f"New maintainers may have taken over."
            )
        else:
            score = 0
            risk = "Critical"
            message = (
                f"Needs support: none of the {len(principal)} principal committer(s) "
                f"from {previous_label} are active in {recent_label}, and commit "
                f"volume fell from {previous_commits} to {recent_commits}."
            )

        return Metric(METRIC_NAME, score, max_score, message, risk, metadata)


_CHECKER = CommitAuthorContinuityChecker()


def check_commit_author_continuity(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        METRIC_NAME,
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "High",
    )


METRIC = MetricSpec(
    name=METRIC_NAME,
    checker=_CHECKER,
    on_error=_on_error,
    error_log="  [yellow]⚠️  Commit author continuity check incomplete: {error}[/yellow]",
)
