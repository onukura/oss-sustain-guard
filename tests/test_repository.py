"""
Tests for repository URL parsing helpers.
"""

from oss_sustain_guard.repository import parse_repository_url


def test_parse_github_https_url():
    """Parse a standard GitHub HTTPS URL."""
    repo = parse_repository_url("https://github.com/owner/repo")
    assert repo is not None
    assert repo.provider == "github"
    assert repo.host == "github.com"
    assert repo.owner == "owner"
    assert repo.name == "repo"
    assert repo.path == "owner/repo"
    assert repo.url == "https://github.com/owner/repo"


def test_parse_gitlab_ssh_url():
    """Parse a GitLab SSH URL with subgroups."""
    repo = parse_repository_url("git@gitlab.com:group/subgroup/repo.git")
    assert repo is not None
    assert repo.provider == "gitlab"
    assert repo.host == "gitlab.com"
    assert repo.owner == "group"
    assert repo.name == "repo"
    assert repo.path == "group/subgroup/repo"


def test_parse_gitlab_web_url_with_suffix():
    """Parse a GitLab URL that includes a merge request path."""
    repo = parse_repository_url("https://gitlab.com/group/project/-/merge_requests/12")
    assert repo is not None
    assert repo.provider == "gitlab"
    assert repo.owner == "group"
    assert repo.name == "project"
    assert repo.path == "group/project"


def test_parse_unknown_host_returns_none():
    """Return None for unsupported hosts."""
    assert parse_repository_url("https://example.com/owner/repo") is None
