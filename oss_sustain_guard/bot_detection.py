"""
Bot detection utilities for identifying automated accounts in version control systems.

This module provides a centralized, configurable bot detection system that identifies
common patterns used by bots and automated services across GitHub, GitLab, and other VCS platforms.

Features:
- Known bot pattern matching (github-actions[bot], dependabot[bot], etc.)
- Keyword-based pattern matching (fallback for generic bots)
- Configurable exclusion list via settings
- Support for email domain-based bot detection
"""

from typing import Any

# Known bot account patterns - these are exact or regex-like patterns
# Format: {pattern_type: [patterns]}
KNOWN_BOT_PATTERNS = {
    # GitHub official bots with [bot] suffix
    "github_bots": [
        "dependabot[bot]",
        "dependabot-preview[bot]",
        "github-actions[bot]",
        "renovate[bot]",
        "snyk-bot[bot]",
        "renovatebot",
        "release-drafter[bot]",
        "stale[bot]",
        "probot[bot]",
        "codecov[bot]",
        "coveralls[bot]",
    ],
    # GitLab bots
    "gitlab_bots": [
        "dependabot",
        "renovate-bot",
        "gitlab-runner",
    ],
    # Known service bots and CI/CD automation
    "service_bots": [
        "travis-ci",
        "circleci",
        "jenkins",
        "appveyor",
        "drone-io",
        "semaphore",
        "buildkite",
        "netlify",
        "vercel",
    ],
}

# Bot keyword patterns (case-insensitive substring matching)
# These are fallback patterns for detecting bots by name
BOT_KEYWORDS = [
    "bot",
    "action",
    "ci-",
    "autorelease",
    "release-bot",
    "copilot",
    "actions-user",
]

# Email domains commonly used by bots
BOT_EMAIL_DOMAINS = [
    "noreply.github.com",
    "github.com",
    "no-reply.github.com",
    "gitlab.com",
    "users.noreply.github.com",
]


def is_bot_by_exact_pattern(login: str) -> bool:
    """
    Check if login matches a known bot pattern exactly.

    This function checks against known bot account names from GitHub, GitLab,
    and other services. It's more precise than keyword matching.

    Args:
        login: The user login/username to check.

    Returns:
        True if the login matches a known bot pattern, False otherwise.
    """
    login_lower = login.lower()

    # Check all known bot patterns
    for pattern_list in KNOWN_BOT_PATTERNS.values():
        for pattern in pattern_list:
            if login_lower == pattern.lower():
                return True

    return False


def is_bot_by_keyword(login: str) -> bool:
    """
    Check if login contains common bot keywords (case-insensitive).

    This is a fallback mechanism for generic bots that don't match specific patterns.
    It's more prone to false positives but catches unknown bots.

    Args:
        login: The user login/username to check.

    Returns:
        True if the login contains a bot keyword, False otherwise.
    """
    lower = login.lower()
    return any(keyword in lower for keyword in BOT_KEYWORDS)


def is_bot_by_email_domain(email: str) -> bool:
    """
    Check if email belongs to a known bot service.

    Args:
        email: The email address to check.

    Returns:
        True if the email domain is associated with bots, False otherwise.
    """
    if not email:
        return False

    email_lower = email.lower()
    return any(domain in email_lower for domain in BOT_EMAIL_DOMAINS)


def is_bot(
    login: str | None,
    email: str | None = None,
    name: str | None = None,
    excluded_users: list[str] | None = None,
) -> bool:
    """
    Determine if a commit author is a bot account.

    This function uses a multi-level approach:
    1. Check against user-provided exclusion list
    2. Check against known bot patterns (most reliable)
    3. Check email domain (for noreply addresses)
    4. Check for bot keywords in login (fallback, less reliable)
    5. Check for bot keywords in name

    Args:
        login: The user login/username.
        email: The email address (optional).
        name: The author name (optional).
        excluded_users: List of user logins to exclude as bots (from configuration).

    Returns:
        True if the author is determined to be a bot, False otherwise.
    """
    if not login:
        # No login available - check email/name as fallback
        if email and is_bot_by_email_domain(email):
            return True
        if name and is_bot_by_keyword(name):
            return True
        return False

    login_str = str(login).strip()

    # Check user-provided exclusion list first
    if excluded_users:
        excluded_lower = [u.lower() for u in excluded_users]
        if login_str.lower() in excluded_lower:
            return True

    # Check exact pattern match (most reliable)
    if is_bot_by_exact_pattern(login_str):
        return True

    # Check email domain
    if email and is_bot_by_email_domain(email):
        return True

    # Check keywords as fallback
    if is_bot_by_keyword(login_str):
        return True

    # Check name as last resort
    if name and is_bot_by_keyword(name):
        return True

    return False


def extract_login(commit: dict[str, Any]) -> str | None:
    """
    Extract a stable contributor identifier from a commit object.

    Tries to get login from the user object first, then falls back to
    name or email for commits without a linked GitHub account.

    Args:
        commit: The commit dictionary from VCS API response.

    Returns:
        The login/identifier string, or None if not available.
    """
    author = commit.get("author")
    if not isinstance(author, dict):
        return None

    # Try to get GitHub login first
    user = author.get("user")
    if isinstance(user, dict):
        login = user.get("login")
        if login:
            return login

    # Fallback to name or email
    for key in ("name", "email"):
        value = author.get(key)
        if value:
            return value

    return None
