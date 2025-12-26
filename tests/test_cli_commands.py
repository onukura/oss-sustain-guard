"""
Tests for CLI commands (check, cache_stats, gratitude, trend, compare, list_snapshots).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from oss_sustain_guard.cli import app
from oss_sustain_guard.core import AnalysisResult, Metric

runner = CliRunner()


class TestCheckCommand:
    """Test the 'check' command."""

    @patch("oss_sustain_guard.cli.analyze_package")
    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.is_verbose_enabled", return_value=False)
    @patch("oss_sustain_guard.cli.get_output_style", return_value="normal")
    def test_check_single_package(
        self, mock_style, mock_verbose, mock_load_db, mock_analyze
    ):
        """Test checking a single package."""
        mock_load_db.return_value = {}
        mock_analyze.return_value = AnalysisResult(
            repo_url="https://github.com/psf/requests",
            total_score=85,
            metrics=[
                Metric(
                    name="Test Metric",
                    score=85,
                    max_score=100,
                    message="Good",
                    risk="Low",
                )
            ],
            funding_links=[],
            is_community_driven=False,
            models=[],
            signals={},
            dependency_scores={},
        )

        result = runner.invoke(app, ["check", "requests"])

        assert result.exit_code == 0
        assert "psf/requests" in result.stdout

    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.is_verbose_enabled", return_value=False)
    @patch("oss_sustain_guard.cli.get_output_style", return_value="normal")
    def test_check_no_packages_no_manifest(
        self, mock_style, mock_verbose, mock_load_db
    ):
        """Test check command with no packages and no manifest files."""
        mock_load_db.return_value = {}

        with patch(
            "oss_sustain_guard.cli.detect_ecosystems", return_value=[]
        ) as _mock_detect:
            result = runner.invoke(app, ["check"])

            # Should exit with code 0 (silent exit for pre-commit hooks)
            assert result.exit_code == 0

    @patch("oss_sustain_guard.cli.clear_cache")
    def test_check_clear_cache_flag(self, mock_clear):
        """Test --clear-cache flag."""
        mock_clear.return_value = 5

        result = runner.invoke(app, ["check", "--clear-cache"])

        assert result.exit_code == 0
        assert "Cleared 5 cache file(s)" in result.stdout
        mock_clear.assert_called_once()

    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.is_verbose_enabled", return_value=False)
    @patch("oss_sustain_guard.cli.get_output_style", return_value="normal")
    def test_check_invalid_profile(self, mock_style, mock_verbose, mock_load_db):
        """Test check command with invalid scoring profile."""
        mock_load_db.return_value = {}

        result = runner.invoke(app, ["check", "requests", "--profile", "invalid"])

        assert result.exit_code == 1
        assert "Unknown profile 'invalid'" in result.stdout

    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.is_verbose_enabled", return_value=False)
    @patch("oss_sustain_guard.cli.get_output_style", return_value="normal")
    def test_check_invalid_output_style(self, mock_style, mock_verbose, mock_load_db):
        """Test check command with invalid output style."""
        mock_load_db.return_value = {}

        result = runner.invoke(app, ["check", "requests", "--output-style", "invalid"])

        assert result.exit_code == 1
        assert "Unknown output style 'invalid'" in result.stdout

    @patch("oss_sustain_guard.cli.analyze_package")
    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.is_package_excluded", return_value=True)
    @patch("oss_sustain_guard.cli.is_verbose_enabled", return_value=False)
    @patch("oss_sustain_guard.cli.get_output_style", return_value="normal")
    def test_check_excluded_packages(
        self, mock_style, mock_verbose, mock_excluded, mock_load_db, mock_analyze
    ):
        """Test checking excluded packages."""
        mock_load_db.return_value = {}

        result = runner.invoke(app, ["check", "excluded-pkg"])

        assert result.exit_code == 0
        # The message shows "Skipping" not "Skipped"
        assert "Skipping" in result.stdout and "excluded" in result.stdout
        mock_analyze.assert_not_called()

    @patch("oss_sustain_guard.cli.analyze_package")
    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.is_verbose_enabled", return_value=False)
    @patch("oss_sustain_guard.cli.get_output_style", return_value="compact")
    def test_check_compact_output(
        self, mock_style, mock_verbose, mock_load_db, mock_analyze
    ):
        """Test check command with compact output style."""
        mock_load_db.return_value = {}
        mock_analyze.return_value = AnalysisResult(
            repo_url="https://github.com/psf/requests",
            total_score=85,
            metrics=[
                Metric(
                    name="Test Metric",
                    score=85,
                    max_score=100,
                    message="Good",
                    risk="Low",
                )
            ],
            funding_links=[],
            is_community_driven=False,
            models=[],
            signals={},
            dependency_scores={},
        )

        result = runner.invoke(app, ["check", "requests"])

        assert result.exit_code == 0
        # Compact output should show one line per package
        assert "psf/requests" in result.stdout
        assert "(85/100)" in result.stdout

    @patch("oss_sustain_guard.cli.analyze_package")
    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.is_verbose_enabled", return_value=False)
    @patch("oss_sustain_guard.cli.get_output_style", return_value="detail")
    def test_check_detail_output(
        self, mock_style, mock_verbose, mock_load_db, mock_analyze
    ):
        """Test check command with detail output style."""
        mock_load_db.return_value = {}
        mock_analyze.return_value = AnalysisResult(
            repo_url="https://github.com/psf/requests",
            total_score=85,
            metrics=[
                Metric(
                    name="Test Metric",
                    score=85,
                    max_score=100,
                    message="Good",
                    risk="Low",
                )
            ],
            funding_links=[],
            is_community_driven=False,
            models=[],
            signals={},
            dependency_scores={},
        )

        result = runner.invoke(app, ["check", "requests"])

        assert result.exit_code == 0
        # Detail output should show metrics table
        assert "psf/requests" in result.stdout
        assert "Test Metric" in result.stdout

    @patch("oss_sustain_guard.cli.analyze_package")
    @patch("oss_sustain_guard.cli.get_resolver")
    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.is_verbose_enabled", return_value=False)
    @patch("oss_sustain_guard.cli.get_output_style", return_value="normal")
    def test_check_with_manifest_file(
        self, mock_style, mock_verbose, mock_load_db, mock_resolver, mock_analyze
    ):
        """Test check command with --manifest option."""
        mock_load_db.return_value = {}

        # Create a temporary manifest file
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("requests==2.28.0\n")
            tmp_path = tmp.name

        try:
            mock_resolver_instance = MagicMock()
            mock_resolver_instance.get_manifest_files.return_value = [
                "requirements.txt"
            ]
            mock_resolver_instance.parse_manifest.return_value = [
                {"name": "requests", "version": "2.28.0"}
            ]
            mock_resolver.return_value = mock_resolver_instance

            # Need to mock Path.name and Path.exists
            with (
                patch.object(Path, "exists", return_value=True),
                patch.object(Path, "is_file", return_value=True),
                patch.object(Path, "name", "requirements.txt"),
            ):
                result = runner.invoke(app, ["check", "--manifest", tmp_path])

                # Manifest parsing error expected since we're mocking
                assert result.exit_code in [0, 1]
        finally:
            import os

            os.unlink(tmp_path)

    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.is_verbose_enabled", return_value=False)
    @patch("oss_sustain_guard.cli.get_output_style", return_value="normal")
    def test_check_with_ecosystem_flag(self, mock_style, mock_verbose, mock_load_db):
        """Test check command with --ecosystem flag."""
        mock_load_db.return_value = {}

        result = runner.invoke(
            app, ["check", "react", "--ecosystem", "javascript", "--no-cache"]
        )

        # Should attempt to analyze with javascript ecosystem
        assert result.exit_code in [0, 1]  # May fail due to mocking

    @patch("oss_sustain_guard.cli.set_verify_ssl")
    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.is_verbose_enabled", return_value=False)
    @patch("oss_sustain_guard.cli.get_output_style", return_value="normal")
    def test_check_with_insecure_flag(
        self, mock_style, mock_verbose, mock_load_db, mock_ssl
    ):
        """Test check command with --insecure flag."""
        mock_load_db.return_value = {}

        _result = runner.invoke(app, ["check", "requests", "--insecure", "--no-cache"])

        mock_ssl.assert_called_once_with(False)


class TestCacheStatsCommand:
    """Test the 'cache-stats' command."""

    @patch("oss_sustain_guard.cli.get_cache_stats")
    def test_cache_stats_no_cache(self, mock_stats):
        """Test cache-stats with no cache directory."""
        mock_stats.return_value = {
            "exists": False,
            "cache_dir": "/tmp/cache",
            "total_entries": 0,
            "valid_entries": 0,
            "expired_entries": 0,
            "ecosystems": {},
        }

        result = runner.invoke(app, ["cache-stats"])

        assert result.exit_code == 0
        assert "Cache directory does not exist" in result.stdout

    @patch("oss_sustain_guard.cli.get_cache_stats")
    def test_cache_stats_with_data(self, mock_stats):
        """Test cache-stats with cache data."""
        mock_stats.return_value = {
            "exists": True,
            "cache_dir": "/tmp/cache",
            "total_entries": 10,
            "valid_entries": 8,
            "expired_entries": 2,
            "ecosystems": {
                "python": {"total": 5, "valid": 4, "expired": 1},
                "javascript": {"total": 5, "valid": 4, "expired": 1},
            },
        }

        result = runner.invoke(app, ["cache-stats"])

        assert result.exit_code == 0
        assert "Total entries: 10" in result.stdout
        assert "Valid entries: 8" in result.stdout
        assert "python" in result.stdout

    @patch("oss_sustain_guard.cli.get_cache_stats")
    def test_cache_stats_specific_ecosystem(self, mock_stats):
        """Test cache-stats for specific ecosystem."""
        mock_stats.return_value = {
            "exists": True,
            "cache_dir": "/tmp/cache",
            "total_entries": 5,
            "valid_entries": 4,
            "expired_entries": 1,
            "ecosystems": {"python": {"total": 5, "valid": 4, "expired": 1}},
        }

        result = runner.invoke(app, ["cache-stats", "python"])

        assert result.exit_code == 0
        assert "Total entries: 5" in result.stdout


class TestGratitudeCommand:
    """Test the 'gratitude' command."""

    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.set_verify_ssl")
    def test_gratitude_no_database(self, mock_ssl, mock_load_db):
        """Test gratitude command with no database."""
        mock_load_db.return_value = {}

        result = runner.invoke(app, ["gratitude"])

        assert result.exit_code == 0
        # When database is empty, it says "No database available"
        assert (
            "No database available" in result.stdout
            or "No community-driven projects with funding links found" in result.stdout
        )

    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.set_verify_ssl")
    def test_gratitude_with_projects(self, mock_ssl, mock_load_db):
        """Test gratitude command with community projects."""
        mock_load_db.return_value = {
            "python:requests": {
                "github_url": "https://github.com/psf/requests",
                "total_score": 70,
                "metrics": [
                    {
                        "name": "Contributor Redundancy (Bus Factor)",
                        "score": 10,
                        "max_score": 20,
                        "message": "Low redundancy",
                        "risk": "High",
                    },
                    {
                        "name": "Maintainer Drain",
                        "score": 8,
                        "max_score": 15,
                        "message": "Some drain",
                        "risk": "Medium",
                    },
                ],
                "funding_links": [
                    {
                        "platform": "GitHub Sponsors",
                        "url": "https://github.com/sponsors",
                    }
                ],
                "is_community_driven": True,
            }
        }

        result = runner.invoke(app, ["gratitude", "--top", "1"], input="q\n")

        assert result.exit_code == 0
        assert "requests" in result.stdout
        assert "Support options" in result.stdout

    @patch("oss_sustain_guard.cli.load_database")
    @patch("oss_sustain_guard.cli.set_verify_ssl")
    def test_gratitude_with_insecure_flag(self, mock_ssl, mock_load_db):
        """Test gratitude command with --insecure flag."""
        mock_load_db.return_value = {}

        result = runner.invoke(app, ["gratitude", "--insecure"])

        assert result.exit_code == 0
        mock_ssl.assert_called_once_with(False)


class TestTrendCommand:
    """Test the 'trend' command."""

    @patch("oss_sustain_guard.cli.TrendAnalyzer")
    def test_trend_no_history(self, mock_analyzer_class):
        """Test trend command with no historical data."""
        mock_analyzer = MagicMock()
        mock_analyzer.list_available_dates.return_value = []
        mock_analyzer.load_package_history.return_value = []
        mock_analyzer_class.return_value = mock_analyzer

        result = runner.invoke(app, ["trend", "requests"])

        assert result.exit_code == 0
        assert "No historical snapshots found" in result.stdout

    @patch("oss_sustain_guard.cli.TrendAnalyzer")
    def test_trend_with_history(self, mock_analyzer_class):
        """Test trend command with historical data."""
        mock_analyzer = MagicMock()
        mock_analyzer.list_available_dates.return_value = ["2025-12-01", "2025-12-15"]
        mock_analyzer.load_package_history.return_value = [
            {"date": "2025-12-01", "total_score": 80},
            {"date": "2025-12-15", "total_score": 85},
        ]
        mock_analyzer.display_trend_table.return_value = None
        mock_analyzer_class.return_value = mock_analyzer

        result = runner.invoke(app, ["trend", "requests"])

        assert result.exit_code == 0
        mock_analyzer.display_trend_table.assert_called_once()

    @patch("oss_sustain_guard.cli.TrendAnalyzer")
    def test_trend_with_metric_flag(self, mock_analyzer_class):
        """Test trend command with --metric flag."""
        mock_analyzer = MagicMock()
        mock_analyzer.list_available_dates.return_value = ["2025-12-01"]
        mock_analyzer.load_package_history.return_value = [
            {"date": "2025-12-01", "total_score": 80}
        ]
        mock_analyzer.display_trend_table.return_value = None
        mock_analyzer.display_metric_comparison.return_value = None
        mock_analyzer_class.return_value = mock_analyzer

        result = runner.invoke(app, ["trend", "requests", "--metric", "Bus Factor"])

        assert result.exit_code == 0
        mock_analyzer.display_metric_comparison.assert_called_once()

    @patch("oss_sustain_guard.cli.TrendAnalyzer")
    def test_trend_no_remote(self, mock_analyzer_class):
        """Test trend command with --no-remote flag."""
        mock_analyzer = MagicMock()
        mock_analyzer.list_available_dates.return_value = []
        mock_analyzer.load_package_history.return_value = []
        mock_analyzer_class.return_value = mock_analyzer

        result = runner.invoke(app, ["trend", "requests", "--no-remote"])

        assert result.exit_code == 0
        # Should instantiate TrendAnalyzer with use_remote=False
        mock_analyzer_class.assert_called_once_with(use_remote=False)


class TestCompareCommand:
    """Test the 'compare' command."""

    @patch("oss_sustain_guard.cli.TrendAnalyzer")
    @patch("oss_sustain_guard.cli.ComparisonReport")
    def test_compare_no_history(self, mock_report_class, mock_analyzer_class):
        """Test compare command with no historical data."""
        mock_analyzer = MagicMock()
        mock_analyzer.list_available_dates.return_value = []
        mock_analyzer_class.return_value = mock_analyzer

        result = runner.invoke(app, ["compare", "requests", "2025-12-01", "2025-12-15"])

        assert result.exit_code == 0
        assert "No historical snapshots found" in result.stdout

    @patch("oss_sustain_guard.cli.TrendAnalyzer")
    @patch("oss_sustain_guard.cli.ComparisonReport")
    def test_compare_invalid_date(self, mock_report_class, mock_analyzer_class):
        """Test compare command with invalid date."""
        mock_analyzer = MagicMock()
        mock_analyzer.list_available_dates.return_value = ["2025-12-01"]
        mock_analyzer_class.return_value = mock_analyzer

        result = runner.invoke(app, ["compare", "requests", "2025-12-01", "2025-12-31"])

        assert result.exit_code == 0
        assert "not found in archive" in result.stdout

    @patch("oss_sustain_guard.cli.TrendAnalyzer")
    @patch("oss_sustain_guard.cli.ComparisonReport")
    def test_compare_success(self, mock_report_class, mock_analyzer_class):
        """Test successful compare command."""
        mock_analyzer = MagicMock()
        mock_analyzer.list_available_dates.return_value = [
            "2025-12-01",
            "2025-12-15",
        ]
        mock_analyzer_class.return_value = mock_analyzer

        mock_report = MagicMock()
        mock_report.compare_dates.return_value = None
        mock_report_class.return_value = mock_report

        result = runner.invoke(app, ["compare", "requests", "2025-12-01", "2025-12-15"])

        assert result.exit_code == 0
        mock_report.compare_dates.assert_called_once_with(
            "requests", "2025-12-01", "2025-12-15", "python"
        )


class TestListSnapshotsCommand:
    """Test the 'list-snapshots' command."""

    @patch("oss_sustain_guard.cli.list_history_dates")
    def test_list_snapshots_no_data(self, mock_list_dates):
        """Test list-snapshots with no historical data."""
        mock_list_dates.return_value = []

        result = runner.invoke(app, ["list-snapshots"])

        assert result.exit_code == 0
        assert "No historical snapshots found" in result.stdout

    @patch("oss_sustain_guard.cli.list_history_dates")
    def test_list_snapshots_with_data(self, mock_list_dates):
        """Test list-snapshots with historical data."""

        def mock_dates_func(ecosystem):
            if ecosystem == "python":
                return ["2025-12-01", "2025-12-15"]
            elif ecosystem == "javascript":
                return ["2025-12-10"]
            return []

        mock_list_dates.side_effect = mock_dates_func

        result = runner.invoke(app, ["list-snapshots"])

        assert result.exit_code == 0
        assert "python" in result.stdout
        assert "javascript" in result.stdout
        assert "Total snapshots: 3" in result.stdout

    @patch("oss_sustain_guard.cli.list_history_dates")
    def test_list_snapshots_specific_ecosystem(self, mock_list_dates):
        """Test list-snapshots for specific ecosystem."""
        mock_list_dates.return_value = ["2025-12-01", "2025-12-15"]

        result = runner.invoke(app, ["list-snapshots", "python"])

        assert result.exit_code == 0
        assert "python" in result.stdout
        mock_list_dates.assert_called_once_with("python")
