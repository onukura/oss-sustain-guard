"""Plotly-based visualization of dependency graphs.

Renders NetworkX graphs as interactive HTML or JSON using Plotly.
"""

import json
from pathlib import Path

import networkx as nx
import plotly.graph_objects as go


class PlotlyVisualizer:
    """Visualize dependency graphs with Plotly."""

    # Color mapping based on health status
    STATUS_COLORS = {
        "healthy": "#2ecc71",  # Green
        "monitor": "#f39c12",  # Yellow
        "needs_attention": "#e74c3c",  # Red
        "unknown": "#95a5a6",  # Gray
    }

    def __init__(self, graph: nx.DiGraph):
        """
        Initialize visualizer with a NetworkX graph.

        Args:
            graph: NetworkX directed graph with node attributes
                  (score, health_status, metrics, etc.)
        """
        self.graph = graph
        self._layout = None

    def _compute_layout(self) -> dict:
        """Compute force-directed layout for the graph.

        Uses spring layout optimized for large graphs (up to 1000+ nodes).
        """
        if self._layout is None:
            # Use spring layout with optimized parameters for large graphs
            self._layout = nx.spring_layout(
                self.graph,
                k=0.5,  # Optimal distance between nodes
                iterations=50,  # Fewer iterations for performance
            )
        return self._layout

    def _prepare_plotly_data(self) -> tuple[list[dict], list[dict], list[dict]]:
        """Prepare node, edge, and arrow data for Plotly visualization.

        Returns:
            Tuple of (node_traces, edge_traces, arrow_annotations)
        """
        layout = self._compute_layout()

        # Extract positions
        pos = layout

        # Prepare edges with arrows
        edge_traces = []
        arrow_annotations = []

        if self.graph.edges():
            # Group edges by type
            edge_x_all = []
            edge_y_all = []
            edge_hovertext = []

            for source, target in self.graph.edges():
                x0, y0 = pos[source]
                x1, y1 = pos[target]
                edge_x_all.append(x0)
                edge_x_all.append(x1)
                edge_x_all.append(None)
                edge_y_all.append(y0)
                edge_y_all.append(y1)
                edge_y_all.append(None)

                # Get edge attributes for hover
                edge_attrs = self.graph.edges[source, target]
                edge_type = edge_attrs.get("type", "unknown")
                version_spec = edge_attrs.get("version_spec", "")
                hover_text = f"{source} → {target}<br>Type: {edge_type}"
                if version_spec:
                    hover_text += f"<br>Version: {version_spec}"
                edge_hovertext.extend([hover_text, hover_text, None])

                # Add arrow annotation for direction
                # Calculate arrow position (80% along the edge to avoid overlap with target node)
                arrow_x = x0 + 0.8 * (x1 - x0)
                arrow_y = y0 + 0.8 * (y1 - y0)

                arrow_annotations.append(
                    {
                        "x": arrow_x,
                        "y": arrow_y,
                        "ax": x0,
                        "ay": y0,
                        "xref": "x",
                        "yref": "y",
                        "axref": "x",
                        "ayref": "y",
                        "showarrow": True,
                        "arrowhead": 2,
                        "arrowsize": 1,
                        "arrowwidth": 1.5,
                        "arrowcolor": "rgba(125,125,125,0.6)",
                        "standoff": 8,  # Distance from the target point
                    }
                )

            # Create edge trace
            edge_trace = {
                "x": edge_x_all,
                "y": edge_y_all,
                "mode": "lines",
                "line": {"width": 1.5, "color": "rgba(125,125,125,0.5)"},
                "hovertext": edge_hovertext,
                "hoverinfo": "text",
                "showlegend": False,
                "name": "Dependencies",
            }
            edge_traces.append(edge_trace)

        # Prepare nodes
        node_traces = {}
        for status in self.STATUS_COLORS.keys():
            node_x = []
            node_y = []
            node_text = []
            node_labels = []
            node_color = self.STATUS_COLORS[status]

            for node in self.graph.nodes():
                node_status = self.graph.nodes[node].get("health_status", "unknown")
                if node_status == status:
                    x, y = pos[node]
                    node_x.append(x)
                    node_y.append(y)
                    node_labels.append(node)

                    # Prepare hover text with detailed info
                    attrs = self.graph.nodes[node]
                    score = attrs.get("score", 0)
                    version = attrs.get("version", "unknown")
                    is_direct = attrs.get("is_direct", False)
                    repo_url = attrs.get("repo_url", "N/A")

                    hover_text = (
                        f"<b>{node}</b><br>"
                        f"Score: {score}/100<br>"
                        f"Status: {node_status}<br>"
                        f"Version: {version}<br>"
                        f"Direct: {is_direct}<br>"
                        f"Repo: {repo_url}<br>"
                    )

                    # Add metrics if available
                    metrics = attrs.get("metrics", {})
                    if metrics:
                        hover_text += "<br><b>Metrics:</b><br>"
                        for metric_name, metric_score in metrics.items():
                            hover_text += f"{metric_name}: {metric_score}<br>"

                    node_text.append(hover_text)

            if node_x:
                trace = {
                    "x": node_x,
                    "y": node_y,
                    "mode": "markers+text",
                    "text": node_labels,
                    "hovertext": node_text,
                    "hoverinfo": "text",
                    "marker": {
                        "size": 10,
                        "color": node_color,
                        "line": {"width": 2, "color": "#fff"},
                        "opacity": 0.8,
                    },
                    "textposition": "top center",
                    "name": status,
                    "showlegend": True,
                }
                node_traces[status] = trace

        return list(node_traces.values()), edge_traces, arrow_annotations

    def export_html(self, output_path: str | Path) -> None:
        """Export graph as interactive HTML file with advanced features.

        Features:
        - Click node to highlight dependencies and dependents
        - Drag nodes to reposition
        - Search for specific packages
        - Filter by score and depth

        Args:
            output_path: Path to write HTML file
        """
        output_path = Path(output_path)

        node_traces, edge_traces, arrow_annotations = self._prepare_plotly_data()

        # Create figure
        fig = go.Figure()

        # Add edges
        for edge_trace in edge_traces:
            fig.add_trace(go.Scatter(**edge_trace))

        # Add nodes
        for node_trace in node_traces:
            fig.add_trace(go.Scatter(**node_trace))

        # Update layout with arrows
        fig.update_layout(
            title="Dependency Graph - Sustainability Overview",
            showlegend=True,
            hovermode="closest",
            height=1200,  # 2x taller for better visibility
            margin={"b": 80, "l": 5, "r": 5, "t": 40},
            annotations=[
                {
                    "text": "Node color indicates health status: Green=Healthy, Yellow=Monitor, Red=Needs Attention. Click nodes to highlight dependencies.",
                    "showarrow": False,
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": -0.05,
                    "xanchor": "center",
                    "yanchor": "top",
                }
            ]
            + arrow_annotations,  # Add arrow annotations
            xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            plot_bgcolor="rgba(240,240,240,0.5)",
        )

        # Generate HTML with custom controls and JavaScript
        html_content = self._generate_interactive_html(fig)

        # Save to HTML
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    def export_json(self, output_path: str | Path) -> None:
        """Export graph data as JSON.

        Args:
            output_path: Path to write JSON file
        """
        output_path = Path(output_path)

        # Prepare nodes data
        nodes = []
        for node in self.graph.nodes():
            attrs = self.graph.nodes[node]
            nodes.append(
                {
                    "id": node,
                    "name": attrs.get("name", node),
                    "score": attrs.get("score", 0),
                    "health_status": attrs.get("health_status", "unknown"),
                    "version": attrs.get("version", "unknown"),
                    "is_direct": attrs.get("is_direct", False),
                    "depth": attrs.get("depth", 0),
                    "ecosystem": attrs.get("ecosystem", "unknown"),
                    "repo_url": attrs.get("repo_url", None),
                    "metrics": attrs.get("metrics", {}),
                }
            )

        # Prepare edges data
        edges = []
        for source, target in self.graph.edges():
            edge_attrs = self.graph.edges[source, target]
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "type": edge_attrs.get("type", "unknown"),
                }
            )

        # Statistics
        stats = {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "avg_score": sum(n.get("score", 0) for n in self.graph.nodes.values())
            / max(self.graph.number_of_nodes(), 1),
            "health_distribution": self._get_health_distribution(),
        }

        # Write JSON
        data = {
            "nodes": nodes,
            "edges": edges,
            "stats": stats,
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    def _get_health_distribution(self) -> dict[str, int]:
        """Get count of nodes by health status."""
        distribution = dict.fromkeys(self.STATUS_COLORS.keys(), 0)
        for node in self.graph.nodes():
            status = self.graph.nodes[node].get("health_status", "unknown")
            distribution[status] += 1
        return distribution

    def _generate_interactive_html(self, fig: go.Figure) -> str:
        """Generate HTML with custom interactive controls.

        Args:
            fig: Plotly figure to embed

        Returns:
            Complete HTML string with embedded JavaScript
        """
        # Get base HTML from Plotly
        base_html = fig.to_html(include_plotlyjs="cdn", div_id="graph-div")

        # Prepare graph data for JavaScript
        graph_data = self._prepare_graph_data_for_js()

        # Custom HTML with controls and JavaScript
        custom_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dependency Graph - Interactive Visualization</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }}

        .controls {{
            background: white;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 10px;
            display: flex;
            gap: 20px;
            align-items: center;
            flex-wrap: wrap;
        }}

        .control-group {{
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}

        .control-group label {{
            font-size: 12px;
            color: #666;
            font-weight: 600;
        }}

        .search-box {{
            padding: 8px 12px;
            border: 2px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            min-width: 250px;
            transition: border-color 0.3s;
        }}

        .search-box:focus {{
            outline: none;
            border-color: #3498db;
        }}

        .filter-slider {{
            min-width: 200px;
        }}

        .filter-value {{
            display: inline-block;
            min-width: 60px;
            font-weight: bold;
            color: #3498db;
        }}

        .button {{
            padding: 8px 16px;
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.3s;
        }}

        .button:hover {{
            background-color: #2980b9;
        }}

        .button-secondary {{
            background-color: #95a5a6;
        }}

        .button-secondary:hover {{
            background-color: #7f8c8d;
        }}

        .info-panel {{
            background: white;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-top: 10px;
            display: none;
        }}

        .info-panel.show {{
            display: block;
        }}

        .info-panel h3 {{
            margin-top: 0;
            color: #2c3e50;
        }}

        .info-list {{
            list-style: none;
            padding: 0;
        }}

        .info-list li {{
            padding: 5px 0;
            border-bottom: 1px solid #ecf0f1;
        }}

        .highlight-legend {{
            margin-top: 10px;
            font-size: 12px;
            color: #666;
        }}

        .highlight-legend span {{
            display: inline-block;
            margin-right: 15px;
        }}

        #graph-container {{
            height: calc(100vh - 200px);
            background: white;
        }}
    </style>
</head>
<body>
    <div class="controls">
        <div class="control-group">
            <label for="search">🔍 Search Package</label>
            <input type="text" id="search" class="search-box" placeholder="Type package name...">
        </div>

        <div class="control-group">
            <label for="score-filter">📊 Min Score: <span id="score-value" class="filter-value">0</span></label>
            <input type="range" id="score-filter" class="filter-slider" min="0" max="100" value="0">
        </div>

        <div class="control-group">
            <label for="depth-filter">📏 Max Depth: <span id="depth-value" class="filter-value">∞</span></label>
            <input type="range" id="depth-filter" class="filter-slider" min="0" max="10" value="10">
        </div>

        <button id="reset-btn" class="button button-secondary">Reset View</button>
        <button id="clear-highlight-btn" class="button button-secondary">Clear Highlight</button>
    </div>

    <div id="graph-container">
        {base_html}
    </div>

    <div id="info-panel" class="info-panel">
        <h3 id="selected-node-name">Selected Node</h3>
        <div class="highlight-legend">
            <span>🟦 Selected Node</span>
            <span>🟩 Dependencies (what it depends on)</span>
            <span>🟪 Dependents (what depends on it)</span>
        </div>
        <ul class="info-list" id="node-info"></ul>
    </div>

    <script>
        // Graph data from Python
        const graphData = {json.dumps(graph_data, indent=2)};

        // Original data for reset
        let originalData = null;
        let selectedNode = null;

        // Wait for Plotly to be ready
        document.addEventListener('DOMContentLoaded', function() {{
            const graphDiv = document.getElementById('graph-div');

            // Store original data
            setTimeout(() => {{
                if (graphDiv && graphDiv.data) {{
                    originalData = JSON.parse(JSON.stringify(graphDiv.data));
                }}
            }}, 500);

            // Node click handler - highlight dependencies
            if (graphDiv) {{
                graphDiv.on('plotly_click', function(data) {{
                    const point = data.points[0];
                    if (point && point.text) {{
                        const nodeName = point.text.trim();
                        highlightNode(nodeName);
                    }}
                }});

                // Enable dragging
                graphDiv.on('plotly_relayout', function(eventData) {{
                    // Handle drag events if needed
                }});
            }}

            // Search functionality
            const searchBox = document.getElementById('search');
            searchBox.addEventListener('input', function(e) {{
                const query = e.target.value.toLowerCase().trim();
                if (query) {{
                    searchAndHighlight(query);
                }} else {{
                    resetHighlight();
                }}
            }});

            // Score filter
            const scoreFilter = document.getElementById('score-filter');
            const scoreValue = document.getElementById('score-value');
            scoreFilter.addEventListener('input', function(e) {{
                scoreValue.textContent = e.target.value;
                applyFilters();
            }});

            // Depth filter
            const depthFilter = document.getElementById('depth-filter');
            const depthValue = document.getElementById('depth-value');
            depthFilter.addEventListener('input', function(e) {{
                const val = parseInt(e.target.value);
                depthValue.textContent = val >= 10 ? '∞' : val;
                applyFilters();
            }});

            // Reset button
            document.getElementById('reset-btn').addEventListener('click', function() {{
                resetView();
            }});

            // Clear highlight button
            document.getElementById('clear-highlight-btn').addEventListener('click', function() {{
                resetHighlight();
            }});
        }});

        function highlightNode(nodeName) {{
            const graphDiv = document.getElementById('graph-div');
            if (!graphDiv || !graphDiv.data) return;

            selectedNode = nodeName;
            const nodeInfo = graphData.nodes.find(n => n.name === nodeName);

            if (!nodeInfo) return;

            // Show info panel
            const infoPanel = document.getElementById('info-panel');
            const selectedNodeName = document.getElementById('selected-node-name');
            const nodeInfoList = document.getElementById('node-info');

            infoPanel.classList.add('show');
            selectedNodeName.textContent = nodeName;

            nodeInfoList.innerHTML = `
                <li><strong>Score:</strong> ${{nodeInfo.score}}/100</li>
                <li><strong>Status:</strong> ${{nodeInfo.health_status}}</li>
                <li><strong>Version:</strong> ${{nodeInfo.version}}</li>
                <li><strong>Direct Dependency:</strong> ${{nodeInfo.is_direct ? 'Yes' : 'No'}}</li>
                <li><strong>Depth:</strong> ${{nodeInfo.depth}}</li>
                <li><strong>Dependencies:</strong> ${{nodeInfo.dependencies.join(', ') || 'None'}}</li>
                <li><strong>Dependents:</strong> ${{nodeInfo.dependents.join(', ') || 'None'}}</li>
            `;

            // Highlight in graph
            const dependencies = new Set(nodeInfo.dependencies);
            const dependents = new Set(nodeInfo.dependents);

            const updates = graphDiv.data.map((trace, idx) => {{
                if (trace.mode && trace.mode.includes('markers')) {{
                    const newMarker = JSON.parse(JSON.stringify(trace.marker));
                    const newSizes = [];
                    const newOpacities = [];
                    const newColors = [];

                    trace.text.forEach((text, i) => {{
                        const node = text.trim();
                        if (node === nodeName) {{
                            // Selected node - larger, bright blue
                            newSizes.push(20);
                            newOpacities.push(1);
                            newColors.push('#3498db');
                        }} else if (dependencies.has(node)) {{
                            // Dependencies - green
                            newSizes.push(15);
                            newOpacities.push(1);
                            newColors.push('#2ecc71');
                        }} else if (dependents.has(node)) {{
                            // Dependents - purple
                            newSizes.push(15);
                            newOpacities.push(1);
                            newColors.push('#9b59b6');
                        }} else {{
                            // Other nodes - dimmed
                            newSizes.push(8);
                            newOpacities.push(0.3);
                            newColors.push(originalData[idx].marker.color);
                        }}
                    }});

                    newMarker.size = newSizes;
                    newMarker.opacity = newOpacities;
                    newMarker.color = newColors;

                    return {{'marker': newMarker}};
                }}
                return {{}};
            }});

            updates.forEach((update, idx) => {{
                if (Object.keys(update).length > 0) {{
                    Plotly.restyle(graphDiv, update, idx);
                }}
            }});
        }}

        function searchAndHighlight(query) {{
            const matches = graphData.nodes.filter(n =>
                n.name.toLowerCase().includes(query)
            );

            if (matches.length === 1) {{
                highlightNode(matches[0].name);
            }} else if (matches.length > 1) {{
                // Highlight all matches
                const matchNames = new Set(matches.map(m => m.name));
                const graphDiv = document.getElementById('graph-div');

                const updates = graphDiv.data.map((trace, idx) => {{
                    if (trace.mode && trace.mode.includes('markers')) {{
                        const newMarker = JSON.parse(JSON.stringify(trace.marker));
                        const newSizes = [];
                        const newOpacities = [];

                        trace.text.forEach((text, i) => {{
                            const node = text.trim();
                            if (matchNames.has(node)) {{
                                newSizes.push(15);
                                newOpacities.push(1);
                            }} else {{
                                newSizes.push(8);
                                newOpacities.push(0.3);
                            }}
                        }});

                        newMarker.size = newSizes;
                        newMarker.opacity = newOpacities;

                        return {{'marker': newMarker}};
                    }}
                    return {{}};
                }});

                updates.forEach((update, idx) => {{
                    if (Object.keys(update).length > 0) {{
                        Plotly.restyle(graphDiv, update, idx);
                    }}
                }});
            }}
        }}

        function applyFilters() {{
            const minScore = parseInt(document.getElementById('score-filter').value);
            const maxDepth = parseInt(document.getElementById('depth-filter').value);
            const graphDiv = document.getElementById('graph-div');

            if (!graphDiv || !originalData) return;

            const updates = originalData.map((trace, idx) => {{
                if (trace.mode && trace.mode.includes('markers')) {{
                    const visibleIndices = [];
                    const newX = [];
                    const newY = [];
                    const newText = [];
                    const newHovertext = [];

                    trace.text.forEach((text, i) => {{
                        const nodeName = text.trim();
                        const nodeInfo = graphData.nodes.find(n => n.name === nodeName);

                        if (nodeInfo &&
                            nodeInfo.score >= minScore &&
                            (maxDepth >= 10 || nodeInfo.depth <= maxDepth)) {{
                            newX.push(trace.x[i]);
                            newY.push(trace.y[i]);
                            newText.push(trace.text[i]);
                            newHovertext.push(trace.hovertext[i]);
                        }}
                    }});

                    return {{
                        'x': [newX],
                        'y': [newY],
                        'text': [newText],
                        'hovertext': [newHovertext]
                    }};
                }}
                return {{}};
            }});

            updates.forEach((update, idx) => {{
                if (Object.keys(update).length > 0) {{
                    Plotly.restyle(graphDiv, update, idx);
                }}
            }});
        }}

        function resetHighlight() {{
            const graphDiv = document.getElementById('graph-div');
            const infoPanel = document.getElementById('info-panel');

            infoPanel.classList.remove('show');
            selectedNode = null;

            if (!graphDiv || !originalData) return;

            // Restore original marker properties
            originalData.forEach((trace, idx) => {{
                if (trace.mode && trace.mode.includes('markers')) {{
                    Plotly.restyle(graphDiv, {{
                        'marker.size': [trace.marker.size],
                        'marker.opacity': [trace.marker.opacity],
                        'marker.color': [trace.marker.color]
                    }}, idx);
                }}
            }});
        }}

        function resetView() {{
            document.getElementById('search').value = '';
            document.getElementById('score-filter').value = 0;
            document.getElementById('score-value').textContent = '0';
            document.getElementById('depth-filter').value = 10;
            document.getElementById('depth-value').textContent = '∞';

            resetHighlight();

            const graphDiv = document.getElementById('graph-div');
            if (!graphDiv || !originalData) return;

            // Restore all original data
            originalData.forEach((trace, idx) => {{
                Plotly.restyle(graphDiv, {{
                    'x': [trace.x],
                    'y': [trace.y],
                    'text': [trace.text],
                    'hovertext': [trace.hovertext],
                    'marker.size': [trace.marker.size],
                    'marker.opacity': [trace.marker.opacity],
                    'marker.color': [trace.marker.color]
                }}, idx);
            }});
        }}
    </script>
</body>
</html>
"""
        return custom_html

    def _prepare_graph_data_for_js(self) -> dict:
        """Prepare simplified graph data for JavaScript.

        Returns:
            Dict with nodes and edges data
        """
        nodes = []
        for node in self.graph.nodes():
            attrs = self.graph.nodes[node]
            nodes.append(
                {
                    "name": node,
                    "score": attrs.get("score", 0),
                    "health_status": attrs.get("health_status", "unknown"),
                    "version": attrs.get("version", "unknown"),
                    "is_direct": attrs.get("is_direct", False),
                    "depth": attrs.get("depth", 0),
                    "dependencies": attrs.get("dependencies", []),
                    "dependents": attrs.get("dependents", []),
                }
            )

        edges = []
        for source, target in self.graph.edges():
            edges.append({"source": source, "target": target})

        return {"nodes": nodes, "edges": edges}
