"""Tests for dependency graph visualization."""

import json
from pathlib import Path

import networkx as nx
import pytest

from oss_sustain_guard.core import AnalysisResult, Metric
from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo
from oss_sustain_guard.visualization import PlotlyVisualizer, build_networkx_graph


@pytest.fixture
def sample_dep_graph() -> DependencyGraph:
    """Create a sample dependency graph for testing."""
    return DependencyGraph(
        root_package="test-app",
        ecosystem="python",
        direct_dependencies=[
            DependencyInfo(
                name="requests",
                ecosystem="python",
                version="2.31.0",
                is_direct=True,
                depth=0,
            ),
            DependencyInfo(
                name="django",
                ecosystem="python",
                version="5.0",
                is_direct=True,
                depth=0,
            ),
        ],
        transitive_dependencies=[
            DependencyInfo(
                name="urllib3",
                ecosystem="python",
                version="2.0",
                is_direct=False,
                depth=1,
            ),
        ],
    )


@pytest.fixture
def sample_scores() -> dict[str, AnalysisResult | None]:
    """Create sample analysis results for testing."""
    healthy_result = AnalysisResult(
        repo_url="https://github.com/psf/requests",
        total_score=85,
        metrics=[
            Metric(
                name="bus_factor", score=90, max_score=100, message="Good", risk="None"
            ),
            Metric(
                name="maintainer_drain",
                score=80,
                max_score=100,
                message="OK",
                risk="Low",
            ),
        ],
    )

    monitor_result = AnalysisResult(
        repo_url="https://github.com/django/django",
        total_score=72,
        metrics=[
            Metric(
                name="bus_factor",
                score=70,
                max_score=100,
                message="Fair",
                risk="Medium",
            ),
        ],
    )

    return {
        "requests": healthy_result,
        "django": monitor_result,
        "urllib3": None,
    }


def test_build_networkx_graph(sample_dep_graph: DependencyGraph, sample_scores: dict):
    """Test building a NetworkX graph from dependency graph."""
    graph = build_networkx_graph(sample_dep_graph, sample_scores)

    assert isinstance(graph, nx.DiGraph)
    assert graph.number_of_nodes() == 3
    assert "requests" in graph.nodes
    assert "django" in graph.nodes
    assert "urllib3" in graph.nodes

    # Check node attributes
    requests_node = graph.nodes["requests"]
    assert requests_node["score"] == 85
    assert requests_node["health_status"] == "healthy"
    assert requests_node["is_direct"] is True

    django_node = graph.nodes["django"]
    assert django_node["score"] == 72
    assert django_node["health_status"] == "monitor"

    urllib3_node = graph.nodes["urllib3"]
    assert urllib3_node["score"] == 0
    assert urllib3_node["health_status"] == "unknown"


def test_plotly_visualizer_export_json(
    sample_dep_graph: DependencyGraph,
    sample_scores: dict,
    tmp_path: Path,
):
    """Test exporting graph as JSON."""
    graph = build_networkx_graph(sample_dep_graph, sample_scores)
    visualizer = PlotlyVisualizer(graph)

    output_file = tmp_path / "test_graph.json"
    visualizer.export_json(output_file)

    assert output_file.exists()

    with open(output_file) as f:
        data = json.load(f)

    assert "nodes" in data
    assert "edges" in data
    assert "stats" in data

    assert len(data["nodes"]) == 3
    assert data["stats"]["total_nodes"] == 3

    # Check node structure
    requests_node = next(n for n in data["nodes"] if n["id"] == "requests")
    assert requests_node["score"] == 85
    assert requests_node["health_status"] == "healthy"


def test_plotly_visualizer_health_distribution(
    sample_dep_graph: DependencyGraph,
    sample_scores: dict,
):
    """Test health status distribution calculation."""
    graph = build_networkx_graph(sample_dep_graph, sample_scores)
    visualizer = PlotlyVisualizer(graph)

    distribution = visualizer._get_health_distribution()

    assert distribution["healthy"] == 1
    assert distribution["monitor"] == 1
    assert distribution["unknown"] == 1
    assert distribution["needs_attention"] == 0


def test_plotly_visualizer_export_html(
    sample_dep_graph: DependencyGraph,
    sample_scores: dict,
    tmp_path: Path,
):
    """Test exporting graph as interactive HTML."""
    graph = build_networkx_graph(sample_dep_graph, sample_scores)
    visualizer = PlotlyVisualizer(graph)

    output_file = tmp_path / "test_graph.html"
    visualizer.export_html(output_file)

    assert output_file.exists()
    assert output_file.stat().st_size > 0

    # Check HTML content contains expected elements
    content = output_file.read_text()
    assert "plotly" in content.lower()
    assert "requests" in content
    assert "django" in content
