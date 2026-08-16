"""Deprecated alias for the commit author continuity metric.

The "Maintainer Retention" metric was renamed to "Commit Author Continuity" in
v0.26.0 (issue #11). This module keeps the old import path working for plugins,
stale entry-point metadata, and downstream code.
"""

from oss_sustain_guard.metrics.base import Metric
from oss_sustain_guard.metrics.commit_author_continuity import (
    METRIC,
    CommitAuthorContinuityChecker,
    check_commit_author_continuity,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

# Historical names, kept so existing imports resolve.
MaintainerRetentionChecker = CommitAuthorContinuityChecker


def check_maintainer_drain(repo_data: VCSRepositoryData) -> Metric:
    """Deprecated: use check_commit_author_continuity()."""
    return check_commit_author_continuity(repo_data)


__all__ = [
    "METRIC",
    "MaintainerRetentionChecker",
    "check_maintainer_drain",
]
