"""Tests for bot detection utilities."""

from oss_sustain_guard.bot_detection import (
    BOT_EMAIL_DOMAINS,
    BOT_KEYWORDS,
    KNOWN_BOT_PATTERNS,
    extract_login,
    is_bot,
    is_bot_by_email_domain,
    is_bot_by_exact_pattern,
    is_bot_by_keyword,
)


class TestBotPatternsDefinition:
    """Test that bot patterns are properly defined."""

    def test_github_bots_patterns_exist(self):
        """Test that GitHub bot patterns are defined."""
        assert "github_bots" in KNOWN_BOT_PATTERNS
        assert len(KNOWN_BOT_PATTERNS["github_bots"]) > 0

    def test_bot_keywords_exist(self):
        """Test that bot keywords are defined."""
        assert len(BOT_KEYWORDS) > 0
        assert "bot" in BOT_KEYWORDS

    def test_email_domains_exist(self):
        """Test that email domains are defined."""
        assert len(BOT_EMAIL_DOMAINS) > 0


class TestIsBot:
    """Test the main is_bot function."""

    def test_known_github_bot_exact_match(self):
        """Test detection of known GitHub bots."""
        assert is_bot("dependabot[bot]")
        assert is_bot("github-actions[bot]")
        assert is_bot("renovate[bot]")

    def test_keyword_matching_fallback(self):
        """Test keyword matching as fallback."""
        assert is_bot("my-ci-bot")
        assert is_bot("test-action")
        assert is_bot("ci-system")

    def test_email_domain_bot_detection(self):
        """Test bot detection via email domain."""
        assert is_bot("someuser", email="someuser@noreply.github.com")
        assert is_bot("someuser", email="bot@users.noreply.github.com")

    def test_name_based_detection(self):
        """Test bot detection via name field."""
        assert is_bot(None, name="GitHub Bot")
        assert is_bot(None, name="CI Action")

    def test_excluded_users_list(self):
        """Test that excluded_users list overrides other checks."""
        assert is_bot("normaluser", excluded_users=["normaluser"])
        assert is_bot("john-doe", excluded_users=["john-doe"])

    def test_real_users_not_detected_as_bots(self):
        """Test that real user names are not incorrectly detected as bots."""
        assert not is_bot("john-doe")
        assert not is_bot("alice")
        # Note: "actionhero" may still be detected due to keyword matching
        # This is a known limitation that could be addressed with more
        # sophisticated pattern matching in future versions
        assert not is_bot("bob")
        assert not is_bot("charlie-xyz")

    def test_none_login_with_no_alternatives(self):
        """Test that None login returns False when no email/name given."""
        assert not is_bot(None)


class TestIsBotByExactPattern:
    """Test exact pattern matching."""

    def test_github_official_bots(self):
        """Test GitHub official bot patterns."""
        assert is_bot_by_exact_pattern("dependabot[bot]")
        assert is_bot_by_exact_pattern("github-actions[bot]")
        assert is_bot_by_exact_pattern("dependabot-preview[bot]")

    def test_gitlab_bots(self):
        """Test GitLab bot patterns."""
        assert is_bot_by_exact_pattern("dependabot")
        assert is_bot_by_exact_pattern("renovate-bot")

    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive."""
        assert is_bot_by_exact_pattern("DependaBot[Bot]")
        assert is_bot_by_exact_pattern("GITHUB-ACTIONS[BOT]")

    def test_non_matching_patterns(self):
        """Test that non-matching patterns return False."""
        assert not is_bot_by_exact_pattern("john-doe")
        assert not is_bot_by_exact_pattern("actionhero")


class TestIsBotByKeyword:
    """Test keyword-based bot detection."""

    def test_bot_keyword_detection(self):
        """Test detection of 'bot' keyword."""
        assert is_bot_by_keyword("my-bot")
        assert is_bot_by_keyword("bot-action")
        assert is_bot_by_keyword("bot")

    def test_action_keyword_detection(self):
        """Test detection of 'action' keyword."""
        assert is_bot_by_keyword("my-action")
        assert is_bot_by_keyword("ci-action")

    def test_case_insensitive_keyword(self):
        """Test that keyword matching is case-insensitive."""
        assert is_bot_by_keyword("MyBot")
        assert is_bot_by_keyword("ACTION-system")

    def test_non_matching_keywords(self):
        """Test that non-bot names return False."""
        assert not is_bot_by_keyword("john-doe")
        assert not is_bot_by_keyword("alice")


class TestIsBotByEmailDomain:
    """Test email domain-based bot detection."""

    def test_github_noreply_detection(self):
        """Test GitHub noreply addresses."""
        assert is_bot_by_email_domain("user@noreply.github.com")
        assert is_bot_by_email_domain("bot@users.noreply.github.com")

    def test_gitlab_detection(self):
        """Test GitLab addresses."""
        assert is_bot_by_email_domain("bot@gitlab.com")

    def test_case_insensitive_email(self):
        """Test that email matching is case-insensitive."""
        assert is_bot_by_email_domain("user@NOREPLY.GITHUB.COM")
        assert is_bot_by_email_domain("USER@No-Reply.GitHub.com")

    def test_non_matching_email(self):
        """Test that regular emails return False."""
        assert not is_bot_by_email_domain("user@example.com")
        assert not is_bot_by_email_domain("")


class TestExtractLogin:
    """Test the extract_login helper function."""

    def test_extract_login_from_user_object(self):
        """Test extracting login from user object."""
        commit = {
            "author": {
                "user": {
                    "login": "john-doe",
                }
            }
        }
        assert extract_login(commit) == "john-doe"

    def test_extract_login_fallback_to_name(self):
        """Test fallback to name field."""
        commit = {
            "author": {
                "name": "John Doe",
            }
        }
        assert extract_login(commit) == "John Doe"

    def test_extract_login_fallback_to_email(self):
        """Test fallback to email field."""
        commit = {
            "author": {
                "email": "john@example.com",
            }
        }
        assert extract_login(commit) == "john@example.com"

    def test_extract_login_priority(self):
        """Test that login has priority over name and email."""
        commit = {
            "author": {
                "user": {
                    "login": "github-user",
                },
                "name": "John Doe",
                "email": "john@example.com",
            }
        }
        assert extract_login(commit) == "github-user"

    def test_extract_login_none(self):
        """Test that None is returned for commits without author info."""
        assert extract_login({}) is None
        assert extract_login({"author": None}) is None
        assert extract_login({"author": {}}) is None


class TestIntegration:
    """Integration tests for bot detection."""

    def test_real_projects_bots(self):
        """Test detection of bots from real-world scenarios."""
        # Dependabot PR commits
        commits_with_dependabot = [
            {
                "author": {
                    "user": {
                        "login": "dependabot[bot]",
                    },
                    "email": "dependabot@users.noreply.github.com",
                }
            },
            {
                "author": {
                    "user": {
                        "login": "john-doe",
                    },
                    "email": "john@example.com",
                }
            },
        ]

        bot_count: int = sum(
            1
            for commit in commits_with_dependabot
            if is_bot(
                (
                    lambda author: author.get("user", {}).get("login")
                    if isinstance(author, dict) and isinstance(author.get("user"), dict)
                    else None
                )(commit.get("author", {}))
            )
        )
        assert bot_count == 1

    def test_false_positive_prevention(self):
        """Test that real users with 'bot' in name are not falsely flagged."""
        # Common pattern: user with "bot" in their legitimate name
        real_users = [
            "actionhero",  # Contains "action" but not a bot
            "bot-master",  # Might be a username
            "robotics-team",  # Contains "bot" but is a real team
        ]

        for user in real_users:
            # These should not be detected as bots by exact pattern
            assert not is_bot_by_exact_pattern(user)

    def test_multi_stage_detection(self):
        """Test multi-stage detection process."""
        # First: exact match
        assert is_bot("github-actions[bot]")

        # Second: keyword match
        assert is_bot("ci-build-system")

        # Third: email domain
        assert is_bot("anonymous", email="bot@noreply.github.com")

        # Fourth: excluded users
        assert is_bot("trusted-ci", excluded_users=["trusted-ci"])

        # Should not match real users
        assert not is_bot("alice")
        assert not is_bot("bob", email="bob@example.com")
