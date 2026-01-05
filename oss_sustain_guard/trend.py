"""
Time Machine Mode (Trend Analysis) for OSS Sustain Guard.

This module provides functionality to analyze sustainability score trends over time
by collecting data across multiple time windows and comparing metric evolution.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import NamedTuple

from oss_sustain_guard.metrics.base import Metric


class TrendInterval(str, Enum):
    """Display interval labels for trend analysis."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi-annual"
    ANNUAL = "annual"


class TimeWindow(NamedTuple):
    """Represents a time window for data collection."""

    start: datetime
    end: datetime
    label: str  # Display label (e.g., "2024-01", "Q1 2024")


class TrendDataPoint(NamedTuple):
    """A single data point in the trend analysis."""

    window: TimeWindow
    total_score: int
    metrics: list[Metric]
    excluded_metrics: list[str]  # Metrics excluded due to time-independence


# Metrics that can be calculated from time-windowed data
# These metrics depend on temporal data (commits, issues, PRs, releases)
TIME_DEPENDENT_METRICS = {
    # Activity metrics
    "Recent Activity",  # Based on pushed_at timestamp
    "Change Request Resolution",  # Based on merged PRs in time window
    "Issue Resolution Duration",  # Based on closed issues in time window
    "Release Rhythm",  # Based on releases in time window
    "PR Acceptance Ratio",  # Based on PRs in time window
    "PR Responsiveness",  # Based on PRs in time window
    "PR Merge Speed",  # Based on merged PRs in time window
    "Stale Issue Ratio",  # Based on open issues in time window
    # Contributor metrics
    "Contributor Redundancy",  # Based on commits in time window
    "Maintainer Retention",  # Based on commits in time window
    "Contributor Attraction",  # Based on commits in time window
    "Contributor Retention",  # Based on commits in time window
    "Organizational Diversity",  # Based on commits in time window
    "Maintainer Load Distribution",  # Based on commits and PRs in time window
    "Review Health",  # Based on PRs in time window
    # Fork metrics
    "Fork Activity",  # Based on fork data in time window
}

# Metrics that cannot be accurately calculated from time-windowed data
# These are excluded from trend analysis
TIME_INDEPENDENT_METRICS = {
    # Static/current-state metrics
    "Funding Signals",  # Funding links (current state only)
    "Security Signals",  # Vulnerability alerts (current state only)
    "Documentation Presence",  # README/CONTRIBUTING existence (current state)
    "Code of Conduct",  # CoC existence (current state)
    "Project Popularity",  # Stars (cumulative, no historical API)
    "License Clarity",  # License info (current state)
    "Community Health",  # Community health files (current state)
    "Build Health",  # CI configuration (current state)
}


def generate_time_windows(
    interval: TrendInterval,
    periods: int,
    window_days: int,
    end_date: datetime | None = None,
) -> list[TimeWindow]:
    """
    Generate time windows for trend analysis.

    Args:
        interval: Display interval for labeling (daily/weekly/monthly/etc.)
        periods: Number of time windows to generate
        window_days: Size of each window in days
        end_date: End date for analysis (defaults to now)

    Returns:
        List of TimeWindow objects, ordered from oldest to newest

    Note:
        This is an approximation. Historical data may not be complete due to
        API limitations and data availability.
    """
    from datetime import timezone

    if end_date is None:
        end_date = datetime.now(timezone.utc)

    windows: list[TimeWindow] = []
    delta = timedelta(days=window_days)

    # Generate windows going backwards from end_date
    # The most recent window ends at end_date
    for i in range(periods):
        # i=0: most recent window (ends at end_date)
        # i=1: second most recent (ends at end_date - delta)
        # ...
        # i=periods-1: oldest window (ends at end_date - delta*(periods-1))
        window_end = end_date - (delta * i)
        window_start = window_end - delta

        # Generate label based on interval type
        label = _generate_window_label(interval, window_start, window_end, i)

        windows.append(TimeWindow(start=window_start, end=window_end, label=label))

    # Return in chronological order (oldest first)
    # Reverse because we generated newest to oldest
    return list(reversed(windows))


def _generate_window_label(
    interval: TrendInterval,
    start: datetime,
    end: datetime,
    index: int,
) -> str:
    """
    Generate a display label for a time window.

    The label is based on the window start date. For monthly intervals,
    if the window spans into the next month (common for 30-day windows),
    the label still uses the starting month.

    Example: A window from 2025-12-06 to 2026-01-05 will be labeled "2025-12"
    """
    if interval == TrendInterval.DAILY:
        return start.strftime("%Y-%m-%d")
    elif interval == TrendInterval.WEEKLY:
        return f"Week {start.strftime('%Y-%W')}"
    elif interval == TrendInterval.MONTHLY:
        # Use start month, even if window extends into next month
        return start.strftime("%Y-%m")
    elif interval == TrendInterval.QUARTERLY:
        quarter = (start.month - 1) // 3 + 1
        return f"Q{quarter} {start.year}"
    elif interval == TrendInterval.SEMI_ANNUAL:
        half = "H1" if start.month <= 6 else "H2"
        return f"{half} {start.year}"
    elif interval == TrendInterval.ANNUAL:
        return str(start.year)
    else:
        return start.strftime("%Y-%m-%d")


def is_metric_time_dependent(metric_name: str) -> bool:
    """
    Check if a metric can be calculated from time-windowed data.

    Args:
        metric_name: Name of the metric to check

    Returns:
        True if metric can be calculated from historical data, False otherwise
    """
    return metric_name in TIME_DEPENDENT_METRICS


def filter_time_dependent_metrics(
    metrics: list[Metric],
) -> tuple[list[Metric], list[str]]:
    """
    Filter metrics to only include time-dependent ones.

    Args:
        metrics: List of calculated metrics

    Returns:
        Tuple of (time_dependent_metrics, excluded_metric_names)
    """
    time_dependent = []
    excluded = []

    for metric in metrics:
        if is_metric_time_dependent(metric.name):
            time_dependent.append(metric)
        else:
            excluded.append(metric.name)

    return time_dependent, excluded


async def analyze_repository_trend(
    owner: str,
    name: str,
    interval: TrendInterval,
    periods: int,
    window_days: int,
    profile: str = "balanced",
    vcs_platform: str = "github",
    scan_depth: str = "default",
) -> list[TrendDataPoint]:
    """
    Analyze repository sustainability trends over multiple time windows.

    This function collects historical data by analyzing the repository across
    multiple time periods, calculating metrics for each period separately.

    Args:
        owner: Repository owner (username or organization)
        name: Repository name
        interval: Display interval for labeling (daily/weekly/monthly/etc.)
        periods: Number of time windows to analyze
        window_days: Size of each window in days
        profile: Scoring profile name
        vcs_platform: VCS platform ('github', 'gitlab', etc.)
        scan_depth: Sampling depth - "shallow", "default", or "deep"

    Returns:
        List of TrendDataPoint objects, one per time window (chronological order)

    Note:
        This analysis is approximate due to API limitations. Some metrics
        (e.g., stars, vulnerability alerts) cannot be historically analyzed
        and are excluded from trend calculations.
    """
    from oss_sustain_guard.core import (
        _analyze_repository_data,
        compute_weighted_total_score,
    )
    from oss_sustain_guard.vcs import get_vcs_provider

    # Generate time windows
    windows = generate_time_windows(interval, periods, window_days)

    # Get VCS provider
    vcs = get_vcs_provider(vcs_platform)

    trend_data: list[TrendDataPoint] = []

    for window in windows:
        # Convert datetime to ISO format strings
        since = window.start.isoformat()
        until = window.end.isoformat()

        # Fetch VCS data for this time window
        vcs_data = await vcs.get_repository_data(
            owner,
            name,
            scan_depth=scan_depth,
            time_window=(since, until),
        )

        # Analyze repository data with standard logic
        result = _analyze_repository_data(
            owner,
            name,
            vcs_data,
            platform=None,
            package_name=None,
            profile=profile,
        )

        # Filter metrics to only time-dependent ones
        time_dependent_metrics, excluded_metrics = filter_time_dependent_metrics(
            result.metrics
        )

        # Recalculate total score using only time-dependent metrics
        # Note: We pass the same profile, but only time-dependent metrics are included
        # This means the score is calculated only from metrics that can be historically analyzed
        filtered_total_score = compute_weighted_total_score(
            time_dependent_metrics, profile
        )

        # Create data point
        data_point = TrendDataPoint(
            window=window,
            total_score=filtered_total_score,
            metrics=time_dependent_metrics,
            excluded_metrics=excluded_metrics,
        )
        trend_data.append(data_point)

    return trend_data
