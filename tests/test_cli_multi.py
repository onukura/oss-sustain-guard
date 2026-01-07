"""
Tests for multi-language CLI functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from oss_sustain_guard.cli_utils.helpers import load_database, parse_package_spec
from oss_sustain_guard.commands.check import (
    analyze_package,
)
from oss_sustain_guard.core import AnalysisResult, Metric
from oss_sustain_guard.repository import RepositoryReference

runner = CliRunner()


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

    async def test_analyze_excluded_package(self):
        """Test that excluded packages return None."""
        with patch(
            "oss_sustain_guard.commands.check.is_package_excluded", return_value=True
        ):
            result = await analyze_package("excluded-pkg", "python", {})
            assert result is None

    async def test_analyze_from_cache(self):
        """Test analyzing package from cache."""
        from oss_sustain_guard.cli_utils.constants import ANALYSIS_VERSION

        cached_db = {
            "python:requests": {
                "github_url": "https://github.com/psf/requests",
                "total_score": 85,  # Old score (will be recalculated)
                "analysis_version": ANALYSIS_VERSION,  # Add version to use cache
                "metrics": [
                    {
                        "name": "Contributor Redundancy",
                        "score": 5,
                        "max_score": 10,
                        "message": "Good",
                        "risk": "Low",
                    }
                ],
                "funding_links": [],
                "is_community_driven": False,
                "models": [],
                "signals": {},
            }
        }

        with patch(
            "oss_sustain_guard.commands.check.is_package_excluded", return_value=False
        ):
            result = await analyze_package("requests", "python", cached_db)
            assert result is not None
            assert result.repo_url == "https://github.com/psf/requests"
            # Score is recalculated based on metric weights (only 1/21 metrics = low score)
            assert result.total_score > 0  # At least some score
            assert (
                result.total_score < 85
            )  # Lower than cached due to incomplete metrics

    async def test_analyze_unknown_ecosystem(self):
        """Test analyzing with unknown ecosystem."""
        with patch(
            "oss_sustain_guard.commands.check.is_package_excluded", return_value=False
        ):
            result = await analyze_package("pkg", "unknown-eco", {})
            assert result is None

    @patch("oss_sustain_guard.commands.check.get_resolver")
    @patch("oss_sustain_guard.commands.check.is_package_excluded", return_value=False)
    async def test_analyze_package_not_found(self, mock_excluded, mock_get_resolver):
        """Test analyzing package that doesn't have GitHub URL."""
        mock_resolver = MagicMock()
        mock_resolver.resolve_repository = AsyncMock(return_value=None)
        mock_get_resolver.return_value = mock_resolver

        result = await analyze_package("nonexistent", "python", {})
        assert result is None

    @patch("oss_sustain_guard.commands.check.analyze_repository")
    @patch("oss_sustain_guard.commands.check.get_resolver")
    @patch("oss_sustain_guard.commands.check.is_package_excluded", return_value=False)
    async def test_analyze_package_success(
        self, mock_excluded, mock_get_resolver, mock_analyze_repo
    ):
        """Test successful package analysis."""
        mock_resolver = MagicMock()
        mock_resolver.resolve_repository = AsyncMock(
            return_value=RepositoryReference(
                provider="github",
                host="github.com",
                path="psf/requests",
                owner="psf",
                name="requests",
            )
        )
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
            ecosystem="python",
        )
        mock_analyze_repo.return_value = mock_result

        result = await analyze_package("requests", "python", {})
        assert result == mock_result
        # Registry context is not used when analyzing packages directly.
        mock_analyze_repo.assert_called_once_with(
            "psf",
            "requests",
            profile="balanced",
            vcs_platform="github",
        )

    @patch("oss_sustain_guard.commands.check.analyze_repository")
    @patch("oss_sustain_guard.commands.check.get_resolver")
    @patch("oss_sustain_guard.commands.check.is_package_excluded", return_value=False)
    async def test_analyze_package_error(
        self, mock_excluded, mock_get_resolver, mock_analyze_repo
    ):
        """Test package analysis with error."""
        mock_resolver = MagicMock()
        mock_resolver.resolve_repository = AsyncMock(
            return_value=RepositoryReference(
                provider="github",
                host="github.com",
                path="user/repo",
                owner="user",
                name="repo",
            )
        )
        mock_get_resolver.return_value = mock_resolver

        mock_analyze_repo.side_effect = Exception("API error")

        result = await analyze_package("pkg", "python", {})
        assert result is None


class TestLoadDatabase:
    """Test database loading functionality."""

    @patch("oss_sustain_guard.cli_utils.helpers.load_cache")
    @patch("oss_sustain_guard.cli_utils.helpers.is_cache_enabled", return_value=True)
    def test_load_database_with_local_cache(self, mock_enabled, mock_load_cache):
        """Test loading database from local cache."""
        mock_load_cache.return_value = {
            "python:requests": {"package_name": "requests", "total_score": 85}
        }

        db = load_database(use_cache=True, use_local_cache=True, verbose=False)

        assert "python:requests" in db
        assert db["python:requests"]["total_score"] == 85
        # Should be called for each ecosystem
        assert mock_load_cache.call_count == 15  # 15 ecosystems

    def test_load_database_no_cache(self):
        """Test loading database with cache disabled."""
        db = load_database(use_cache=False, use_local_cache=True, verbose=False)
        assert db == {}

    @patch("oss_sustain_guard.cli_utils.helpers.load_cache", return_value=None)
    @patch("oss_sustain_guard.cli_utils.helpers.is_cache_enabled", return_value=True)
    def test_load_database_empty_cache(self, mock_enabled, mock_load_cache):
        """Test loading database with empty cache."""
        db = load_database(use_cache=True, use_local_cache=True, verbose=False)
        assert db == {}

    @patch("oss_sustain_guard.cli_utils.helpers.is_cache_enabled", return_value=False)
    def test_load_database_cache_disabled(self, mock_enabled):
        """Test loading database when cache is disabled."""
        db = load_database(use_cache=True, use_local_cache=True, verbose=False)
        assert db == {}
