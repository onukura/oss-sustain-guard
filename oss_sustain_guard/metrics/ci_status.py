"""CI status metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_ci_status(repo_data: dict[str, Any]) -> Metric:
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

    # Check if repository is archived
    is_archived = repo_data.get("isArchived", False)
    if is_archived:
        return Metric(
            "Build Health",
            max_score,
            max_score,
            "Repository archived (CI check skipped).",
            "None",
        )

    # Extract CI status from checkSuites
    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
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

    # Get the most recent check suite
    latest_suite = check_suites[0] if check_suites else None
    if not latest_suite or not isinstance(latest_suite, dict):
        return Metric(
            "Build Health",
            0,
            max_score,
            "No recent CI checks.",
            "High",
        )

    conclusion = latest_suite.get("conclusion") or ""
    status = latest_suite.get("status") or ""

    # Ensure we have strings before calling upper()
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
        message = f"CI Status: {conclusion.lower()} (Latest check failed)."
    elif conclusion in ("SKIPPED", "STALE"):
        # SKIPPED is not a failure - give partial credit
        score = 6  # 3/5 → 6/10
        risk = "Low"
        message = f"CI Status: {conclusion.lower()} (Check skipped but CI configured)."
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


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_ci_status(repo_data)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "CI/CD Status",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="Build Health",
    checker=_check,
    on_error=_on_error,
)
