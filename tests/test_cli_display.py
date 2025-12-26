"""
Tests for CLI display functions (display_results, display_results_compact, display_results_detailed).
"""

from oss_sustain_guard.cli import (
    display_results,
    display_results_compact,
    display_results_detailed,
)
from oss_sustain_guard.core import AnalysisResult, Metric


class TestDisplayResultsCompact:
    """Test compact display format."""

    def test_display_results_compact_healthy(self, capsys):
        """Test compact display for healthy package."""
        results = [
            AnalysisResult(
                repo_url="https://github.com/psf/requests",
                total_score=85,
                metrics=[
                    Metric("Test", 85, 100, "Good", "Low"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[],
                signals={},
                dependency_scores={},
            )
        ]

        display_results_compact(results)

        captured = capsys.readouterr()
        assert "psf/requests" in captured.out
        assert "(85/100)" in captured.out
        assert "Healthy" in captured.out

    def test_display_results_compact_needs_attention(self, capsys):
        """Test compact display for package needing attention."""
        results = [
            AnalysisResult(
                repo_url="https://github.com/test/package",
                total_score=65,
                metrics=[
                    Metric("Test", 65, 100, "Medium", "Medium"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[],
                signals={},
                dependency_scores={},
            )
        ]

        display_results_compact(results)

        captured = capsys.readouterr()
        assert "test/package" in captured.out
        assert "(65/100)" in captured.out
        assert "Needs attention" in captured.out

    def test_display_results_compact_needs_support(self, capsys):
        """Test compact display for package needing support."""
        results = [
            AnalysisResult(
                repo_url="https://github.com/test/package",
                total_score=40,
                metrics=[
                    Metric("Test", 40, 100, "Low", "High"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[],
                signals={},
                dependency_scores={},
            )
        ]

        display_results_compact(results)

        captured = capsys.readouterr()
        assert "test/package" in captured.out
        assert "(40/100)" in captured.out
        assert "Needs support" in captured.out

    def test_display_results_compact_with_dependencies(self, capsys):
        """Test compact display with dependency scores."""
        results = [
            AnalysisResult(
                repo_url="https://github.com/psf/requests",
                total_score=85,
                metrics=[
                    Metric("Test", 85, 100, "Good", "Low"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[],
                signals={},
                dependency_scores={"dep1": 90, "dep2": 80, "dep3": 70},
            )
        ]

        display_results_compact(results, show_dependencies=True)

        captured = capsys.readouterr()
        assert "Dependencies:" in captured.out
        assert "avg=" in captured.out
        assert "count=3" in captured.out


class TestDisplayResults:
    """Test normal display format."""

    def test_display_results_table(self, capsys):
        """Test normal table display."""
        results = [
            AnalysisResult(
                repo_url="https://github.com/psf/requests",
                total_score=85,
                metrics=[
                    Metric("Test Metric", 85, 100, "Good", "Low"),
                    Metric("Critical Metric", 10, 100, "Bad", "Critical"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[],
                signals={},
                dependency_scores={},
            )
        ]

        display_results(results)

        captured = capsys.readouterr()
        assert "OSS Sustain Guard Report" in captured.out
        assert "psf/requests" in captured.out
        assert "85/100" in captured.out
        assert "Healthy" in captured.out

    def test_display_results_with_funding(self, capsys):
        """Test display with funding links."""
        results = [
            AnalysisResult(
                repo_url="https://github.com/psf/requests",
                total_score=85,
                metrics=[
                    Metric("Test", 85, 100, "Good", "Low"),
                ],
                funding_links=[
                    {
                        "platform": "GitHub Sponsors",
                        "url": "https://github.com/sponsors/test",
                    }
                ],
                is_community_driven=True,
                models=[],
                signals={},
                dependency_scores={},
            )
        ]

        display_results(results)

        captured = capsys.readouterr()
        assert "Consider supporting" in captured.out
        assert "GitHub Sponsors" in captured.out

    def test_display_results_with_dependencies(self, capsys):
        """Test display with dependency scores."""
        results = [
            AnalysisResult(
                repo_url="https://github.com/psf/requests",
                total_score=85,
                metrics=[
                    Metric("Test", 85, 100, "Good", "Low"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[],
                signals={},
                dependency_scores={"dep1": 90, "dep2": 80, "dep3": 70},
            )
        ]

        display_results(results, show_dependencies=True)

        captured = capsys.readouterr()
        assert "Dependency Reference Scores" in captured.out
        assert "dep1" in captured.out

    def test_display_results_with_models(self, capsys):
        """Test display with CHAOSS models."""
        # Import the Metric/Model classes
        from oss_sustain_guard.core import MetricModel

        results = [
            AnalysisResult(
                repo_url="https://github.com/psf/requests",
                total_score=85,
                metrics=[
                    Metric("Test", 85, 100, "Good", "Low"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[
                    MetricModel(
                        name="Risk Model",
                        score=85,
                        max_score=100,
                        observation="Low risk",
                    )
                ],
                signals={},
                dependency_scores={},
            )
        ]

        display_results(results, show_models=True)

        captured = capsys.readouterr()
        assert "CHAOSS Metric Models" in captured.out


class TestDisplayResultsDetailed:
    """Test detailed display format."""

    def test_display_results_detailed_basic(self, capsys):
        """Test detailed display with basic metrics."""
        results = [
            AnalysisResult(
                repo_url="https://github.com/psf/requests",
                total_score=85,
                metrics=[
                    Metric("Test Metric", 85, 100, "Good observation", "Low"),
                    Metric("Critical Metric", 10, 100, "Needs improvement", "Critical"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[],
                signals={},
                dependency_scores={},
            )
        ]

        display_results_detailed(results)

        captured = capsys.readouterr()
        assert "psf/requests" in captured.out
        assert "Total Score: 85/100" in captured.out
        assert "Test Metric" in captured.out
        assert "Critical Metric" in captured.out

    def test_display_results_detailed_with_funding(self, capsys):
        """Test detailed display with funding links."""
        results = [
            AnalysisResult(
                repo_url="https://github.com/psf/requests",
                total_score=70,
                metrics=[
                    Metric("Test", 70, 100, "Medium", "Medium"),
                ],
                funding_links=[
                    {
                        "platform": "GitHub Sponsors",
                        "url": "https://github.com/sponsors/test",
                    },
                    {"platform": "Patreon", "url": "https://patreon.com/test"},
                ],
                is_community_driven=True,
                models=[],
                signals={},
                dependency_scores={},
            )
        ]

        display_results_detailed(results)

        captured = capsys.readouterr()
        assert "Funding support available" in captured.out
        assert "GitHub Sponsors" in captured.out
        assert "Patreon" in captured.out

    def test_display_results_detailed_with_models(self, capsys):
        """Test detailed display with CHAOSS models."""
        from oss_sustain_guard.core import MetricModel

        results = [
            AnalysisResult(
                repo_url="https://github.com/psf/requests",
                total_score=85,
                metrics=[
                    Metric("Test", 85, 100, "Good", "Low"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[
                    MetricModel(
                        name="Risk Model",
                        score=85,
                        max_score=100,
                        observation="Low risk indicators",
                    ),
                    MetricModel(
                        name="Sustainability Model",
                        score=80,
                        max_score=100,
                        observation="Good sustainability",
                    ),
                ],
                signals={},
                dependency_scores={},
            )
        ]

        display_results_detailed(results, show_models=True)

        captured = capsys.readouterr()
        assert "CHAOSS Metric Models" in captured.out
        assert "Risk Model" in captured.out
        assert "Sustainability Model" in captured.out

    def test_display_results_detailed_with_signals(self, capsys):
        """Test detailed display with raw signals."""
        results = [
            AnalysisResult(
                repo_url="https://github.com/psf/requests",
                total_score=85,
                metrics=[
                    Metric("Test", 85, 100, "Good", "Low"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[],
                signals={
                    "total_contributors": 100,
                    "recent_commits": 50,
                    "open_issues": 20,
                },
                dependency_scores={},
            )
        ]

        display_results_detailed(results, show_signals=True)

        captured = capsys.readouterr()
        assert "Raw Signals" in captured.out
        assert "total_contributors" in captured.out
        assert "100" in captured.out

    def test_display_results_detailed_with_dependencies(self, capsys):
        """Test detailed display with dependency scores."""
        dep_scores = {f"dep{i}": 90 - i * 5 for i in range(20)}

        results = [
            AnalysisResult(
                repo_url="https://github.com/psf/requests",
                total_score=85,
                metrics=[
                    Metric("Test", 85, 100, "Good", "Low"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[],
                signals={},
                dependency_scores=dep_scores,
            )
        ]

        display_results_detailed(results)

        captured = capsys.readouterr()
        assert "Dependency Reference Scores" in captured.out
        assert "dep0" in captured.out
        # Should show top 15 + "... and X more"
        assert "... and 5 more" in captured.out

    def test_display_results_detailed_metric_status_colors(self, capsys):
        """Test metric status color coding."""
        results = [
            AnalysisResult(
                repo_url="https://github.com/test/package",
                total_score=50,
                metrics=[
                    Metric("Critical Risk", 10, 100, "Critical issue", "Critical"),
                    Metric("High Risk", 20, 100, "High risk issue", "High"),
                    Metric("Medium Risk", 50, 100, "Medium issue", "Medium"),
                    Metric("Low Risk", 70, 100, "Minor issue", "Low"),
                    Metric("No Risk", 90, 100, "Good", "None"),
                ],
                funding_links=[],
                is_community_driven=False,
                models=[],
                signals={},
                dependency_scores={},
            )
        ]

        display_results_detailed(results)

        captured = capsys.readouterr()
        assert "Critical Risk" in captured.out
        assert "High Risk" in captured.out
        assert "Medium Risk" in captured.out
        assert "Low Risk" in captured.out
        assert "No Risk" in captured.out
