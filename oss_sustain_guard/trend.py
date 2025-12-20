"""Time series analysis and trend tracking for package health metrics.

This module provides functionality to:
- Load historical data from Cloudflare KV or local cache
- Compare package health metrics over time
- Identify improvement/degradation trends
- Generate trend reports and visualizations
"""

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.table import Table

from oss_sustain_guard.cache import list_history_dates, load_history
from oss_sustain_guard.core import Metric, compute_weighted_total_score


class TrendData:
    """Container for package health data at a specific point in time."""

    def __init__(
        self,
        date: str,
        package_name: str,
        total_score: int,
        metrics: list[dict[str, Any]],
        github_url: str,
    ):
        self.date = date
        self.package_name = package_name
        self.total_score = total_score
        self.metrics = metrics
        self.github_url = github_url

    def __repr__(self) -> str:
        return f"TrendData({self.date}, {self.package_name}, score={self.total_score})"


class TrendAnalyzer:
    """Analyzes package health trends over time.

    Data sources (priority order):
    1. Cloudflare KV (remote historical data) - if use_remote=True
    2. Local cache history (~/.cache/oss-sustain-guard/history/) - fallback
    """

    def __init__(self, use_remote: bool = True):
        """Initialize TrendAnalyzer.

        Args:
            use_remote: If True, try to load historical data from Cloudflare KV first.
        """
        self.use_remote = use_remote
        self.console = Console()

    def list_available_dates(self, ecosystem: str) -> list[str]:
        """List all available snapshot dates for ecosystem.

        Tries Cloudflare KV first, then falls back to local sources.

        Args:
            ecosystem: Ecosystem name (python, javascript, etc.).

        Returns:
            Sorted list of date strings in YYYY-MM-DD format (descending, newest first).
        """
        # Try Cloudflare KV first if enabled
        if self.use_remote:
            try:
                # Note: This returns ALL dates available in KV across all packages
                # For now, use local cache history implementation
                # TODO: Implement KV-wide date listing or package-specific date listing
                pass
            except Exception:
                pass

        # Fallback to local cache history
        return list_history_dates(ecosystem)

    @staticmethod
    def _is_valid_date_format(date_str: str) -> bool:
        """Validate YYYY-MM-DD format."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def load_package_history(
        self, package_name: str, ecosystem: str = "python"
    ) -> list[TrendData]:
        """Load historical data for a specific package.

        Data sources (priority order):
        1. Cloudflare KV (if use_remote=True)
        2. Local cache history

        Args:
            package_name: Name of the package to track
            ecosystem: Package ecosystem (python, javascript, etc.)

        Returns:
            List of TrendData objects sorted by date (oldest first)
        """
        history = []

        # Try Cloudflare KV first if enabled
        if self.use_remote:
            try:
                from oss_sustain_guard.remote_cache import CloudflareKVClient

                client = CloudflareKVClient()
                kv_history = client.get_history(ecosystem, package_name)

                if kv_history:
                    for date, snapshot in kv_history.items():
                        # Get total_score, calculate if not present
                        total_score = snapshot.get("total_score")
                        if total_score is None:
                            metrics_data = snapshot.get("metrics", [])
                            if metrics_data:
                                metric_objects = [
                                    Metric(
                                        name=m.get("name", ""),
                                        score=m.get("score", 0),
                                        max_score=m.get("max_score", 0),
                                        message=m.get("message", ""),
                                        risk=m.get("risk", "None"),
                                    )
                                    for m in metrics_data
                                ]
                                total_score = compute_weighted_total_score(
                                    metric_objects
                                )
                            else:
                                total_score = 0

                        history.append(
                            TrendData(
                                date=date,
                                package_name=package_name,
                                total_score=total_score,
                                metrics=snapshot.get("metrics", []),
                                github_url=snapshot.get("github_url", ""),
                            )
                        )

                    # Sort by date (oldest first) and return
                    history.sort(key=lambda x: x.date)
                    return history

            except Exception as e:
                # Silently fall back to local sources
                self.console.print(
                    f"[dim]Note: Cloudflare KV unavailable ({type(e).__name__}), using local data[/dim]"
                )

        # Fallback: Load history from local cache
        history_data = load_history(ecosystem)
        package_key = f"{ecosystem}:{package_name}"

        if package_key in history_data:
            for snapshot in history_data[package_key]:
                date = snapshot.get("date", "")

                # Get total_score, calculate if not present
                total_score = snapshot.get("total_score")
                if total_score is None:
                    # Calculate from metrics using weighted scoring
                    metrics_data = snapshot.get("metrics", [])
                    if metrics_data:
                        # Convert dict metrics to Metric namedtuples
                        metric_objects = [
                            Metric(
                                name=m.get("name", ""),
                                score=m.get("score", 0),
                                max_score=m.get("max_score", 0),
                                message=m.get("message", ""),
                                risk=m.get("risk", "None"),
                            )
                            for m in metrics_data
                        ]
                        # Use weighted scoring to get 0-100 score
                        total_score = compute_weighted_total_score(metric_objects)
                    else:
                        total_score = 0

                history.append(
                    TrendData(
                        date=date,
                        package_name=package_name,
                        total_score=total_score,
                        metrics=snapshot.get("metrics", []),
                        github_url=snapshot.get("github_url", ""),
                    )
                )

        # Sort by date (oldest first)
        history.sort(key=lambda x: x.date)
        return history

    def calculate_trend(self, history: list[TrendData]) -> dict[str, Any]:
        """Calculate trend statistics from historical data.

        Args:
            history: List of TrendData objects

        Returns:
            Dictionary containing trend statistics:
            - first_score: Initial score
            - last_score: Most recent score
            - change: Score change (last - first)
            - change_pct: Percentage change
            - trend: "improving", "stable", or "degrading"
            - avg_score: Average score across all snapshots
        """
        if not history:
            return {
                "first_score": 0,
                "last_score": 0,
                "change": 0,
                "change_pct": 0.0,
                "trend": "unknown",
                "avg_score": 0,
            }

        scores = [h.total_score for h in history]
        first_score = scores[0]
        last_score = scores[-1]
        change = last_score - first_score
        change_pct = (change / first_score * 100) if first_score > 0 else 0.0
        avg_score = sum(scores) // len(scores)

        # Determine trend
        if change > 5:
            trend = "improving"
        elif change < -5:
            trend = "degrading"
        else:
            trend = "stable"

        return {
            "first_score": first_score,
            "last_score": last_score,
            "change": change,
            "change_pct": change_pct,
            "trend": trend,
            "avg_score": avg_score,
        }

    def display_trend_table(self, package_name: str, history: list[TrendData]) -> None:
        """Display trend data in a rich table format."""
        if not history:
            self.console.print(
                f"[yellow]ℹ️  No historical data found for package: {package_name}[/yellow]"
            )
            return

        trend_stats = self.calculate_trend(history)

        # Create summary table
        summary = Table(title=f"📊 Health Trend for {package_name}", show_header=False)
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", style="white")

        summary.add_row("GitHub URL", history[0].github_url)
        summary.add_row("First Snapshot", history[0].date)
        summary.add_row("Latest Snapshot", history[-1].date)
        summary.add_row("First Score", f"{trend_stats['first_score']}/100")
        summary.add_row("Latest Score", f"{trend_stats['last_score']}/100")
        summary.add_row("Average Score", f"{trend_stats['avg_score']}/100")

        # Color-code the change
        change = trend_stats["change"]
        change_pct = trend_stats["change_pct"]
        if change > 0:
            change_str = f"[green]+{change} ({change_pct:+.1f}%)[/green]"
        elif change < 0:
            change_str = f"[red]{change} ({change_pct:+.1f}%)[/red]"
        else:
            change_str = f"[dim]{change} ({change_pct:+.1f}%)[/dim]"

        summary.add_row("Score Change", change_str)

        # Trend indicator
        trend = trend_stats["trend"]
        if trend == "improving":
            trend_str = "[green]📈 Improving[/green]"
        elif trend == "degrading":
            trend_str = "[red]📉 Degrading[/red]"
        else:
            trend_str = "[dim]➡️  Stable[/dim]"

        summary.add_row("Trend", trend_str)

        self.console.print(summary)

        # Create detailed timeline table
        self.console.print("\n")
        timeline = Table(title="📅 Score History")
        timeline.add_column("Date", style="cyan")
        timeline.add_column("Total Score", justify="right")
        timeline.add_column("Change", justify="right")
        timeline.add_column("Status", justify="center")

        prev_score = None
        for trend_data in history:
            score = trend_data.total_score

            # Calculate change from previous snapshot
            if prev_score is not None:
                delta = score - prev_score
                if delta > 0:
                    change_str = f"[green]+{delta}[/green]"
                    status = "📈"
                elif delta < 0:
                    change_str = f"[red]{delta}[/red]"
                    status = "📉"
                else:
                    change_str = "[dim]0[/dim]"
                    status = "➡️"
            else:
                change_str = "[dim]-[/dim]"
                status = "🟢"

            # Color-code score
            if score >= 80:
                score_str = f"[green]{score}/100[/green]"
            elif score >= 50:
                score_str = f"[yellow]{score}/100[/yellow]"
            else:
                score_str = f"[red]{score}/100[/red]"

            timeline.add_row(trend_data.date, score_str, change_str, status)
            prev_score = score

        self.console.print(timeline)

    def display_metric_comparison(
        self,
        package_name: str,
        history: list[TrendData],
        metric_name: str | None = None,
    ) -> None:
        """Display detailed metric comparison over time.

        Args:
            package_name: Name of the package
            history: Historical data
            metric_name: Specific metric to focus on (if None, show all)
        """
        if not history:
            self.console.print(
                f"[yellow]ℹ️  No historical data found for package: {package_name}[/yellow]"
            )
            return

        # Get all metric names from latest snapshot
        latest = history[-1]
        metric_names = [m["name"] for m in latest.metrics]

        if metric_name and metric_name not in metric_names:
            self.console.print(
                f"[yellow]ℹ️  Metric '{metric_name}' not found. Available metrics: {', '.join(metric_names)}[/yellow]"
            )
            return

        # Filter metrics if specific one requested
        if metric_name:
            target_metrics = [metric_name]
        else:
            target_metrics = metric_names

        for m_name in target_metrics:
            table = Table(title=f"📊 {m_name} - Trend Analysis")
            table.add_column("Date", style="cyan")
            table.add_column("Score", justify="right")
            table.add_column("Max", justify="right")
            table.add_column("Risk", justify="center")
            table.add_column("Note")

            for trend_data in history:
                # Find the metric in this snapshot
                metric = next(
                    (m for m in trend_data.metrics if m["name"] == m_name), None
                )

                if metric:
                    score = metric.get("score", 0)
                    max_score = metric.get("max_score", 0)
                    risk = metric.get("risk", "Unknown")
                    message = metric.get("message", "")

                    # Color-code score
                    score_pct = (score / max_score * 100) if max_score > 0 else 0
                    if score_pct >= 80:
                        score_str = f"[green]{score}[/green]"
                    elif score_pct >= 50:
                        score_str = f"[yellow]{score}[/yellow]"
                    else:
                        score_str = f"[red]{score}[/red]"

                    # Risk color
                    risk_colors = {
                        "None": "green",
                        "Low": "green",
                        "Medium": "yellow",
                        "High": "red",
                        "Critical": "red",
                    }
                    risk_color = risk_colors.get(risk, "white")
                    risk_str = f"[{risk_color}]{risk}[/{risk_color}]"

                    # Truncate message if too long
                    if len(message) > 60:
                        message = message[:57] + "..."

                    table.add_row(
                        trend_data.date,
                        score_str,
                        str(max_score),
                        risk_str,
                        f"[dim]{message}[/dim]",
                    )
                else:
                    table.add_row(
                        trend_data.date,
                        "[dim]N/A[/dim]",
                        "[dim]N/A[/dim]",
                        "[dim]N/A[/dim]",
                        "[dim]Metric not available[/dim]",
                    )

            self.console.print(table)
            self.console.print()


class ComparisonReport:
    """Generate comparison reports between specific time periods."""

    def __init__(self, analyzer: TrendAnalyzer):
        self.analyzer = analyzer
        self.console = Console()

    def compare_dates(
        self, package_name: str, date1: str, date2: str, ecosystem: str = "python"
    ) -> None:
        """Compare package health between two specific dates.

        Args:
            package_name: Name of the package
            date1: Earlier date (YYYY-MM-DD)
            date2: Later date (YYYY-MM-DD)
            ecosystem: Package ecosystem
        """
        history = self.analyzer.load_package_history(package_name, ecosystem)

        if not history:
            self.console.print(
                f"[yellow]ℹ️  No historical data found for package: {package_name}[/yellow]"
            )
            return

        # Find snapshots for specified dates
        snapshot1 = next((h for h in history if h.date == date1), None)
        snapshot2 = next((h for h in history if h.date == date2), None)

        if not snapshot1 or not snapshot2:
            self.console.print(
                "[yellow]ℹ️  Data not available for one or both dates[/yellow]"
            )
            self.console.print(
                f"Available dates: {', '.join([h.date for h in history])}"
            )
            return

        # Create comparison table
        table = Table(title=f"📊 Comparison Report: {package_name}\n{date1} → {date2}")
        table.add_column("Metric", style="cyan")
        table.add_column(f"{date1}\nScore", justify="right")
        table.add_column(f"{date2}\nScore", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("Status", justify="center")

        # Overall score comparison
        score1 = snapshot1.total_score
        score2 = snapshot2.total_score
        delta = score2 - score1

        if delta > 0:
            delta_str = f"[green]+{delta}[/green]"
            status = "📈"
        elif delta < 0:
            delta_str = f"[red]{delta}[/red]"
            status = "📉"
        else:
            delta_str = "[dim]0[/dim]"
            status = "➡️"

        table.add_row(
            "[bold]Total Score[/bold]",
            f"{score1}/100",
            f"{score2}/100",
            delta_str,
            status,
        )

        # Individual metrics comparison
        metric_names = set(
            [m["name"] for m in snapshot1.metrics]
            + [m["name"] for m in snapshot2.metrics]
        )

        for m_name in sorted(metric_names):
            metric1 = next((m for m in snapshot1.metrics if m["name"] == m_name), None)
            metric2 = next((m for m in snapshot2.metrics if m["name"] == m_name), None)

            if metric1 and metric2:
                s1 = metric1.get("score", 0)
                s2 = metric2.get("score", 0)
                delta_m = s2 - s1

                max_score = metric2.get("max_score", 0)

                if delta_m > 0:
                    delta_str = f"[green]+{delta_m}[/green]"
                    status = "📈"
                elif delta_m < 0:
                    delta_str = f"[red]{delta_m}[/red]"
                    status = "📉"
                else:
                    delta_str = "[dim]0[/dim]"
                    status = "➡️"

                table.add_row(
                    m_name,
                    f"{s1}/{max_score}",
                    f"{s2}/{max_score}",
                    delta_str,
                    status,
                )
            elif metric1:
                s1 = metric1.get("score", 0)
                max_score = metric1.get("max_score", 0)
                table.add_row(
                    m_name,
                    f"{s1}/{max_score}",
                    "[dim]N/A[/dim]",
                    "[red]Removed[/red]",
                    "❌",
                )
            elif metric2:
                s2 = metric2.get("score", 0)
                max_score = metric2.get("max_score", 0)
                table.add_row(
                    m_name,
                    "[dim]N/A[/dim]",
                    f"{s2}/{max_score}",
                    "[green]New[/green]",
                    "✨",
                )

        self.console.print(table)
