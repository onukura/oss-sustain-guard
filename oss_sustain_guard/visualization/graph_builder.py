"""Build NetworkX graph from DependencyGraph with sustainability scores.

Converts OSS Sustain Guard analysis results into a NetworkX directed graph
suitable for visualization and analysis.
"""

import networkx as nx

from oss_sustain_guard.core import AnalysisResult
from oss_sustain_guard.dependency_graph import DependencyGraph


def build_networkx_graph(
    dep_graph: DependencyGraph,
    scores: dict[str, AnalysisResult | None],
    direct_only: bool = False,
    max_depth: int | None = None,
) -> nx.DiGraph:
    """
    Build a NetworkX directed graph from dependency graph with scores.

    Creates nodes for each package with score/health metadata, and edges
    representing dependency relationships.

    Args:
        dep_graph: Parsed dependency graph from lockfile
        scores: Dict mapping package names to AnalysisResult (or None if unavailable)
        direct_only: If True, only include direct dependencies
        max_depth: If set, only include dependencies up to this depth (0=root, 1=direct, 2=first-level transitive, etc.)

    Returns:
        NetworkX DiGraph with nodes containing score attributes and edges
        representing dependencies
    """
    G = nx.DiGraph()

    # Build mapping from package name to DependencyInfo for quick lookup
    all_deps_list = dep_graph.direct_dependencies + dep_graph.transitive_dependencies

    # Apply filters
    if direct_only:
        all_deps_list = [dep for dep in all_deps_list if dep.is_direct]

    if max_depth is not None:
        all_deps_list = [dep for dep in all_deps_list if dep.depth <= max_depth]

    all_deps = {dep.name: dep for dep in all_deps_list}

    # Add nodes with attributes
    for pkg_name, dep_info in all_deps.items():
        score_result = scores.get(pkg_name)

        # Determine health status based on score
        if score_result is None:
            health_status = "unknown"
            score = 0
            max_score = 100
            metrics = {}
        else:
            score = score_result.total_score
            max_score = 100
            health_status = _get_health_status(score)
            metrics = {metric.name: metric.score for metric in score_result.metrics}

        node_attrs = {
            "name": pkg_name,
            "score": score,
            "max_score": max_score,
            "health_status": health_status,
            "is_direct": dep_info.is_direct,
            "depth": dep_info.depth,
            "version": dep_info.version or "unknown",
            "ecosystem": dep_info.ecosystem,
            "metrics": metrics,
            "repo_url": score_result.repo_url if score_result else None,
        }

        G.add_node(pkg_name, **node_attrs)

    # Add edges representing dependencies
    # Build edge graph from the dependency relationships
    # This requires analyzing which packages depend on which
    _add_dependency_edges(G, dep_graph)

    # Add dependencies and dependents to node attributes
    for node in G.nodes():
        # Dependencies: packages this node depends on (outgoing edges)
        dependencies = list(G.successors(node))
        # Dependents: packages that depend on this node (incoming edges)
        dependents = list(G.predecessors(node))

        G.nodes[node]["dependencies"] = dependencies
        G.nodes[node]["dependents"] = dependents

    return G


def _get_health_status(score: int) -> str:
    """Determine health status from score."""
    if score < 50:
        return "needs_attention"
    elif score < 80:
        return "monitor"
    else:
        return "healthy"


def _add_dependency_edges(G: nx.DiGraph, dep_graph: DependencyGraph) -> None:
    """Add edges to graph representing dependency relationships.

    Uses explicit edges from DependencyGraph.edges if available,
    otherwise falls back to heuristic-based edge inference.

    Only adds edges where both source and target nodes exist in the graph.
    """
    # Get set of nodes that exist in the graph
    existing_nodes = set(G.nodes())

    # Use explicit edges if provided
    if dep_graph.edges:
        for edge in dep_graph.edges:
            # Only add edge if both nodes exist in the filtered graph
            if edge.source in existing_nodes and edge.target in existing_nodes:
                G.add_edge(
                    edge.source,
                    edge.target,
                    type="explicit",
                    version_spec=edge.version_spec,
                )
    else:
        # Fallback: heuristic-based edges for graphs without explicit edge info
        _add_heuristic_edges(G, dep_graph)


def _add_heuristic_edges(G: nx.DiGraph, dep_graph: DependencyGraph) -> None:
    """Add edges using heuristics when explicit edge data is not available.

    This is a fallback for legacy lockfiles or parsers that don't provide
    explicit edge information.

    Only adds edges where both source and target nodes exist in the graph.
    """
    # Get set of nodes that exist in the graph
    existing_nodes = set(G.nodes())

    # Group by depth
    direct_pkgs = {
        dep.name for dep in dep_graph.direct_dependencies if dep.name in existing_nodes
    }
    transitive_by_depth: dict[int, set[str]] = {}

    for dep in dep_graph.transitive_dependencies:
        if dep.name in existing_nodes:
            if dep.depth not in transitive_by_depth:
                transitive_by_depth[dep.depth] = set()
            transitive_by_depth[dep.depth].add(dep.name)

    # Add edges from direct to their transitive dependencies
    if direct_pkgs and 1 in transitive_by_depth:
        for direct_pkg in direct_pkgs:
            for transitive_pkg in transitive_by_depth[1]:
                if direct_pkg in existing_nodes and transitive_pkg in existing_nodes:
                    G.add_edge(direct_pkg, transitive_pkg, type="inferred")

    # Add edges between transitive depths
    depths = sorted(transitive_by_depth.keys())
    for i in range(len(depths) - 1):
        current_depth = depths[i]
        next_depth = depths[i + 1]
        if current_depth + 1 == next_depth:
            for pkg_current in transitive_by_depth[current_depth]:
                for pkg_next in transitive_by_depth[next_depth]:
                    if pkg_current in existing_nodes and pkg_next in existing_nodes:
                        if not G.has_edge(pkg_current, pkg_next):
                            G.add_edge(pkg_current, pkg_next, type="inferred")
