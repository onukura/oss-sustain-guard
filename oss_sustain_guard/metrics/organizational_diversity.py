"""Organizational diversity metric."""

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

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class OrganizationalDiversityChecker(MetricChecker):
    """Evaluate organizational diversity using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates Organizational Diversity (CHAOSS metric).

        Measures diversity of contributor affiliations based on:
        - Email domains (heuristic)
        - Company field from GitHub profiles

        A diverse contributor base reduces single-organization dependence.

        Scoring:
        - 5+ organizations: 10/10 (Highly diverse)
        - 3-4 organizations: 7/10 (Good diversity)
        - 2 organizations: 4/10 (Moderate)
        - Single organization: 0/10 (Single-org concentration)
        """
        max_score = 10

        commits = vcs_data.commits
        if not commits:
            if vcs_data.default_branch is None:
                return Metric(
                    "Organizational Diversity",
                    max_score // 2,
                    max_score,
                    "Note: Commit history data not available.",
                    "None",
                )
            return Metric(
                "Organizational Diversity",
                max_score // 2,
                max_score,
                "Note: No commit history for analysis.",
                "None",
            )

        # Bot patterns to exclude
        excluded_users = get_excluded_users()

        def extract_author_info(
            commit: dict[str, Any],
        ) -> tuple[str | None, str | None, str | None]:
            """Extract login, email, and name from a commit."""
            login = extract_login(commit)
            author = commit.get("author", {})
            email = author.get("email") if isinstance(author, dict) else None
            name = author.get("name") if isinstance(author, dict) else None
            return login, email, name

        # Collect organization signals
        organizations: set[str] = set()
        email_domains: set[str] = set()

        for commit in commits:
            author = commit.get("author")
            if not isinstance(author, dict):
                continue
            login, email, name = extract_author_info(commit)
            if login and is_bot(
                login, email=email, name=name, excluded_users=excluded_users
            ):
                continue
            user = author.get("user")
            if isinstance(user, dict):
                company = user.get("company")
                if company and len(company) > 1:
                    company_clean = company.strip().lower().replace("@", "")
                    if company_clean:
                        organizations.add(company_clean)

            email = author.get("email")
            if email and "@" in email:
                domain = email.split("@")[-1].lower()
                # Filter out common free email providers
                free_providers = {
                    "gmail.com",
                    "yahoo.com",
                    "hotmail.com",
                    "outlook.com",
                    "users.noreply.github.com",
                    "localhost",
                }
                if domain not in free_providers and "." in domain:
                    email_domains.add(domain)

        # Combine signals (prefer organizations, fall back to domains)
        total_orgs = len(organizations)
        total_domains = len(email_domains)
        diversity_score = max(total_orgs, total_domains)

        # Scoring logic
        if diversity_score >= 5:
            score = max_score
            risk = "None"
            message = (
                f"Excellent: {diversity_score} organizations/domains detected. "
                f"Highly diverse."
            )
        elif diversity_score >= 3:
            score = 7
            risk = "Low"
            message = f"Good: {diversity_score} organizations/domains detected. Good diversity."
        elif diversity_score >= 2:
            score = 4
            risk = "Medium"
            message = (
                f"Moderate: {diversity_score} organizations/domains detected. "
                f"Consider expanding."
            )
        elif diversity_score == 1:
            score = 2
            risk = "High"
            message = (
                "Observe: Single organization dominates. Reliance is concentrated."
            )
        else:
            score = max_score // 2
            risk = "None"
            message = (
                "Note: Unable to determine organizational diversity "
                "(personal project likely)."
            )

        return Metric("Organizational Diversity", score, max_score, message, risk)


_CHECKER = OrganizationalDiversityChecker()


def check_organizational_diversity(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Organizational Diversity",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="Organizational Diversity",
    checker=_CHECKER,
    on_error=_on_error,
)
