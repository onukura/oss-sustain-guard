"""
Tests for LFX Insights integration.
"""

from oss_sustain_guard.integrations.lfx import (
    LFXProjectResolver,
    LFXUrlBuilder,
    get_lfx_info,
)


class TestLFXUrlBuilder:
    """Tests for LFXUrlBuilder class."""

    def test_build_project_url(self):
        """Test building project URL."""
        url = LFXUrlBuilder.build_project_url("kubernetes-kubernetes")
        assert (
            url == "https://insights.linuxfoundation.org/project/kubernetes-kubernetes"
        )

    def test_build_badge_url_health_score(self):
        """Test building health-score badge URL."""
        url = LFXUrlBuilder.build_badge_url("health-score", "kubernetes-kubernetes")
        assert (
            url
            == "https://insights.linuxfoundation.org/api/badge/health-score?project=kubernetes-kubernetes"
        )

    def test_build_badge_url_active_contributors(self):
        """Test building active-contributors badge URL."""
        url = LFXUrlBuilder.build_badge_url(
            "active-contributors", "ant-design-ant-design"
        )
        assert (
            url
            == "https://insights.linuxfoundation.org/api/badge/active-contributors?project=ant-design-ant-design"
        )

    def test_build_badge_url_with_repos(self):
        """Test building active-contributors badge URL with repos parameter."""
        url = LFXUrlBuilder.build_badge_url(
            "active-contributors",
            "ant-design-ant-design",
            "https://github.com/ant-design/ant-design",
        )
        assert "repos=https%3A%2F%2Fgithub.com%2Fant-design%2Fant-design" in url

    def test_build_all_badges(self):
        """Test building all default badges."""
        badges = LFXUrlBuilder.build_all_badges("kubernetes-kubernetes")
        assert "health-score" in badges
        assert "active-contributors" in badges
        assert len(badges) == 2

    def test_build_all_badges_custom_types(self):
        """Test building custom badge types."""
        badges = LFXUrlBuilder.build_all_badges(
            "kubernetes-kubernetes",
            badge_types=["health-score", "contributors"],
        )
        assert "health-score" in badges
        assert "contributors" in badges
        assert len(badges) == 2


class TestLFXProjectResolver:
    """Tests for LFXProjectResolver class."""

    def test_resolve_from_github_url_standard(self):
        """Test resolving from standard GitHub URL."""
        slug = LFXProjectResolver.resolve_from_github_url(
            "https://github.com/kubernetes/kubernetes"
        )
        assert slug == "kubernetes-kubernetes"

    def test_resolve_from_github_url_with_trailing_slash(self):
        """Test resolving from GitHub URL with trailing slash."""
        slug = LFXProjectResolver.resolve_from_github_url(
            "https://github.com/ant-design/ant-design/"
        )
        assert slug == "ant-design-ant-design"

    def test_resolve_from_github_url_with_git_extension(self):
        """Test resolving from GitHub URL with .git extension."""
        slug = LFXProjectResolver.resolve_from_github_url(
            "https://github.com/facebook/react.git"
        )
        assert slug == "facebook-react"

    def test_resolve_from_github_url_ssh_format(self):
        """Test resolving from SSH GitHub URL."""
        slug = LFXProjectResolver.resolve_from_github_url(
            "git@github.com:nodejs/node.git"
        )
        assert slug == "nodejs-node"

    def test_resolve_from_github_url_invalid(self):
        """Test resolving from invalid URL."""
        slug = LFXProjectResolver.resolve_from_github_url("https://example.com")
        assert slug is None

    def test_resolve_from_github_url_none(self):
        """Test resolving from None."""
        slug = LFXProjectResolver.resolve_from_github_url(None)  # type: ignore
        assert slug is None

    def test_resolve_with_config_mapping(self):
        """Test resolving with explicit config mapping (highest priority)."""
        config = {"pypi:requests": "psf-requests"}
        slug, method = LFXProjectResolver.resolve(
            "pypi:requests",
            repo_url="https://github.com/psf/requests",
            config_mapping=config,
        )
        assert slug == "psf-requests"
        assert method == "config"

    def test_resolve_with_heuristic(self):
        """Test resolving with heuristic from GitHub URL."""
        slug, method = LFXProjectResolver.resolve(
            "npm:react", repo_url="https://github.com/facebook/react"
        )
        assert slug == "facebook-react"
        assert method == "heuristic"

    def test_resolve_unable(self):
        """Test resolving when unable to determine slug."""
        slug, method = LFXProjectResolver.resolve("pypi:unknown")
        assert slug is None
        assert method == "none"

    def test_resolve_config_takes_precedence(self):
        """Test that config mapping takes precedence over heuristic."""
        config = {"npm:react": "custom-react-slug"}
        slug, method = LFXProjectResolver.resolve(
            "npm:react",
            repo_url="https://github.com/facebook/react",
            config_mapping=config,
        )
        assert slug == "custom-react-slug"
        assert method == "config"


class TestGetLFXInfo:
    """Tests for get_lfx_info function."""

    def test_get_lfx_info_success(self):
        """Test getting LFX info successfully."""
        info = get_lfx_info("npm:react", repo_url="https://github.com/facebook/react")
        assert info is not None
        assert info.project_slug == "facebook-react"
        assert (
            info.project_url
            == "https://insights.linuxfoundation.org/project/facebook-react"
        )
        assert "health-score" in info.badges
        assert "active-contributors" in info.badges
        assert info.resolution == "heuristic"

    def test_get_lfx_info_with_config(self):
        """Test getting LFX info with config mapping."""
        config = {"pypi:requests": "psf-requests"}
        info = get_lfx_info(
            "pypi:requests",
            repo_url="https://github.com/psf/requests",
            config_mapping=config,
        )
        assert info is not None
        assert info.project_slug == "psf-requests"
        assert info.resolution == "config"

    def test_get_lfx_info_unable_to_resolve(self):
        """Test getting LFX info when unable to resolve."""
        info = get_lfx_info("pypi:unknown")
        assert info is None

    def test_get_lfx_info_custom_badges(self):
        """Test getting LFX info with custom badge types."""
        info = get_lfx_info(
            "npm:react",
            repo_url="https://github.com/facebook/react",
            badge_types=["health-score", "contributors"],
        )
        assert info is not None
        assert "health-score" in info.badges
        assert "contributors" in info.badges
        assert "active-contributors" not in info.badges

    def test_get_lfx_info_repos_url_included(self):
        """Test that repos_url is included in LFXInfo."""
        repo_url = "https://github.com/kubernetes/kubernetes"
        info = get_lfx_info("github:kubernetes/kubernetes", repo_url=repo_url)
        assert info is not None
        assert info.repos_url == repo_url
