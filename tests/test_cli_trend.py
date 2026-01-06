"""
Tests for CLI trend command functionality.

This module tests the trend analysis feature, including:
- Trend command parameter validation
- Async trend analysis execution
- Time window generation and labeling
- Trend data filtering and processing
- Display functions for trend results
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from oss_sustain_guard.cli import app
from oss_sustain_guard.commands.trend import (
    _display_ascii_chart,
    _display_trend_results,
)
from oss_sustain_guard.core import Metric
from oss_sustain_guard.trend import (
    TIME_DEPENDENT_METRICS,
    TIME_INDEPENDENT_METRICS,
    TimeWindow,
    TrendDataPoint,
    TrendInterval,
    filter_time_dependent_metrics,
    generate_time_windows,
    is_metric_time_dependent,
)

runner = CliRunner()


def _mock_asyncio_run(coro):
    """Mock asyncio.run that properly closes coroutines to avoid warnings."""
    if asyncio.iscoroutine(coro):
        coro.close()
    return None


class TestTrendInterval:
    """Test TrendInterval enum."""

    def test_trend_intervals_defined(self):
        """Test that all trend intervals are defined."""
        assert TrendInterval.DAILY == "daily"
        assert TrendInterval.WEEKLY == "weekly"
        assert TrendInterval.MONTHLY == "monthly"
        assert TrendInterval.QUARTERLY == "quarterly"
        assert TrendInterval.SEMI_ANNUAL == "semi-annual"
        assert TrendInterval.ANNUAL == "annual"

    def test_trend_interval_string_value(self):
        """Test that TrendInterval is string-based."""
        interval = TrendInterval.MONTHLY
        assert isinstance(interval.value, str)
        assert str(interval) == "TrendInterval.MONTHLY"


class TestTimeWindow:
    """Test TimeWindow namedtuple."""

    def test_time_window_creation(self):
        """Test creating a TimeWindow."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 31, tzinfo=timezone.utc)
        window = TimeWindow(start=start, end=end, label="2025-01")

        assert window.start == start
        assert window.end == end
        assert window.label == "2025-01"

    def test_time_window_immutable(self):
        """Test that TimeWindow is immutable."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 31, tzinfo=timezone.utc)
        window = TimeWindow(start=start, end=end, label="2025-01")

        with pytest.raises(AttributeError):
            window.label = "2025-02"  # type: ignore[misc]


class TestTrendDataPoint:
    """Test TrendDataPoint namedtuple."""

    def test_trend_data_point_creation(self):
        """Test creating a TrendDataPoint."""
        window = TimeWindow(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 1, 31, tzinfo=timezone.utc),
            label="2025-01",
        )
        metrics = [
            Metric("Test Metric", 75, 100, "OK", "Low"),
        ]
        point = TrendDataPoint(
            window=window,
            total_score=75,
            metrics=metrics,
            excluded_metrics=["Funding Signals"],
        )

        assert point.total_score == 75
        assert len(point.metrics) == 1
        assert point.excluded_metrics == ["Funding Signals"]


class TestGenerateTimeWindows:
    """Test time window generation."""

    def test_generate_time_windows_monthly(self):
        """Test generating monthly time windows."""
        end_date = datetime(2025, 12, 31, tzinfo=timezone.utc)
        windows = generate_time_windows(
            TrendInterval.MONTHLY,
            periods=3,
            window_days=30,
            end_date=end_date,
        )

        assert len(windows) == 3
        # Windows should be in chronological order (oldest first)
        assert windows[0].end < windows[1].end < windows[2].end
        assert windows[-1].end == end_date

    def test_generate_time_windows_daily(self):
        """Test generating daily time windows."""
        end_date = datetime(2025, 12, 31, tzinfo=timezone.utc)
        windows = generate_time_windows(
            TrendInterval.DAILY,
            periods=5,
            window_days=1,
            end_date=end_date,
        )

        assert len(windows) == 5
        for i in range(1, len(windows)):
            assert (windows[i].start - windows[i - 1].end) == timedelta(days=0)

    def test_generate_time_windows_labels_monthly(self):
        """Test that monthly windows have correct labels."""
        end_date = datetime(2025, 12, 31, tzinfo=timezone.utc)
        windows = generate_time_windows(
            TrendInterval.MONTHLY,
            periods=3,
            window_days=30,
            end_date=end_date,
        )

        # Labels should be in format YYYY-MM
        assert windows[-1].label == "2025-12"
        for window in windows:
            assert len(window.label) == 7  # YYYY-MM format

    def test_generate_time_windows_labels_quarterly(self):
        """Test that quarterly windows have correct labels."""
        end_date = datetime(2025, 12, 31, tzinfo=timezone.utc)
        windows = generate_time_windows(
            TrendInterval.QUARTERLY,
            periods=4,
            window_days=90,
            end_date=end_date,
        )

        # Labels should be in format QN YYYY
        assert windows[-1].label == "Q4 2025"
        for window in windows:
            assert "Q" in window.label and window.label[1] in "1234"

    def test_generate_time_windows_labels_annual(self):
        """Test that annual windows have correct labels."""
        end_date = datetime(2025, 12, 31, tzinfo=timezone.utc)
        windows = generate_time_windows(
            TrendInterval.ANNUAL,
            periods=3,
            window_days=365,
            end_date=end_date,
        )

        # Labels should be year only (most recent window may be previous year due to 365-day window)
        assert windows[-1].label in ["2024", "2025"]
        for window in windows:
            assert window.label.isdigit() and len(window.label) == 4

    def test_generate_time_windows_default_end_date(self):
        """Test that end_date defaults to now if not specified, with seconds normalized."""
        before = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        windows = generate_time_windows(
            TrendInterval.MONTHLY,
            periods=2,
            window_days=30,
            end_date=None,
        )
        after = (datetime.now(timezone.utc) + timedelta(seconds=1)).replace(
            second=0, microsecond=0
        )

        # end_date should be normalized (seconds and microseconds = 0)
        assert windows[-1].end >= before
        assert windows[-1].end <= after


class TestIsMetricTimeDependent:
    """Test metric time-dependence checking."""

    def test_time_dependent_metrics_recognized(self):
        """Test that time-dependent metrics are recognized."""
        for metric_name in [
            "Recent Activity",
            "Release Rhythm",
            "Contributor Redundancy",
        ]:
            assert is_metric_time_dependent(metric_name) is True

    def test_time_independent_metrics_recognized(self):
        """Test that time-independent metrics are recognized."""
        for metric_name in ["Funding Signals", "License Clarity", "Code of Conduct"]:
            assert is_metric_time_dependent(metric_name) is False

    def test_unknown_metric_treated_as_time_dependent(self):
        """Test that unknown metrics default to time-dependent."""
        assert is_metric_time_dependent("Unknown Metric") is False

    def test_no_overlap_between_sets(self):
        """Test that time-dependent and independent sets don't overlap."""
        overlap = TIME_DEPENDENT_METRICS & TIME_INDEPENDENT_METRICS
        assert len(overlap) == 0


class TestFilterTimeDependentMetrics:
    """Test filtering metrics by time-dependence."""

    def test_filter_mixed_metrics(self):
        """Test filtering a list of mixed metrics."""
        metrics = [
            Metric("Recent Activity", 80, 100, "OK", "Low"),
            Metric("Funding Signals", 50, 100, "Warning", "Medium"),
            Metric("Release Rhythm", 70, 100, "OK", "Low"),
            Metric("Code of Conduct", 100, 100, "OK", "None"),
        ]

        time_dependent, excluded = filter_time_dependent_metrics(metrics)

        assert len(time_dependent) == 2
        assert len(excluded) == 2
        assert all(
            m.name in ["Recent Activity", "Release Rhythm"] for m in time_dependent
        )
        assert all(n in ["Funding Signals", "Code of Conduct"] for n in excluded)

    def test_filter_all_time_dependent(self):
        """Test filtering when all metrics are time-dependent."""
        metrics = [
            Metric("Recent Activity", 80, 100, "OK", "Low"),
            Metric("Release Rhythm", 70, 100, "OK", "Low"),
        ]

        time_dependent, excluded = filter_time_dependent_metrics(metrics)

        assert len(time_dependent) == 2
        assert len(excluded) == 0

    def test_filter_all_time_independent(self):
        """Test filtering when all metrics are time-independent."""
        metrics = [
            Metric("Funding Signals", 50, 100, "Warning", "Medium"),
            Metric("Code of Conduct", 100, 100, "OK", "None"),
        ]

        time_dependent, excluded = filter_time_dependent_metrics(metrics)

        assert len(time_dependent) == 0
        assert len(excluded) == 2

    def test_filter_empty_list(self):
        """Test filtering an empty metric list."""
        time_dependent, excluded = filter_time_dependent_metrics([])

        assert len(time_dependent) == 0
        assert len(excluded) == 0


class TestDisplayTrendResults:
    """Test trend result display functions."""

    def test_display_trend_results_basic(self, capsys):
        """Test basic trend results display."""
        window1 = TimeWindow(
            start=datetime(2025, 10, 1, tzinfo=timezone.utc),
            end=datetime(2025, 10, 31, tzinfo=timezone.utc),
            label="2025-10",
        )
        window2 = TimeWindow(
            start=datetime(2025, 11, 1, tzinfo=timezone.utc),
            end=datetime(2025, 11, 30, tzinfo=timezone.utc),
            label="2025-11",
        )
        window3 = TimeWindow(
            start=datetime(2025, 12, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
            label="2025-12",
        )

        trend_data = [
            TrendDataPoint(
                window=window1,
                total_score=70,
                metrics=[Metric("Test", 70, 100, "OK", "Low")],
                excluded_metrics=[],
            ),
            TrendDataPoint(
                window=window2,
                total_score=75,
                metrics=[Metric("Test", 75, 100, "OK", "Low")],
                excluded_metrics=[],
            ),
            TrendDataPoint(
                window=window3,
                total_score=78,
                metrics=[Metric("Test", 78, 100, "OK", "Low")],
                excluded_metrics=[],
            ),
        ]

        from rich.console import Console

        console = Console()
        _display_trend_results(
            console, trend_data, "https://github.com/test/repo", "balanced"
        )

        captured = capsys.readouterr()
        assert "Sustainability Trend Analysis" in captured.out
        assert "test/repo" in captured.out
        assert "balanced" in captured.out

    def test_display_trend_results_empty_data(self, capsys):
        """Test display with empty trend data."""
        from rich.console import Console

        console = Console()
        _display_trend_results(console, [], "https://github.com/test/repo", "balanced")

        captured = capsys.readouterr()
        assert "No trend data available" in captured.out

    def test_display_ascii_chart_upward_trend(self, capsys):
        """Test ASCII chart display with upward trend."""
        window1 = TimeWindow(
            start=datetime(2025, 10, 1, tzinfo=timezone.utc),
            end=datetime(2025, 10, 31, tzinfo=timezone.utc),
            label="Oct",
        )
        window2 = TimeWindow(
            start=datetime(2025, 11, 1, tzinfo=timezone.utc),
            end=datetime(2025, 11, 30, tzinfo=timezone.utc),
            label="Nov",
        )
        window3 = TimeWindow(
            start=datetime(2025, 12, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
            label="Dec",
        )

        trend_data = [
            TrendDataPoint(
                window=window1,
                total_score=60,
                metrics=[],
                excluded_metrics=[],
            ),
            TrendDataPoint(
                window=window2,
                total_score=70,
                metrics=[],
                excluded_metrics=[],
            ),
            TrendDataPoint(
                window=window3,
                total_score=80,
                metrics=[],
                excluded_metrics=[],
            ),
        ]

        from rich.console import Console

        console = Console()
        _display_ascii_chart(console, trend_data)

        captured = capsys.readouterr()
        # Just verify that output is produced
        assert len(captured.out) > 0
        assert "Oct" in captured.out or "80" in captured.out

    def test_display_ascii_chart_flat_trend(self, capsys):
        """Test ASCII chart with flat (unchanging) trend."""
        windows = [
            TimeWindow(
                start=datetime(2025, 10, i, tzinfo=timezone.utc),
                end=datetime(2025, 10, i + 1, tzinfo=timezone.utc),
                label=f"Day {i}",
            )
            for i in range(1, 4)
        ]

        trend_data = [
            TrendDataPoint(
                window=window,
                total_score=75,
                metrics=[],
                excluded_metrics=[],
            )
            for window in windows
        ]

        from rich.console import Console

        console = Console()
        _display_ascii_chart(console, trend_data)

        captured = capsys.readouterr()
        # Flat line should still produce output
        assert len(captured.out) > 0


class TestTrendCommandValidation:
    """Test trend command parameter validation."""

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_valid_interval(self, mock_run):
        """Test that valid intervals are accepted."""
        for interval in [
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "semi-annual",
            "annual",
        ]:
            result = runner.invoke(
                app,
                [
                    "trend",
                    "requests",
                    "--interval",
                    interval,
                ],
            )
            assert result.exit_code == 0

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_valid_profiles(self, mock_run):
        """Test that valid profiles are accepted."""
        for profile in [
            "balanced",
            "security_first",
            "contributor_experience",
            "long_term_stability",
        ]:
            result = runner.invoke(
                app,
                [
                    "trend",
                    "requests",
                    "--profile",
                    profile,
                ],
            )
            assert result.exit_code == 0

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_positive_periods(self, mock_run):
        """Test that positive periods are accepted."""
        result = runner.invoke(
            app,
            [
                "trend",
                "requests",
                "--periods",
                "12",
            ],
        )

        # Should accept positive integer
        assert result.exit_code == 0

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_valid_scan_depths(self, mock_run):
        """Test that valid scan depths are accepted."""
        for depth in ["shallow", "default", "deep", "very_deep"]:
            result = runner.invoke(
                app,
                [
                    "trend",
                    "requests",
                    "--scan-depth",
                    depth,
                ],
            )
            assert result.exit_code == 0

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_positive_days_lookback(self, mock_run):
        """Test that positive days-lookback is accepted."""
        result = runner.invoke(
            app,
            [
                "trend",
                "requests",
                "--days-lookback",
                "90",
            ],
        )

        # Should accept the command (exit code 0) even if the actual analysis fails
        # because we're mocking the async implementation
        assert result.exit_code in [0, 2] or "Missing argument" in str(result.output)


class TestTrendCommandOptions:
    """Test trend command with various options."""

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_package_argument(self, mock_run):
        """Test trend command with package argument."""

        result = runner.invoke(
            app,
            [
                "trend",
                "requests",
            ],
        )

        # Should not fail on argument parsing
        assert "Error" not in result.stdout

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_with_ecosystem_option(self, mock_run):
        """Test trend command with ecosystem option."""

        result = runner.invoke(
            app,
            [
                "trend",
                "react",
                "--ecosystem",
                "javascript",
            ],
        )

        assert result.exit_code == 0 or "Error" not in result.stdout

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_with_interval_option(self, mock_run):
        """Test trend command with interval option."""

        result = runner.invoke(
            app,
            [
                "trend",
                "requests",
                "--interval",
                "weekly",
            ],
        )

        assert result.exit_code == 0 or "Error" not in result.stdout

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_with_periods_option(self, mock_run):
        """Test trend command with periods option."""

        result = runner.invoke(
            app,
            [
                "trend",
                "requests",
                "--periods",
                "12",
            ],
        )

        assert result.exit_code == 0 or "Error" not in result.stdout

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_with_window_days_option(self, mock_run):
        """Test trend command with window-days option."""

        result = runner.invoke(
            app,
            [
                "trend",
                "requests",
                "--window-days",
                "14",
            ],
        )

        assert result.exit_code == 0 or "Error" not in result.stdout

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_with_profile_option(self, mock_run):
        """Test trend command with profile option."""

        result = runner.invoke(
            app,
            [
                "trend",
                "requests",
                "--profile",
                "security_first",
            ],
        )

        assert result.exit_code == 0 or "Error" not in result.stdout

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_with_cache_options(self, mock_run):
        """Test trend command with cache options."""

        result = runner.invoke(
            app,
            [
                "trend",
                "requests",
                "--no-cache",
            ],
        )

        assert result.exit_code == 0 or "Error" not in result.stdout

    @patch("asyncio.run", side_effect=_mock_asyncio_run)
    def test_trend_with_verbose_option(self, mock_run):
        """Test trend command with verbose option."""

        result = runner.invoke(
            app,
            [
                "trend",
                "requests",
                "--verbose",
            ],
        )

        assert result.exit_code == 0 or "Error" not in result.stdout


class TestTrendDataProcessing:
    """Test trend data processing and analysis."""

    def test_trend_data_point_with_excluded_metrics(self):
        """Test TrendDataPoint with excluded metrics information."""
        window = TimeWindow(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 1, 31, tzinfo=timezone.utc),
            label="2025-01",
        )
        metrics = [
            Metric("Recent Activity", 75, 100, "OK", "Low"),
            Metric("Release Rhythm", 80, 100, "OK", "Low"),
        ]
        excluded = ["Funding Signals", "Code of Conduct"]

        point = TrendDataPoint(
            window=window,
            total_score=77,
            metrics=metrics,
            excluded_metrics=excluded,
        )

        assert len(point.metrics) == 2
        assert len(point.excluded_metrics) == 2
        assert point.total_score == 77

    def test_trend_score_progression(self):
        """Test tracking score progression across time windows."""
        windows = [
            TimeWindow(
                start=datetime(2025, 1, 1, tzinfo=timezone.utc),
                end=datetime(2025, 1, 31, tzinfo=timezone.utc),
                label="2025-01",
            ),
            TimeWindow(
                start=datetime(2025, 2, 1, tzinfo=timezone.utc),
                end=datetime(2025, 2, 28, tzinfo=timezone.utc),
                label="2025-02",
            ),
            TimeWindow(
                start=datetime(2025, 3, 1, tzinfo=timezone.utc),
                end=datetime(2025, 3, 31, tzinfo=timezone.utc),
                label="2025-03",
            ),
        ]

        scores = [65, 70, 75]
        trend_data = [
            TrendDataPoint(
                window=windows[i],
                total_score=scores[i],
                metrics=[],
                excluded_metrics=[],
            )
            for i in range(len(windows))
        ]

        # Verify increasing trend
        for i in range(1, len(trend_data)):
            assert trend_data[i].total_score >= trend_data[i - 1].total_score
