"""Documentation presence metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class DocumentationPresenceChecker(MetricChecker):
    """Evaluate documentation signals using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
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

        readme_size = vcs_data.readme_size
        readme_text = None
        raw_data = vcs_data.raw_data or {}

        if raw_data:
            for candidate_key in (
                "readmeUpperCase",
                "readmeLowerCase",
                "readmeAllCaps",
            ):
                candidate = raw_data.get(candidate_key)
                if not isinstance(candidate, dict):
                    continue
                if readme_size is None:
                    candidate_size = candidate.get("byteSize")
                    if isinstance(candidate_size, int):
                        readme_size = candidate_size
                if readme_text is None:
                    text = candidate.get("text")
                    if isinstance(text, str):
                        readme_text = text
                if readme_size is not None and readme_text is not None:
                    break

        # Check if README exists and handle symlinks
        has_readme = False
        if readme_size is not None:
            # If byte_size is small (< 100), it might be a symlink - check text content
            if readme_size > 100:
                has_readme = True
            elif readme_size > 0:
                if readme_text:
                    # Small file - might be a symlink, check if text looks like a path
                    if "/" in readme_text and not readme_text.startswith("#"):
                        # Looks like a symlink path (e.g., "packages/next/README.md")
                        # In this case, consider README as present since GitHub resolves it
                        has_readme = True
                    elif len(readme_text.strip()) >= 10:
                        # Small but valid README content
                        has_readme = True
                elif vcs_data.raw_data is None:
                    has_readme = True
        elif readme_text and len(readme_text.strip()) >= 10:
            has_readme = True

        # Check CONTRIBUTING.md
        contributing_size = vcs_data.contributing_file_size
        has_contributing = contributing_size is not None
        if not has_contributing and raw_data:
            contributing = raw_data.get("contributingFile")
            if isinstance(contributing, dict):
                has_contributing = True

        # Check Wiki
        has_wiki = vcs_data.has_wiki

        # Check Homepage URL
        homepage = vcs_data.homepage_url
        has_homepage = bool(homepage and len(homepage) > 5)

        # Check Description
        description = vcs_data.description
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


_CHECKER = DocumentationPresenceChecker()


def check_documentation_presence(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


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
    checker=_CHECKER,
    on_error=_on_error,
)
