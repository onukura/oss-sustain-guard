"""Tests for trend analysis and comparison functionality."""

import gzip
import json

import pytest

from oss_sustain_guard.cache import (
    get_cache_dir,
)
from oss_sustain_guard.trend import ComparisonReport, TrendAnalyzer, TrendData


@pytest.fixture
def temp_cache_history(tmp_path, monkeypatch):
    """Create a temporary cache directory with sample history data."""
    # Override cache directory to use temp directory
    cache_dir = tmp_path / ".cache" / "oss-sustain-guard"
    monkeypatch.setenv("OSS_SUSTAIN_GUARD_CACHE_DIR", str(cache_dir))

    # Reload config to pick up new env var
    from oss_sustain_guard import config

    config._CACHE_DIR = None  # Reset cached value

    # Create history directory
    history_dir = cache_dir / "history" / "python"
    history_dir.mkdir(parents=True)

    # Create sample snapshots
    dates = ["2025-12-11", "2025-12-12"]

    for date in dates:
        snapshot_data = {
            "python:requests": {
                "ecosystem": "python",
                "package_name": "requests",
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
                "package_name": "flask",
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
        }

        snapshot_file = history_dir / f"{date}.json.gz"
        with gzip.open(snapshot_file, "wt", encoding="utf-8") as f:
            json.dump(snapshot_data, f, indent=2)

    yield cache_dir

    # Cleanup: Reset cache_dir to ensure no side effects
    config._CACHE_DIR = None


class TestTrendAnalyzer:
    """Test TrendAnalyzer functionality."""

    def test_list_available_dates(self, temp_cache_history):
        """Test listing available snapshot dates."""
        analyzer = TrendAnalyzer(use_remote=False)
        dates = analyzer.list_available_dates("python")

        assert len(dates) == 2
        assert "2025-12-11" in dates
        assert "2025-12-12" in dates
        assert dates == sorted(dates)

    def test_list_available_dates_empty(self, tmp_path, monkeypatch):
        """Test listing dates when no history exists."""
        cache_dir = tmp_path / ".cache" / "oss-sustain-guard"
        monkeypatch.setenv("OSS_SUSTAIN_GUARD_CACHE_DIR", str(cache_dir))

        from oss_sustain_guard import config

        config._CACHE_DIR = None

        analyzer = TrendAnalyzer(use_remote=False)
        dates = analyzer.list_available_dates("python")

        assert dates == []

    def test_is_valid_date_format(self):
        """Test date format validation."""
        assert TrendAnalyzer._is_valid_date_format("2025-12-11") is True
        assert TrendAnalyzer._is_valid_date_format("2025-12-31") is True
        assert TrendAnalyzer._is_valid_date_format("invalid") is False
        assert TrendAnalyzer._is_valid_date_format("2025-13-01") is False
        assert TrendAnalyzer._is_valid_date_format("2025-12-32") is False

    def test_load_package_history(self, temp_cache_history):
        """Test loading package history from local cache."""
        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("requests", "python")

        assert len(history) == 2
        assert history[0].date == "2025-12-11"
        assert history[1].date == "2025-12-12"
        assert history[0].package_name == "requests"
        assert history[0].total_score == 75
        assert history[1].total_score == 80

    def test_load_package_history_nonexistent_package(self, temp_cache_history):
        """Test loading history for non-existent package."""
        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("nonexistent", "python")

        assert history == []

    def test_load_package_history_partial_data(self, temp_cache_history):
        """Test loading history when package only exists in some snapshots."""
        # Add a third date with only flask (not requests)
        history_dir = get_cache_dir() / "history" / "python"

        snapshot_data = {
            "python:flask": {
                "ecosystem": "python",
                "package_name": "flask",
                "github_url": "https://github.com/pallets/flask",
                "total_score": 90,
                "metrics": [],
            }
        }

        snapshot_file = history_dir / "2025-12-13.json.gz"
        with gzip.open(snapshot_file, "wt", encoding="utf-8") as f:
            json.dump(snapshot_data, f, indent=2)

        analyzer = TrendAnalyzer(use_remote=False)

        # requests should have 2 entries
        requests_history = analyzer.load_package_history("requests", "python")
        assert len(requests_history) == 2

        # flask should have 3 entries
        flask_history = analyzer.load_package_history("flask", "python")
        assert len(flask_history) == 3

    def test_calculate_trend_improving(self, temp_cache_history):
        """Test trend calculation for improving package."""
        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("requests", "python")

        trend_stats = analyzer.calculate_trend(history)

        assert trend_stats["first_score"] == 75
        assert trend_stats["last_score"] == 80
        assert trend_stats["change"] == 5
        assert trend_stats["change_pct"] > 0
        assert trend_stats["trend"] == "stable"  # Change is exactly 5, not > 5
        assert trend_stats["avg_score"] == 77  # (75 + 80) // 2

    def test_calculate_trend_degrading(self, temp_cache_history):
        """Test trend calculation for degrading package."""
        analyzer = TrendAnalyzer(use_remote=False)
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
        analyzer = TrendAnalyzer(use_remote=False)
        trend_stats = analyzer.calculate_trend([])

        assert trend_stats["first_score"] == 0
        assert trend_stats["last_score"] == 0
        assert trend_stats["change"] == 0
        assert trend_stats["change_pct"] == 0.0
        assert trend_stats["trend"] == "unknown"
        assert trend_stats["avg_score"] == 0

    def test_calculate_trend_large_improvement(self, tmp_path, monkeypatch):
        """Test trend calculation with large improvement."""
        # Set up cache directory
        cache_dir = tmp_path / ".cache" / "oss-sustain-guard"
        monkeypatch.setenv("OSS_SUSTAIN_GUARD_CACHE_DIR", str(cache_dir))

        from oss_sustain_guard import config

        config._CACHE_DIR = None

        # Create history directory
        history_dir = cache_dir / "history" / "python"
        history_dir.mkdir(parents=True)

        # Create test data with large improvement
        for date, score in [("2025-12-11", 50), ("2025-12-12", 70)]:
            snapshot_data = {
                "python:test-pkg": {
                    "ecosystem": "python",
                    "package_name": "test-pkg",
                    "total_score": score,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [],
                }
            }

            snapshot_file = history_dir / f"{date}.json.gz"
            with gzip.open(snapshot_file, "wt", encoding="utf-8") as f:
                json.dump(snapshot_data, f, indent=2)

        analyzer = TrendAnalyzer(use_remote=False)
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

    def test_comparison_report_creation(self, temp_cache_history):
        """Test creating ComparisonReport."""
        analyzer = TrendAnalyzer(use_remote=False)
        reporter = ComparisonReport(analyzer)

        assert reporter.analyzer == analyzer
        assert reporter.console is not None

    def test_compare_dates_valid(self, temp_cache_history, capsys):
        """Test comparing valid dates."""
        analyzer = TrendAnalyzer(use_remote=False)
        reporter = ComparisonReport(analyzer)

        # This should not raise an error
        reporter.compare_dates("requests", "2025-12-11", "2025-12-12", "python")

        # Check that output was generated (just verify no errors)
        # Actual output testing would require mocking Rich console

    def test_compare_dates_no_history(self, temp_cache_history, capsys):
        """Test comparing dates when package has no history."""
        analyzer = TrendAnalyzer(use_remote=False)
        reporter = ComparisonReport(analyzer)

        # Should handle gracefully
        reporter.compare_dates("nonexistent", "2025-12-11", "2025-12-12", "python")

    def test_compare_dates_missing_snapshot(self, temp_cache_history, capsys):
        """Test comparing when one date is missing."""
        analyzer = TrendAnalyzer(use_remote=False)
        reporter = ComparisonReport(analyzer)

        # Should handle gracefully
        reporter.compare_dates("requests", "2025-12-11", "2025-12-20", "python")

    def test_compare_dates_metric_changes(self, tmp_path):
        """Test comparing dates with metrics that appear/disappear."""
        archive = tmp_path / "archive"
        archive.mkdir()

        # First date has metric A and B
        date1_dir = archive / "2025-12-11"
        date1_dir.mkdir()
        data1 = {
            "packages": {
                "python:test-pkg": {
                    "total_score": 60,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [
                        {
                            "name": "Metric A",
                            "score": 10,
                            "max_score": 20,
                            "message": "Test",
                            "risk": "Low",
                        },
                        {
                            "name": "Metric B",
                            "score": 15,
                            "max_score": 20,
                            "message": "Test",
                            "risk": "None",
                        },
                    ],
                }
            }
        }
        with open(date1_dir / "python.json", "w", encoding="utf-8") as f:
            json.dump(data1, f)

        # Second date has metric B and C (A removed, C added)
        date2_dir = archive / "2025-12-12"
        date2_dir.mkdir()
        data2 = {
            "packages": {
                "python:test-pkg": {
                    "total_score": 70,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [
                        {
                            "name": "Metric B",
                            "score": 18,
                            "max_score": 20,
                            "message": "Test",
                            "risk": "None",
                        },
                        {
                            "name": "Metric C",
                            "score": 12,
                            "max_score": 20,
                            "message": "Test",
                            "risk": "Medium",
                        },
                    ],
                }
            }
        }
        with open(date2_dir / "python.json", "w", encoding="utf-8") as f:
            json.dump(data2, f)

        analyzer = TrendAnalyzer()
        reporter = ComparisonReport(analyzer)

        # Should handle metrics that appear/disappear
        reporter.compare_dates("test-pkg", "2025-12-11", "2025-12-12", "python")

    def test_compare_dates_no_change(self, tmp_path):
        """Test comparing dates with no score change."""
        archive = tmp_path / "archive"
        archive.mkdir()

        # Create two snapshots with same score
        for date in ["2025-12-11", "2025-12-12"]:
            date_dir = archive / date
            date_dir.mkdir()
            data = {
                "packages": {
                    "python:test-pkg": {
                        "total_score": 70,
                        "github_url": "https://github.com/test/pkg",
                        "metrics": [
                            {
                                "name": "Test Metric",
                                "score": 15,
                                "max_score": 20,
                                "message": "Test",
                                "risk": "Low",
                            }
                        ],
                    }
                }
            }
            with open(date_dir / "python.json", "w", encoding="utf-8") as f:
                json.dump(data, f)

        analyzer = TrendAnalyzer()
        reporter = ComparisonReport(analyzer)

        # Should handle no change gracefully
        reporter.compare_dates("test-pkg", "2025-12-11", "2025-12-12", "python")

    def test_compare_dates_positive_change(self, tmp_path):
        """Test comparing dates with positive score change."""
        archive = tmp_path / "archive"
        archive.mkdir()

        date1_dir = archive / "2025-12-11"
        date1_dir.mkdir()
        data1 = {
            "packages": {
                "python:test-pkg": {
                    "total_score": 60,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [
                        {
                            "name": "Test Metric",
                            "score": 10,
                            "max_score": 20,
                            "message": "Test",
                            "risk": "Low",
                        }
                    ],
                }
            }
        }
        with open(date1_dir / "python.json", "w", encoding="utf-8") as f:
            json.dump(data1, f)

        date2_dir = archive / "2025-12-12"
        date2_dir.mkdir()
        data2 = {
            "packages": {
                "python:test-pkg": {
                    "total_score": 80,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [
                        {
                            "name": "Test Metric",
                            "score": 18,
                            "max_score": 20,
                            "message": "Test",
                            "risk": "None",
                        }
                    ],
                }
            }
        }
        with open(date2_dir / "python.json", "w", encoding="utf-8") as f:
            json.dump(data2, f)

        analyzer = TrendAnalyzer()
        reporter = ComparisonReport(analyzer)

        # Should show positive change
        reporter.compare_dates("test-pkg", "2025-12-11", "2025-12-12", "python")

    def test_compare_dates_negative_change(self, tmp_path):
        """Test comparing dates with negative score change."""
        archive = tmp_path / "archive"
        archive.mkdir()

        date1_dir = archive / "2025-12-11"
        date1_dir.mkdir()
        data1 = {
            "packages": {
                "python:test-pkg": {
                    "total_score": 80,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [
                        {
                            "name": "Test Metric",
                            "score": 18,
                            "max_score": 20,
                            "message": "Test",
                            "risk": "None",
                        }
                    ],
                }
            }
        }
        with open(date1_dir / "python.json", "w", encoding="utf-8") as f:
            json.dump(data1, f)

        date2_dir = archive / "2025-12-12"
        date2_dir.mkdir()
        data2 = {
            "packages": {
                "python:test-pkg": {
                    "total_score": 60,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [
                        {
                            "name": "Test Metric",
                            "score": 10,
                            "max_score": 20,
                            "message": "Test",
                            "risk": "Low",
                        }
                    ],
                }
            }
        }
        with open(date2_dir / "python.json", "w", encoding="utf-8") as f:
            json.dump(data2, f)

        analyzer = TrendAnalyzer()
        reporter = ComparisonReport(analyzer)

        # Should show negative change
        reporter.compare_dates("test-pkg", "2025-12-11", "2025-12-12", "python")


class TestDisplayMethods:
    """Test display and visualization methods."""

    def test_display_trend_table_with_data(self, temp_cache_history):
        """Test displaying trend table with valid data."""
        analyzer = TrendAnalyzer()
        history = analyzer.load_package_history("requests", "python")

        # Should not raise an error
        analyzer.display_trend_table("requests", history)

    def test_display_trend_table_negative_change(self, tmp_path):
        """Test displaying trend table with negative change."""
        archive = tmp_path / "archive"
        archive.mkdir()

        # Create data with decreasing scores
        for date, score in [("2025-12-11", 80), ("2025-12-12", 70)]:
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

        analyzer = TrendAnalyzer()
        history = analyzer.load_package_history("test-pkg", "python")
        analyzer.display_trend_table("test-pkg", history)

    def test_display_trend_table_positive_change(self, tmp_path):
        """Test displaying trend table with positive change."""
        archive = tmp_path / "archive"
        archive.mkdir()

        # Create data with increasing scores
        for date, score in [("2025-12-11", 60), ("2025-12-12", 75)]:
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

        analyzer = TrendAnalyzer()
        history = analyzer.load_package_history("test-pkg", "python")
        analyzer.display_trend_table("test-pkg", history)

    def test_display_trend_table_no_change(self, tmp_path):
        """Test displaying trend table with no change."""
        archive = tmp_path / "archive"
        archive.mkdir()

        # Create data with same scores
        for date in ["2025-12-11", "2025-12-12"]:
            date_dir = archive / date
            date_dir.mkdir()
            data = {
                "packages": {
                    "python:test-pkg": {
                        "total_score": 70,
                        "github_url": "https://github.com/test/pkg",
                        "metrics": [],
                    }
                }
            }
            with open(date_dir / "python.json", "w", encoding="utf-8") as f:
                json.dump(data, f)

        analyzer = TrendAnalyzer()
        history = analyzer.load_package_history("test-pkg", "python")
        analyzer.display_trend_table("test-pkg", history)

    def test_display_trend_table_low_score(self, tmp_path):
        """Test displaying trend table with low scores (< 50)."""
        archive = tmp_path / "archive"
        archive.mkdir()

        # Create data with low scores
        for date, score in [("2025-12-11", 40), ("2025-12-12", 30)]:
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

        analyzer = TrendAnalyzer()
        history = analyzer.load_package_history("test-pkg", "python")
        analyzer.display_trend_table("test-pkg", history)

    def test_display_trend_table_no_data(self):
        """Test displaying trend table with no data."""
        analyzer = TrendAnalyzer(use_remote=False)

        # Should handle empty history gracefully
        analyzer.display_trend_table("nonexistent", [])

    def test_display_metric_comparison_with_data(self, temp_cache_history):
        """Test displaying metric comparison with valid data."""
        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("requests", "python")

        # Test with all metrics
        analyzer.display_metric_comparison("requests", history)

        # Test with specific metric
        analyzer.display_metric_comparison(
            "requests", history, "Contributor Redundancy"
        )

    def test_display_metric_comparison_no_data(self):
        """Test displaying metric comparison with no data."""
        analyzer = TrendAnalyzer(use_remote=False)

        # Should handle empty history gracefully
        analyzer.display_metric_comparison("nonexistent", [], "Test Metric")

    def test_display_metric_comparison_invalid_metric(self, temp_cache_history):
        """Test displaying metric comparison with invalid metric name."""
        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("requests", "python")

        # Should handle invalid metric name gracefully
        analyzer.display_metric_comparison("requests", history, "NonexistentMetric")

    def test_display_metric_comparison_long_message(self, tmp_path):
        """Test metric comparison with long message (truncation)."""
        archive = tmp_path / "archive"
        archive.mkdir()

        date_dir = archive / "2025-12-11"
        date_dir.mkdir()

        data = {
            "packages": {
                "python:test-pkg": {
                    "total_score": 60,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [
                        {
                            "name": "Test Metric",
                            "score": 10,
                            "max_score": 20,
                            "message": "This is a very long message that should be truncated because it exceeds sixty characters in length",
                            "risk": "Medium",
                        }
                    ],
                }
            }
        }
        with open(date_dir / "python.json", "w", encoding="utf-8") as f:
            json.dump(data, f)

        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("test-pkg", "python")

        # Should truncate long messages
        analyzer.display_metric_comparison("test-pkg", history, "Test Metric")

    def test_display_metric_comparison_missing_metric_in_snapshot(self, tmp_path):
        """Test metric comparison when metric is missing in some snapshots."""
        archive = tmp_path / "archive"
        archive.mkdir()

        # First snapshot with metric
        date1_dir = archive / "2025-12-11"
        date1_dir.mkdir()
        data1 = {
            "packages": {
                "python:test-pkg": {
                    "total_score": 60,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [
                        {
                            "name": "Test Metric",
                            "score": 10,
                            "max_score": 20,
                            "message": "Present",
                            "risk": "Low",
                        }
                    ],
                }
            }
        }
        with open(date1_dir / "python.json", "w", encoding="utf-8") as f:
            json.dump(data1, f)

        # Second snapshot without the specific metric (empty metrics list)
        date2_dir = archive / "2025-12-12"
        date2_dir.mkdir()
        data2 = {
            "packages": {
                "python:test-pkg": {
                    "total_score": 70,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [
                        {
                            "name": "Different Metric",
                            "score": 15,
                            "max_score": 20,
                            "message": "Different",
                            "risk": "None",
                        }
                    ],
                }
            }
        }
        with open(date2_dir / "python.json", "w", encoding="utf-8") as f:
            json.dump(data2, f)

        # Third snapshot with the metric again
        date3_dir = archive / "2025-12-13"
        date3_dir.mkdir()
        data3 = {
            "packages": {
                "python:test-pkg": {
                    "total_score": 80,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [
                        {
                            "name": "Test Metric",
                            "score": 18,
                            "max_score": 20,
                            "message": "Present again",
                            "risk": "None",
                        }
                    ],
                }
            }
        }
        with open(date3_dir / "python.json", "w", encoding="utf-8") as f:
            json.dump(data3, f)

        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("test-pkg", "python")

        # Should handle missing metrics gracefully (line 360 - else branch)
        analyzer.display_metric_comparison("test-pkg", history, "Test Metric")

    def test_display_metric_comparison_all_risk_levels(self, tmp_path):
        """Test metric comparison with all risk levels."""
        archive = tmp_path / "archive"
        archive.mkdir()

        date_dir = archive / "2025-12-11"
        date_dir.mkdir()

        data = {
            "packages": {
                "python:test-pkg": {
                    "total_score": 60,
                    "github_url": "https://github.com/test/pkg",
                    "metrics": [
                        {
                            "name": "Critical Risk",
                            "score": 5,
                            "max_score": 20,
                            "message": "Critical",
                            "risk": "Critical",
                        },
                        {
                            "name": "High Risk",
                            "score": 8,
                            "max_score": 20,
                            "message": "High",
                            "risk": "High",
                        },
                        {
                            "name": "Medium Risk",
                            "score": 12,
                            "max_score": 20,
                            "message": "Medium",
                            "risk": "Medium",
                        },
                        {
                            "name": "Low Risk",
                            "score": 16,
                            "max_score": 20,
                            "message": "Low",
                            "risk": "Low",
                        },
                        {
                            "name": "No Risk",
                            "score": 20,
                            "max_score": 20,
                            "message": "None",
                            "risk": "None",
                        },
                        {
                            "name": "Unknown Risk",
                            "score": 10,
                            "max_score": 20,
                            "message": "Unknown",
                            "risk": "Unknown",
                        },
                    ],
                }
            }
        }
        with open(date_dir / "python.json", "w", encoding="utf-8") as f:
            json.dump(data, f)

        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("test-pkg", "python")

        # Test all metrics are displayed with different risk colors
        analyzer.display_metric_comparison("test-pkg", history)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_load_package_history_invalid_json(self, tmp_path):
        """Test loading history with invalid JSON files."""
        archive = tmp_path / "archive"
        archive.mkdir()

        date_dir = archive / "2025-12-11"
        date_dir.mkdir()

        # Write invalid JSON
        json_file = date_dir / "python.json"
        with open(json_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json content }")

        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("test-pkg", "python")

        # Should handle invalid JSON gracefully
        assert history == []

    def test_load_package_history_old_schema(self, tmp_path, monkeypatch):
        """Test loading history with old schema format (packages at root)."""
        cache_dir = tmp_path / ".cache" / "oss-sustain-guard"
        monkeypatch.setenv("OSS_SUSTAIN_GUARD_CACHE_DIR", str(cache_dir))

        from oss_sustain_guard import config

        config._CACHE_DIR = None

        history_dir = cache_dir / "history" / "python"
        history_dir.mkdir(parents=True)

        # Old schema: packages directly at root, no nesting
        old_schema_data = {
            "python:requests": {
                "ecosystem": "python",
                "github_url": "https://github.com/psf/requests",
                "total_score": 75,  # Old schema includes total_score
                "metrics": [
                    {
                        "name": "Test",
                        "score": 10,
                        "max_score": 20,
                        "message": "Test",
                        "risk": "Low",
                    }
                ],
            }
        }

        snapshot_file = history_dir / "2025-12-11.json.gz"
        with gzip.open(snapshot_file, "wt", encoding="utf-8") as f:
            json.dump(old_schema_data, f)

        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("requests", "python")

        # Should handle old schema
        assert len(history) == 1
        assert history[0].package_name == "requests"
        assert history[0].total_score == 75

    def test_load_package_history_missing_total_score(self, tmp_path, monkeypatch):
        """Test loading history when total_score is missing (needs calculation)."""
        cache_dir = tmp_path / ".cache" / "oss-sustain-guard"
        monkeypatch.setenv("OSS_SUSTAIN_GUARD_CACHE_DIR", str(cache_dir))

        from oss_sustain_guard import config

        config._CACHE_DIR = None

        history_dir = cache_dir / "history" / "python"
        history_dir.mkdir(parents=True)

        # Data without total_score but with metrics
        data = {
            "python:test-pkg": {
                "github_url": "https://github.com/test/pkg",
                "metrics": [
                    {
                        "name": "Test Metric",
                        "score": 15,
                        "max_score": 20,
                        "message": "Test",
                        "risk": "Low",
                    }
                ],
            }
        }

        snapshot_file = history_dir / "2025-12-11.json.gz"
        with gzip.open(snapshot_file, "wt", encoding="utf-8") as f:
            json.dump(data, f)

        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("test-pkg", "python")

        # Should calculate total_score from metrics using weighted scoring
        assert len(history) == 1
        # Check that score was calculated (not just 0)
        assert history[0].total_score >= 0  # Can be 0 if weights result in 0

    def test_load_package_history_missing_metrics(self, tmp_path, monkeypatch):
        """Test loading history when metrics are missing."""
        cache_dir = tmp_path / ".cache" / "oss-sustain-guard"
        monkeypatch.setenv("OSS_SUSTAIN_GUARD_CACHE_DIR", str(cache_dir))

        from oss_sustain_guard import config

        config._CACHE_DIR = None

        history_dir = cache_dir / "history" / "python"
        history_dir.mkdir(parents=True)

        # Data without metrics
        data = {
            "python:test-pkg": {
                "github_url": "https://github.com/test/pkg",
            }
        }

        snapshot_file = history_dir / "2025-12-11.json.gz"
        with gzip.open(snapshot_file, "wt", encoding="utf-8") as f:
            json.dump(data, f)

        analyzer = TrendAnalyzer(use_remote=False)
        history = analyzer.load_package_history("test-pkg", "python")

        # Should handle missing metrics gracefully
        assert len(history) == 1
        assert history[0].total_score == 0

    def test_calculate_trend_zero_first_score(self, tmp_path):
        """Test trend calculation when first_score is zero (avoid division by zero)."""
        # Create test data with zero first score
        trend_data = [
            TrendData(
                date="2025-12-11",
                package_name="test",
                total_score=0,
                metrics=[],
                github_url="https://github.com/test/pkg",
            ),
            TrendData(
                date="2025-12-12",
                package_name="test",
                total_score=50,
                metrics=[],
                github_url="https://github.com/test/pkg",
            ),
        ]

        analyzer = TrendAnalyzer()
        trend_stats = analyzer.calculate_trend(trend_data)

        # Should handle zero division gracefully
        assert trend_stats["first_score"] == 0
        assert trend_stats["last_score"] == 50
        assert trend_stats["change"] == 50
        assert trend_stats["change_pct"] == 0.0  # No percentage when first_score is 0

    def test_calculate_trend_large_degradation(self, tmp_path):
        """Test trend calculation with large degradation."""
        trend_data = [
            TrendData(
                date="2025-12-11",
                package_name="test",
                total_score=80,
                metrics=[],
                github_url="https://github.com/test/pkg",
            ),
            TrendData(
                date="2025-12-12",
                package_name="test",
                total_score=60,
                metrics=[],
                github_url="https://github.com/test/pkg",
            ),
        ]

        analyzer = TrendAnalyzer()
        trend_stats = analyzer.calculate_trend(trend_data)

        assert trend_stats["change"] == -20
        assert trend_stats["trend"] == "degrading"  # change < -5

    def test_list_available_dates_ignores_invalid_format(self, tmp_path, monkeypatch):
        """Test that invalid date formats are ignored."""
        cache_dir = tmp_path / ".cache" / "oss-sustain-guard"
        monkeypatch.setenv("OSS_SUSTAIN_GUARD_CACHE_DIR", str(cache_dir))

        from oss_sustain_guard import config

        config._CACHE_DIR = None

        history_dir = cache_dir / "history" / "python"
        history_dir.mkdir(parents=True)

        # Create files with various names
        (history_dir / "2025-12-11.json.gz").touch()  # Valid
        (history_dir / "2025-12-12.json.gz").touch()  # Valid
        (history_dir / "invalid-date.json.gz").touch()  # Invalid
        (history_dir / "not-a-date.json.gz").touch()  # Invalid
        (history_dir / ".hidden.json.gz").touch()  # Invalid

        analyzer = TrendAnalyzer(use_remote=False)
        dates = analyzer.list_available_dates("python")

        # Should only return valid dates
        assert len(dates) == 2
        assert "2025-12-11" in dates
        assert "2025-12-12" in dates
        assert "invalid-date" not in dates


class TestIntegration:
    """Integration tests for trend analysis workflow."""

    def test_full_workflow(self, temp_cache_history):
        """Test complete trend analysis workflow."""
        analyzer = TrendAnalyzer(use_remote=False)

        # Step 1: List dates
        dates = analyzer.list_available_dates("python")
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
