"""License clarity metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_license_clarity(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates license clarity and OSI approval status.

    A clear, OSI-approved license is essential for:
    - Legal clarity
    - Enterprise adoption
    - Community trust

    Scoring:
    - OSI-approved license (MIT, Apache, GPL, etc.): 5/5
    - Other recognized license: 3/5
    - No license detected: 0/5 (High risk for users)
    """
    max_score = 10

    license_info = repo_data.get("licenseInfo")

    if not license_info:
        return Metric(
            "License Clarity",
            0,
            max_score,
            "Attention: No license detected. Add a license for legal clarity.",
            "High",
        )

    license_name = license_info.get("name", "Unknown")
    spdx_id = license_info.get("spdxId")

    # Common OSI-approved licenses
    osi_approved = {
        "MIT",
        "Apache-2.0",
        "GPL-2.0",
        "GPL-3.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "MPL-2.0",
        "LGPL-2.1",
        "LGPL-3.0",
        "EPL-2.0",
        "AGPL-3.0",
        "Unlicense",
        "CC0-1.0",
    }

    if spdx_id and spdx_id in osi_approved:
        score = max_score
        risk = "None"
        message = f"Excellent: {license_name} (OSI-approved). Clear licensing."
    elif spdx_id:
        score = 6
        risk = "Low"
        message = (
            f"Good: {license_name} detected. Verify compatibility for your use case."
        )
    else:
        score = 4
        risk = "Medium"
        message = (
            f"Note: {license_name} detected but not recognized. Review license terms."
        )

    return Metric("License Clarity", score, max_score, message, risk)


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_license_clarity(repo_data)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "License Clarity",
        0,
        5,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="License Clarity",
    checker=_check,
    on_error=_on_error,
)
