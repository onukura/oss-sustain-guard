"""
Tests for multi-language CLI functionality.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from oss_sustain_guard.cli import (
    _analyze_dependencies_for_package,
    analyze_package,
    load_database,
    load_packages_from_cloudflare,
    parse_package_spec,
)
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
        mock_resolver.resolve_repository.return_value = None
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
        mock_resolver.resolve_repository.return_value = RepositoryReference(
            provider="github",
            host="github.com",
            path="psf/requests",
            owner="psf",
            name="requests",
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
        mock_resolver.resolve_repository.return_value = RepositoryReference(
            provider="github",
            host="github.com",
            path="psf/requests",
            owner="psf",
            name="requests",
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
        mock_resolver.resolve_repository.return_value = RepositoryReference(
            provider="github",
            host="github.com",
            path="user/repo",
            owner="user",
            name="repo",
        )
        mock_get_resolver.return_value = mock_resolver

        mock_analyze_repo.side_effect = Exception("API error")

        result = analyze_package("pkg", "python", {})
        assert result is None
        # save_cache should not be called on error
        mock_save_cache.assert_not_called()


class TestLoadDatabase:
    """Test database loading functionality."""

    @patch("oss_sustain_guard.cli.load_cache")
    @patch("oss_sustain_guard.cli.is_cache_enabled", return_value=True)
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

    @patch("oss_sustain_guard.cli.load_cache", return_value=None)
    @patch("oss_sustain_guard.cli.is_cache_enabled", return_value=True)
    def test_load_database_empty_cache(self, mock_enabled, mock_load_cache):
        """Test loading database with empty cache."""
        db = load_database(use_cache=True, use_local_cache=True, verbose=False)
        assert db == {}

    @patch("oss_sustain_guard.cli.is_cache_enabled", return_value=False)
    def test_load_database_cache_disabled(self, mock_enabled):
        """Test loading database when cache is disabled."""
        db = load_database(use_cache=True, use_local_cache=True, verbose=False)
        assert db == {}


class TestLoadPackagesFromCloudflare:
    """Test Cloudflare KV loading functionality."""

    @patch("oss_sustain_guard.cli.CloudflareKVClient")
    @patch("oss_sustain_guard.cli.is_cache_enabled", return_value=True)
    @patch("oss_sustain_guard.cli.save_cache")
    @patch("oss_sustain_guard.cli.is_analysis_version_compatible", return_value=True)
    def test_load_packages_success(
        self, mock_version, mock_save, mock_cache_enabled, mock_client
    ):
        """Test successfully loading packages from Cloudflare KV."""
        mock_kv = MagicMock()
        mock_kv.batch_get.return_value = {
            "2.0:python:requests": {
                "ecosystem": "python",
                "package_name": "requests",
                "total_score": 85,
                "analysis_version": "2.0",
            }
        }
        mock_client.return_value = mock_kv

        result = load_packages_from_cloudflare([("python", "requests")], verbose=False)

        assert "python:requests" in result
        assert result["python:requests"]["total_score"] == 85

    @patch("oss_sustain_guard.cli.CloudflareKVClient")
    def test_load_packages_exception(self, mock_client):
        """Test handling exceptions when loading from Cloudflare KV."""
        mock_client.side_effect = Exception("Network error")

        result = load_packages_from_cloudflare([("python", "requests")], verbose=False)

        assert result == {}

    def test_load_packages_empty_list(self):
        """Test loading with empty package list."""
        result = load_packages_from_cloudflare([], verbose=False)
        assert result == {}

    @patch("oss_sustain_guard.cli.CloudflareKVClient")
    @patch("oss_sustain_guard.cli.is_analysis_version_compatible", return_value=False)
    def test_load_packages_incompatible_version(self, mock_version, mock_client):
        """Test skipping packages with incompatible analysis version."""
        mock_kv = MagicMock()
        mock_kv.batch_get.return_value = {
            "2.0:python:requests": {
                "ecosystem": "python",
                "package_name": "requests",
                "total_score": 85,
                "analysis_version": "1.0",
            }
        }
        mock_client.return_value = mock_kv

        result = load_packages_from_cloudflare([("python", "requests")], verbose=False)

        assert result == {}


class TestAnalyzeDependenciesForPackage:
    """Test dependency analysis functionality."""

    @patch("oss_sustain_guard.dependency_graph.get_package_dependencies")
    def test_analyze_dependencies_success(self, mock_get_deps):
        """Test successful dependency analysis."""
        # Mock get_package_dependencies to return a list of dependency names
        mock_get_deps.return_value = ["dep1", "dep2"]

        db = {
            "python:dep1": {
                "metrics": [
                    {
                        "name": "Contributor Redundancy",
                        "score": 20,
                        "max_score": 20,
                        "message": "Test message",
                        "risk": "None",
                    },
                    {
                        "name": "Recent Activity",
                        "score": 15,
                        "max_score": 20,
                        "message": "Test message",
                        "risk": "None",
                    },
                    {
                        "name": "Security Signals",
                        "score": 10,
                        "max_score": 15,
                        "message": "Test message",
                        "risk": "None",
                    },
                ]
            },
            "python:dep2": {
                "metrics": [
                    {
                        "name": "Contributor Redundancy",
                        "score": 20,
                        "max_score": 20,
                        "message": "Test message",
                        "risk": "None",
                    },
                    {
                        "name": "Recent Activity",
                        "score": 20,
                        "max_score": 20,
                        "message": "Test message",
                        "risk": "None",
                    },
                    {
                        "name": "Security Signals",
                        "score": 15,
                        "max_score": 15,
                        "message": "Test message",
                        "risk": "None",
                    },
                ]
            },
        }

        # Create a temporary lockfile
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".lock", delete=False) as tmp:
            tmp.write("")
            tmp_path = tmp.name

        try:
            result = _analyze_dependencies_for_package(
                "python", tmp_path, db, "test-package"
            )

            assert "dep1" in result
            assert "dep2" in result
            # Scores are calculated from metrics using balanced profile
            # dep1: Contributor Redundancy (20/20) + Recent Activity (15/20) + Security Signals (10/15)
            # dep2: Contributor Redundancy (20/20) + Recent Activity (20/20) + Security Signals (15/15)
            # Scores will be weighted by category
            assert result["dep1"] > 0  # Should have a positive score
            assert result["dep2"] > 0  # Should have a positive score
            assert result["dep2"] > result["dep1"]  # dep2 has better scores
        finally:
            import os

            os.unlink(tmp_path)

    def test_analyze_dependencies_missing_lockfile(self):
        """Test dependency analysis with missing lockfile."""
        result = _analyze_dependencies_for_package(
            "python", "/nonexistent/file.lock", {}, "test-package"
        )
        assert result == {}

    @patch("oss_sustain_guard.dependency_graph.get_package_dependencies")
    def test_analyze_dependencies_no_deps(self, mock_get_deps):
        """Test dependency analysis with no dependencies found."""
        mock_get_deps.return_value = []

        result = _analyze_dependencies_for_package(
            "python", "/tmp/test.lock", {}, "test-package"
        )
        assert result == {}

    @patch("oss_sustain_guard.dependency_graph.get_package_dependencies")
    def test_analyze_dependencies_exception(self, mock_get_deps):
        """Test dependency analysis with exception."""
        mock_get_deps.side_effect = Exception("Parse error")

        result = _analyze_dependencies_for_package(
            "python", "/tmp/test.lock", {}, "test-package"
        )
        assert result == {}
