"""Code of Conduct metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class CodeOfConductChecker(MetricChecker):
    """Evaluate Code of Conduct presence using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Checks for presence of a Code of Conduct.

        A Code of Conduct signals a welcoming, inclusive community.

        Scoring (0-10 scale):
        - GitHub recognized CoC: 10/10
        - No CoC: 0/10 (informational)
        """
        max_score = 10

        code_of_conduct = vcs_data.code_of_conduct

        if code_of_conduct and code_of_conduct.get("name"):
            coc_name = code_of_conduct.get("name", "Unknown")
            score = max_score
            risk = "None"
            message = f"Excellent: Code of Conduct present ({coc_name})."
        else:
            score = 0
            risk = "Low"
            message = "Note: No Code of Conduct detected. Consider adding one for inclusivity."

        return Metric("Code of Conduct", score, max_score, message, risk)


_CHECKER = CodeOfConductChecker()


def check_code_of_conduct(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Code of Conduct",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="Code of Conduct",
    checker=_CHECKER,
    on_error=_on_error,
)
