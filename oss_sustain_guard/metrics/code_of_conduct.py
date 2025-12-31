"""Code of Conduct metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_code_of_conduct(repo_data: dict[str, Any]) -> Metric:
    """
    Checks for presence of a Code of Conduct.

    A Code of Conduct signals a welcoming, inclusive community.

    Scoring (0-10 scale):
    - GitHub recognized CoC: 10/10
    - No CoC: 0/10 (but low risk - informational)
    """
    max_score = 10

    code_of_conduct = repo_data.get("codeOfConduct")

    if code_of_conduct and code_of_conduct.get("name"):
        coc_name = code_of_conduct.get("name", "Unknown")
        score = max_score
        risk = "None"
        message = f"Excellent: Code of Conduct present ({coc_name})."
    else:
        score = 0
        risk = "Low"
        message = (
            "Note: No Code of Conduct detected. Consider adding one for inclusivity."
        )

    return Metric("Code of Conduct", score, max_score, message, risk)


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_code_of_conduct(repo_data)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Code of Conduct",
        0,
        5,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="Code of Conduct",
    checker=_check,
    on_error=_on_error,
)
