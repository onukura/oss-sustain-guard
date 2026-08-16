"""License clarity metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class LicenseClarityChecker(MetricChecker):
    """Evaluate license clarity using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates license clarity and OSI approval status.

        A clear, OSI-approved license is essential for:
        - Legal clarity
        - Enterprise adoption
        - Community trust

        Scoring:
        - OSI-approved license (MIT, Apache, GPL, etc.): 5/5
        - Other recognized license: 3/5
        - No license detected: 0/5 (Unclear usage terms)
        """
        max_score = 10

        license_info = vcs_data.license_info

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
            message = f"Good: {license_name} detected. Verify compatibility for your use case."
        else:
            score = 4
            risk = "Medium"
            message = f"Note: {license_name} detected but not recognized. Review license terms."

        return Metric("License Clarity", score, max_score, message, risk)


_CHECKER = LicenseClarityChecker()


def check_license_clarity(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "License Clarity",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="License Clarity",
    checker=_CHECKER,
    on_error=_on_error,
)
