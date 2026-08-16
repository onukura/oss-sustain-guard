"""CI status metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class CiStatusChecker(MetricChecker):
    """Evaluate CI status using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Verifies the status of recent CI builds by checking checkSuites.

        Note: CI Status is now a reference metric with reduced weight.

        Scoring (0-10 scale):
        - SUCCESS or NEUTRAL: 10/10 (CI passing)
        - FAILURE: 0/10 (CI issues detected)
        - IN_PROGRESS/QUEUED: 6/10 (Not yet completed)
        - No CI data: 0/10 (No CI configuration detected)
        """
        max_score = 10

        if vcs_data.is_archived:
            return Metric(
                "Build Health",
                max_score,
                max_score,
                "Repository archived (CI check skipped).",
                "None",
            )

        conclusion = ""
        status = ""
        ci_status = vcs_data.ci_status
        if ci_status is None and vcs_data.raw_data is None:
            return Metric(
                "Build Health",
                0,
                max_score,
                "Note: CI status data not available.",
                "High",
            )

        if ci_status is None:
            raw_data = vcs_data.raw_data or {}
            default_branch = raw_data.get("defaultBranchRef")
            if not default_branch or vcs_data.default_branch is None:
                return Metric(
                    "Build Health",
                    0,
                    max_score,
                    "Note: CI status data not available.",
                    "High",
                )

            target = default_branch.get("target")
            if target is None:
                return Metric(
                    "Build Health",
                    0,
                    max_score,
                    "Note: CI status data not available.",
                    "High",
                )

            check_suites_data = target.get("checkSuites")
            if not check_suites_data:
                return Metric(
                    "Build Health",
                    0,
                    max_score,
                    "No CI configuration detected.",
                    "High",
                )

            check_suites = check_suites_data.get("nodes", [])
            if not check_suites:
                return Metric(
                    "Build Health",
                    0,
                    max_score,
                    "No recent CI checks.",
                    "High",
                )

            latest_suite = check_suites[0] if check_suites else None
            if not isinstance(latest_suite, dict):
                return Metric(
                    "Build Health",
                    0,
                    max_score,
                    "No recent CI checks.",
                    "High",
                )

            conclusion = latest_suite.get("conclusion") or ""
            status = latest_suite.get("status") or ""
        else:
            if isinstance(ci_status, dict):
                conclusion = ci_status.get("conclusion") or ""
                status = ci_status.get("status") or ""

        if not isinstance(conclusion, str):
            conclusion = ""
        if not isinstance(status, str):
            status = ""

        conclusion = conclusion.upper()
        status = status.upper()

        # Scoring logic based on CI conclusion (0-10 scale)
        if conclusion in ("SUCCESS", "NEUTRAL"):
            score = max_score
            risk = "None"
            message = f"CI Status: {conclusion.lower()} (Latest check passed)."
        elif conclusion in ("FAILURE", "TIMED_OUT"):
            score = 0
            risk = "Medium"  # Downgraded from Critical
            message = f"CI Status: {conclusion.lower()} (Latest check did not pass)."
        elif conclusion in ("SKIPPED", "STALE"):
            # SKIPPED is not a failure - give partial credit
            score = 6  # 3/5 → 6/10
            risk = "Low"
            message = (
                f"CI Status: {conclusion.lower()} (Check skipped but CI configured)."
            )
        elif status == "IN_PROGRESS":
            score = 6  # 3/5 → 6/10
            risk = "Low"
            message = "CI Status: Tests in progress (not yet complete)."
        elif status == "QUEUED":
            score = 6  # 3/5 → 6/10
            risk = "Low"
            message = "CI Status: Tests queued."
        elif conclusion == "" and status == "":
            # CI exists but no conclusion yet - give partial credit
            score = 6  # 3/5 → 6/10
            risk = "Low"
            message = "CI Status: Configured (no recent runs detected)."
        else:
            # Unknown status - still give some credit if CI exists
            score = 4  # 2/5 → 4/10
            risk = "Low"
            message = f"CI Status: Unknown ({conclusion or status or 'no data'})."

        return Metric("Build Health", score, max_score, message, risk)


_CHECKER = CiStatusChecker()


def check_ci_status(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Build Health",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="Build Health",
    checker=_CHECKER,
    on_error=_on_error,
)
