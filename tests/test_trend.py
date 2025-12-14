"""Tests for trend analysis and comparison functionality."""

import json

import pytest

from oss_sustain_guard.trend import ComparisonReport, TrendAnalyzer, TrendData


@pytest.fixture
def temp_archive_dir(tmp_path):
    """Create a temporary archive directory with sample data."""
    archive = tmp_path / "archive"
    archive.mkdir()

    # Create sample snapshots
    dates = ["2025-12-11", "2025-12-12"]

    for date in dates:
        date_dir = archive / date
        date_dir.mkdir()

        # Create sample Python ecosystem data
        python_data = {
            "_ecosystem": "python",
            "_generated_at": f"{date}T10:00:00+00:00",
            "_schema_version": "2.0",
            "packages": {
                "python:requests": {
                    "ecosystem": "python",
                    "github_url": "https://github.com/psf/requests",
                    "total_score": 75 if date == "2025-12-11" else 80,
                    "metrics": [
                        {
                            "name": "Contributor Redundancy",
                            "score": 15 if date == "2025-12-11" else 18,
                            "max_score": 20,
                            "message": "Healthy contributors",
                            "risk": "Low",
                        },
                        {
                            "name": "Recent Activity",
                            "score": 20,
                            "max_score": 20,
                            "message": "Recently active",
                            "risk": "None",
                        },
                    ],
                },
                "python:flask": {
                    "ecosystem": "python",
                    "github_url": "https://github.com/pallets/flask",
                    "total_score": 85 if date == "2025-12-11" else 82,
                    "metrics": [
                        {
                            "name": "Contributor Redundancy",
                            "score": 18,
                            "max_score": 20,
                            "message": "Healthy contributors",
                            "risk": "None",
                        },
                        {
                            "name": "Recent Activity",
                            "score": 20 if date == "2025-12-11" else 18,
                            "max_score": 20,
                            "message": "Recently active",
                            "risk": "None",
                        },
                    ],
                },
            },
        }

        python_file = date_dir / "python.json"
        with open(python_file, "w", encoding="utf-8") as f:
            json.dump(python_data, f, indent=2)

    return archive


class TestTrendAnalyzer:
    """Test TrendAnalyzer functionality."""

    def test_list_available_dates(self, temp_archive_dir):
        """Test listing available snapshot dates."""
        analyzer = TrendAnalyzer(archive_dir=temp_archive_dir)
        dates = analyzer.list_available_dates()

        assert len(dates) == 2
        assert "2025-12-11" in dates
        assert "2025-12-12" in dates
        assert dates == sorted(dates)

    def test_list_available_dates_empty(self, tmp_path):
        """Test listing dates when archive is empty."""
        empty_archive = tmp_path / "empty_archive"
        empty_archive.mkdir()

        analyzer = TrendAnalyzer(archive_dir=empty_archive)
        dates = analyzer.list_available_dates()

        assert dates == []

    def test_list_available_dates_nonexistent(self, tmp_path):
        """Test listing dates when archive doesn't exist."""
        nonexistent = tmp_path / "nonexistent"

        analyzer = TrendAnalyzer(archive_dir=nonexistent)
        dates = analyzer.list_available_dates()

        assert dates == []

    def test_is_valid_date_format(self):
        """Test date format validation."""
        assert TrendAnalyzer._is_valid_date_format("2025-12-11") is True
        assert TrendAnalyzer._is_valid_date_format("2025-12-31") is True
        assert TrendAnalyzer._is_valid_date_format("invalid") is False
        assert TrendAnalyzer._is_valid_date_format("2025-13-01") is False
        assert TrendAnalyzer._is_valid_date_format("2025-12-32") is False

    def test_load_package_history(self, temp_archive_dir):
        """Test loading package history across snapshots."""
        analyzer = TrendAnalyzer(archive_dir=temp_archive_dir)
        history = analyzer.load_package_history("requests", "python")

        assert len(history) == 2
        assert history[0].date == "2025-12-11"
        assert history[1].date == "2025-12-12"
        assert history[0].package_name == "requests"
        assert history[0].total_score == 75
        assert history[1].total_score == 80

    def test_load_package_history_nonexistent_package(self, temp_archive_dir):
        """Test loading history for non-existent package."""
        analyzer = TrendAnalyzer(archive_dir=temp_archive_dir)
        history = analyzer.load_package_history("nonexistent", "python")

        assert history == []

    def test_load_package_history_partial_data(self, temp_archive_dir):
        """Test loading history when package only exists in some snapshots."""
        # Add a third date with only flask (not requests)
        date_dir = temp_archive_dir / "2025-12-13"
        date_dir.mkdir()

        python_data = {
            "_ecosystem": "python",
            "_generated_at": "2025-12-13T10:00:00+00:00",
            "_schema_version": "2.0",
            "packages": {
                "python:flask": {
                    "ecosystem": "python",
                    "github_url": "https://github.com/pallets/flask",
                    "total_score": 90,
                    "metrics": [],
                }
            },
        }

        python_file = date_dir / "python.json"
        with open(python_file, "w", encoding="utf-8") as f:
            json.dump(python_data, f, indent=2)

        analyzer = TrendAnalyzer(archive_dir=temp_archive_dir)

        # requests should have 2 entries
        requests_history = analyzer.load_package_history("requests", "python")
        assert len(requests_history) == 2

        # flask should have 3 entries
        flask_history = analyzer.load_package_history("flask", "python")
        assert len(flask_history) == 3

    def test_calculate_trend_improving(self, temp_archive_dir):
        """Test trend calculation for improving package."""
        analyzer = TrendAnalyzer(archive_dir=temp_archive_dir)
        history = analyzer.load_package_history("requests", "python")

        trend_stats = analyzer.calculate_trend(history)

        assert trend_stats["first_score"] == 75
        assert trend_stats["last_score"] == 80
        assert trend_stats["change"] == 5
        assert trend_stats["change_pct"] > 0
        assert trend_stats["trend"] == "stable"  # Change is exactly 5, not > 5
        assert trend_stats["avg_score"] == 77  # (75 + 80) // 2

    def test_calculate_trend_degrading(self, temp_archive_dir):
        """Test trend calculation for degrading package."""
        analyzer = TrendAnalyzer(archive_dir=temp_archive_dir)
        history = analyzer.load_package_history("flask", "python")

        trend_stats = analyzer.calculate_trend(history)

        assert trend_stats["first_score"] == 85
        assert trend_stats["last_score"] == 82
        assert trend_stats["change"] == -3
        assert trend_stats["change_pct"] < 0
        assert trend_stats["trend"] == "stable"  # Change is > -5
        assert trend_stats["avg_score"] == 83  # (85 + 82) // 2

    def test_calculate_trend_empty(self):
        """Test trend calculation with empty history."""
        analyzer = TrendAnalyzer()
        trend_stats = analyzer.calculate_trend([])

        assert trend_stats["first_score"] == 0
        assert trend_stats["last_score"] == 0
        assert trend_stats["change"] == 0
        assert trend_stats["change_pct"] == 0.0
        assert trend_stats["trend"] == "unknown"
        assert trend_stats["avg_score"] == 0

    def test_calculate_trend_large_improvement(self, tmp_path):
        """Test trend calculation with large improvement."""
        # Create test data with large improvement
        archive = tmp_path / "archive"
        archive.mkdir()

        for date, score in [("2025-12-11", 50), ("2025-12-12", 70)]:
            date_dir = archive / date
            date_dir.mkdir()

            data = {
                "packages": {
                    "python:test-pkg": {
                        "total_score": score,
                        "github_url": "https://github.com/test/pkg",
                        "metrics": [],
                    }
                }
            }

            with open(date_dir / "python.json", "w", encoding="utf-8") as f:
                json.dump(data, f)

        analyzer = TrendAnalyzer(archive_dir=archive)
        history = analyzer.load_package_history("test-pkg", "python")
        trend_stats = analyzer.calculate_trend(history)

        assert trend_stats["change"] == 20
        assert trend_stats["trend"] == "improving"  # change > 5


class TestTrendData:
    """Test TrendData data structure."""

    def test_trend_data_creation(self):
        """Test creating TrendData object."""
        trend = TrendData(
            date="2025-12-11",
            package_name="requests",
            total_score=75,
            metrics=[{"name": "Test", "score": 10}],
            github_url="https://github.com/psf/requests",
        )

        assert trend.date == "2025-12-11"
        assert trend.package_name == "requests"
        assert trend.total_score == 75
        assert len(trend.metrics) == 1
        assert trend.github_url == "https://github.com/psf/requests"

    def test_trend_data_repr(self):
        """Test TrendData string representation."""
        trend = TrendData(
            date="2025-12-11",
            package_name="requests",
            total_score=75,
            metrics=[],
            github_url="https://github.com/psf/requests",
        )

        repr_str = repr(trend)
        assert "2025-12-11" in repr_str
        assert "requests" in repr_str
        assert "75" in repr_str


class TestComparisonReport:
    """Test ComparisonReport functionality."""

    def test_comparison_report_creation(self, temp_archive_dir):
        """Test creating ComparisonReport."""
        analyzer = TrendAnalyzer(archive_dir=temp_archive_dir)
        reporter = ComparisonReport(analyzer)

        assert reporter.analyzer == analyzer
        assert reporter.console is not None

    def test_compare_dates_valid(self, temp_archive_dir, capsys):
        """Test comparing valid dates."""
        analyzer = TrendAnalyzer(archive_dir=temp_archive_dir)
        reporter = ComparisonReport(analyzer)

        # This should not raise an error
        reporter.compare_dates("requests", "2025-12-11", "2025-12-12", "python")

        # Check that output was generated (just verify no errors)
        # Actual output testing would require mocking Rich console

    def test_compare_dates_no_history(self, temp_archive_dir, capsys):
        """Test comparing dates when package has no history."""
        analyzer = TrendAnalyzer(archive_dir=temp_archive_dir)
        reporter = ComparisonReport(analyzer)

        # Should handle gracefully
        reporter.compare_dates("nonexistent", "2025-12-11", "2025-12-12", "python")

    def test_compare_dates_missing_snapshot(self, temp_archive_dir, capsys):
        """Test comparing when one date is missing."""
        analyzer = TrendAnalyzer(archive_dir=temp_archive_dir)
        reporter = ComparisonReport(analyzer)

        # Should handle gracefully
        reporter.compare_dates("requests", "2025-12-11", "2025-12-20", "python")


class TestIntegration:
    """Integration tests for trend analysis workflow."""

    def test_full_workflow(self, temp_archive_dir):
        """Test complete trend analysis workflow."""
        analyzer = TrendAnalyzer(archive_dir=temp_archive_dir)

        # Step 1: List dates
        dates = analyzer.list_available_dates()
        assert len(dates) >= 2

        # Step 2: Load history
        history = analyzer.load_package_history("requests", "python")
        assert len(history) >= 2

        # Step 3: Calculate trends
        trend_stats = analyzer.calculate_trend(history)
        assert "first_score" in trend_stats
        assert "last_score" in trend_stats
        assert "trend" in trend_stats

        # Step 4: Generate report
        reporter = ComparisonReport(analyzer)
        # Just ensure it doesn't crash
        reporter.compare_dates("requests", dates[0], dates[1], "python")
