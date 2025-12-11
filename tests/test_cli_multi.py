"""
Tests for multi-language CLI functionality.
"""

from unittest.mock import MagicMock, patch

from oss_sustain_guard.cli import analyze_package, parse_package_spec


class TestParsePackageSpec:
    """Test package specification parsing."""

    def test_simple_package_name(self):
        """Test parsing simple package name."""
        eco, pkg = parse_package_spec("requests")
        assert eco == "python"
        assert pkg == "requests"

    def test_ecosystem_prefix(self):
        """Test parsing with ecosystem prefix."""
        eco, pkg = parse_package_spec("npm:react")
        assert eco == "npm"
        assert pkg == "react"

    def test_ecosystem_prefix_case_insensitive(self):
        """Test ecosystem name is lowercased."""
        eco, pkg = parse_package_spec("NPM:React")
        assert eco == "npm"
        assert pkg == "React"

    def test_go_module_path(self):
        """Test parsing Go module path."""
        eco, pkg = parse_package_spec("go:github.com/gin-gonic/gin")
        assert eco == "go"
        assert pkg == "github.com/gin-gonic/gin"

    def test_direct_github_go_path(self):
        """Test parsing direct GitHub path for Go."""
        eco, pkg = parse_package_spec("github.com/golang/go")
        assert eco == "python"  # No prefix defaults to python
        assert pkg == "github.com/golang/go"


class TestAnalyzePackage:
    """Test package analysis functionality."""

    def test_analyze_excluded_package(self):
        """Test that excluded packages return None."""
        with patch("oss_sustain_guard.cli.is_package_excluded", return_value=True):
            result = analyze_package("excluded-pkg", "python", {})
            assert result is None

    def test_analyze_from_cache(self):
        """Test analyzing package from cache."""
        cached_db = {
            "python:requests": {
                "github_url": "https://github.com/psf/requests",
                "total_score": 85,  # Old score (will be recalculated)
                "metrics": [
                    {
                        "name": "Contributor Redundancy",
                        "score": 5,
                        "max_score": 10,
                        "message": "Good",
                        "risk": "Low",
                    }
                ],
            }
        }

        with patch("oss_sustain_guard.cli.is_package_excluded", return_value=False):
            result = analyze_package("requests", "python", cached_db)
            assert result is not None
            assert result.repo_url == "https://github.com/psf/requests"
            # Score is recalculated based on category weights (only 1/21 metrics = low score)
            assert result.total_score > 0  # At least some score
            assert (
                result.total_score < 85
            )  # Lower than cached due to incomplete metrics

    def test_analyze_unknown_ecosystem(self):
        """Test analyzing with unknown ecosystem."""
        with patch("oss_sustain_guard.cli.is_package_excluded", return_value=False):
            result = analyze_package("pkg", "unknown-eco", {})
            assert result is None

    @patch("oss_sustain_guard.cli.get_resolver")
    @patch("oss_sustain_guard.cli.is_package_excluded", return_value=False)
    def test_analyze_package_not_found(self, mock_excluded, mock_get_resolver):
        """Test analyzing package that doesn't have GitHub URL."""
        mock_resolver = MagicMock()
        mock_resolver.resolve_github_url.return_value = None
        mock_get_resolver.return_value = mock_resolver

        result = analyze_package("nonexistent", "python", {})
        assert result is None

    @patch("oss_sustain_guard.cli.save_cache")
    @patch("oss_sustain_guard.cli.analyze_repository")
    @patch("oss_sustain_guard.cli.get_resolver")
    @patch("oss_sustain_guard.cli.is_package_excluded", return_value=False)
    def test_analyze_package_success(
        self, mock_excluded, mock_get_resolver, mock_analyze_repo, mock_save_cache
    ):
        """Test successful package analysis."""
        from oss_sustain_guard.core import AnalysisResult, Metric

        mock_resolver = MagicMock()
        mock_resolver.resolve_github_url.return_value = ("psf", "requests")
        mock_get_resolver.return_value = mock_resolver

        mock_result = AnalysisResult(
            repo_url="https://github.com/psf/requests",
            total_score=85,
            metrics=[
                Metric(
                    name="Test Metric",
                    score=85,
                    max_score=100,
                    message="Package analyzed successfully",
                    risk="Low",
                )
            ],
        )
        mock_analyze_repo.return_value = mock_result

        result = analyze_package("requests", "python", {})
        assert result == mock_result
        # By default, enable_dependents=False, so platform and package_name should be None
        mock_analyze_repo.assert_called_once_with(
            "psf", "requests", platform=None, package_name=None
        )

    @patch("oss_sustain_guard.cli.save_cache")
    @patch("oss_sustain_guard.cli.analyze_repository")
    @patch("oss_sustain_guard.cli.get_resolver")
    @patch("oss_sustain_guard.cli.is_package_excluded", return_value=False)
    def test_analyze_package_with_dependents(
        self, mock_excluded, mock_get_resolver, mock_analyze_repo, mock_save_cache
    ):
        """Test package analysis with dependents enabled."""
        from oss_sustain_guard.core import AnalysisResult, Metric

        mock_resolver = MagicMock()
        mock_resolver.resolve_github_url.return_value = ("psf", "requests")
        mock_get_resolver.return_value = mock_resolver

        mock_result = AnalysisResult(
            repo_url="https://github.com/psf/requests",
            total_score=85,
            metrics=[
                Metric(
                    name="Test Metric",
                    score=85,
                    max_score=100,
                    message="Package analyzed successfully",
                    risk="Low",
                )
            ],
        )
        mock_analyze_repo.return_value = mock_result

        result = analyze_package("requests", "python", {}, enable_dependents=True)
        assert result == mock_result
        # With enable_dependents=True, platform and package_name should be passed
        mock_analyze_repo.assert_called_once_with(
            "psf", "requests", platform="Pypi", package_name="requests"
        )

    @patch("oss_sustain_guard.cli.save_cache")
    @patch("oss_sustain_guard.cli.analyze_repository")
    @patch("oss_sustain_guard.cli.get_resolver")
    @patch("oss_sustain_guard.cli.is_package_excluded", return_value=False)
    def test_analyze_package_error(
        self, mock_excluded, mock_get_resolver, mock_analyze_repo, mock_save_cache
    ):
        """Test package analysis with error."""
        mock_resolver = MagicMock()
        mock_resolver.resolve_github_url.return_value = ("user", "repo")
        mock_get_resolver.return_value = mock_resolver

        mock_analyze_repo.side_effect = Exception("API error")

        result = analyze_package("pkg", "python", {})
        assert result is None
        # save_cache should not be called on error
        mock_save_cache.assert_not_called()
