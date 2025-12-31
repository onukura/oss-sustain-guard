"""Documentation presence metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_documentation_presence(repo_data: dict[str, Any]) -> Metric:
    """
    Checks for presence of essential documentation files.

    Evaluates:
    - README.md existence and size
    - CONTRIBUTING.md existence
    - Wiki enabled
    - Homepage/documentation link
    - Description presence

    Scoring:
    - All docs present: 10/10
    - README + some docs: 7/10
    - Only README: 4/10
    - No documentation: 0/10
    """
    max_score = 10

    # Check README (multiple patterns for case sensitivity)
    readme_upper = repo_data.get("readmeUpperCase")  # README.md
    readme_lower = repo_data.get("readmeLowerCase")  # readme.md
    readme_all_caps = repo_data.get("readmeAllCaps")  # README

    # Use whichever README pattern exists
    readme = readme_upper or readme_lower or readme_all_caps

    # Check if README exists and handle symlinks
    has_readme = False
    if readme is not None:
        byte_size = readme.get("byteSize", 0)
        # If byte_size is small (< 100), it might be a symlink - check text content
        if byte_size > 100:
            has_readme = True
        elif byte_size > 0:
            # Small file - might be a symlink, check if text looks like a path
            text = readme.get("text", "")
            if text and "/" in text and not text.startswith("#"):
                # Looks like a symlink path (e.g., "packages/next/README.md")
                # In this case, consider README as present since GitHub resolves it
                has_readme = True
            elif text and len(text.strip()) >= 10:
                # Small but valid README content
                has_readme = True

    # Check CONTRIBUTING.md
    contributing = repo_data.get("contributingFile")
    has_contributing = contributing is not None

    # Check Wiki
    has_wiki = repo_data.get("hasWikiEnabled", False)

    # Check Homepage URL
    homepage = repo_data.get("homepageUrl")
    has_homepage = bool(homepage and len(homepage) > 5)

    # Check Description
    description = repo_data.get("description")
    has_description = bool(description and len(description) > 10)

    # Count documentation signals
    doc_signals = sum(
        [has_readme, has_contributing, has_wiki, has_homepage, has_description]
    )

    # Scoring logic
    if doc_signals >= 4:
        score = max_score
        risk = "None"
        message = f"Excellent: {doc_signals}/5 documentation signals present."
    elif doc_signals >= 3:
        score = 7
        risk = "Low"
        message = f"Good: {doc_signals}/5 documentation signals present."
    elif has_readme and doc_signals >= 2:
        score = 5
        risk = "Low"
        message = (
            f"Moderate: README present with {doc_signals}/5 documentation signals."
        )
    elif has_readme:
        score = 4
        risk = "Medium"
        message = "Basic: Only README detected. Consider adding CONTRIBUTING.md."
    else:
        score = 0
        risk = "High"
        message = "Observe: No README or documentation found. Add documentation to help contributors."

    return Metric("Documentation Presence", score, max_score, message, risk)


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_documentation_presence(repo_data)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Documentation Presence",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="Documentation Presence",
    checker=_check,
    on_error=_on_error,
)
