"""Organizational diversity metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_organizational_diversity(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates Organizational Diversity (CHAOSS metric).

    Measures diversity of contributor affiliations based on:
    - Email domains (heuristic)
    - Company field from GitHub profiles

    A diverse contributor base reduces single-organization dependency risk.

    Scoring:
    - 5+ organizations: 10/10 (Highly diverse)
    - 3-4 organizations: 7/10 (Good diversity)
    - 2 organizations: 4/10 (Moderate)
    - Single organization: 0/10 (Single-org risk)
    """
    max_score = 10

    default_branch = repo_data.get("defaultBranchRef")
    if not default_branch:
        return Metric(
            "Organizational Diversity",
            max_score // 2,
            max_score,
            "Note: Commit history data not available.",
            "None",
        )

    target = default_branch.get("target")
    if not target:
        return Metric(
            "Organizational Diversity",
            max_score // 2,
            max_score,
            "Note: Commit history data not available.",
            "None",
        )

    history = target.get("history", {}).get("edges", [])
    if not history:
        return Metric(
            "Organizational Diversity",
            max_score // 2,
            max_score,
            "Note: No commit history for analysis.",
            "None",
        )

    # Bot patterns to exclude (same as check_bus_factor)
    bot_keywords = [
        "bot",
        "action",
        "dependabot",
        "renovate",
        "github-actions",
        "ci-",
        "autorelease",
        "release-bot",
        "copilot",
        "actions-user",
    ]

    def is_bot(login: str) -> bool:
        """Check if login appears to be a bot."""
        lower = login.lower()
        return any(keyword in lower for keyword in bot_keywords)

    # Collect organization signals
    organizations: set[str] = set()
    email_domains: set[str] = set()

    for edge in history:
        node = edge.get("node", {})
        author = node.get("author", {})

        # Check company field
        user = author.get("user")
        if user:
            login = user.get("login")
            # Skip bots
            if login and is_bot(login):
                continue

            company = user.get("company")
            if company and len(company) > 1:
                # Normalize company name
                company_clean = company.strip().lower().replace("@", "")
                if company_clean:
                    organizations.add(company_clean)

        # Check email domain
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
        message = f"Excellent: {diversity_score} organizations/domains detected. Highly diverse."
    elif diversity_score >= 3:
        score = 7
        risk = "Low"
        message = (
            f"Good: {diversity_score} organizations/domains detected. Good diversity."
        )
    elif diversity_score >= 2:
        score = 4
        risk = "Medium"
        message = f"Moderate: {diversity_score} organizations/domains detected. Consider expanding."
    elif diversity_score == 1:
        score = 2
        risk = "High"
        message = "Observe: Single organization dominates. Dependency risk exists."
    else:
        score = max_score // 2
        risk = "None"
        message = "Note: Unable to determine organizational diversity (personal project likely)."

    return Metric("Organizational Diversity", score, max_score, message, risk)


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_organizational_diversity(repo_data)


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
    checker=_check,
    on_error=_on_error,
)
