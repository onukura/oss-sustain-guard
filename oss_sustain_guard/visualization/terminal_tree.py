"""Terminal tree visualization for dependency graphs."""

import networkx as nx
from rich.console import Console
from rich.tree import Tree


class TerminalTreeVisualizer:
    """Visualize dependency graphs as colored trees in the terminal."""

    def __init__(self, graph: nx.DiGraph):
        """Initialize visualizer with NetworkX graph.

        Args:
            graph: NetworkX DiGraph with node attributes (name, score, health_status, etc.)
        """
        self.graph = graph
        self.console = Console()

    def display(self) -> None:
        """Display the dependency tree in the terminal with colors based on health scores."""
        if not self.graph.nodes():
            self.console.print("[yellow]No dependencies to display[/yellow]")
            return

        # Find root nodes (nodes with no incoming edges)
        root_nodes = [
            node for node in self.graph.nodes() if self.graph.in_degree(node) == 0
        ]

        if not root_nodes:
            # If no clear root (circular dependencies), pick the first node
            root_nodes = [list(self.graph.nodes())[0]]

        # Display health distribution summary
        stats = self._get_health_distribution()
        self.console.print("\n[bold cyan]Dependency Tree:[/bold cyan]")
        self.console.print(
            f"[dim]Total: {self.graph.number_of_nodes()} packages | "
            f"Healthy: {stats.get('healthy', 0)} | "
            f"Monitor: {stats.get('monitor', 0)} | "
            f"Needs attention: {stats.get('needs_attention', 0)} | "
            f"Unknown: {stats.get('unknown', 0)}[/dim]"
        )
        self.console.print(
            "[dim]Legend: [green]■[/green] Healthy (≥80) | "
            "[yellow]■[/yellow] Monitor (50-79) | "
            "[red]■[/red] Needs attention (<50) | "
            "[bold magenta]*[/bold magenta] Direct dependency[/dim]\n"
        )

        # Build and display tree for each root
        for root_node in root_nodes:
            tree = self._build_tree(root_node, set())
            self.console.print(tree)

    def _build_tree(self, node: str, visited: set) -> Tree:
        """Recursively build rich Tree from graph node.

        Args:
            node: Node name to build tree from
            visited: Set of already visited nodes (to detect cycles)

        Returns:
            Rich Tree object
        """
        # Get node attributes
        attrs = self.graph.nodes[node]
        name = attrs.get("name", node)
        score = attrs.get("score", 0)
        health_status = attrs.get("health_status", "unknown")
        version = attrs.get("version", "")
        is_direct = attrs.get("is_direct", False)

        # Format node label with color based on health status
        color = self._get_health_color(health_status)
        label = f"[{color}]{name}[/{color}]"

        # Add version if available
        if version and version != "unknown":
            label += f" [dim]{version}[/dim]"

        # Add score if available (already on 0-100 scale)
        if score > 0:
            label += f" [dim](score: {score:.0f})[/dim]"

        # Add direct dependency marker
        if is_direct:
            label += " [bold magenta]*[/bold magenta]"

        # Create tree node
        tree = Tree(label)

        # Mark as visited
        visited.add(node)

        # Add children (dependencies)
        children = list(self.graph.successors(node))
        for child in sorted(children):  # Sort alphabetically
            if child in visited:
                # Circular dependency - mark but don't recurse
                child_attrs = self.graph.nodes[child]
                child_name = child_attrs.get("name", child)
                tree.add(f"[dim]{child_name} (circular reference)[/dim]")
            else:
                child_tree = self._build_tree(child, visited.copy())
                tree.add(child_tree)

        return tree

    def _get_health_color(self, health_status: str) -> str:
        """Get color for health status.

        Args:
            health_status: Health status string

        Returns:
            Rich color name
        """
        color_map = {
            "healthy": "green",
            "monitor": "yellow",
            "needs_attention": "red",
            "unknown": "dim",
        }
        return color_map.get(health_status, "dim")

    def _get_health_distribution(self) -> dict[str, int]:
        """Get count of packages by health status.

        Returns:
            Dict mapping health status to count
        """
        distribution = {"healthy": 0, "monitor": 0, "needs_attention": 0, "unknown": 0}

        for node in self.graph.nodes():
            attrs = self.graph.nodes[node]
            status = attrs.get("health_status", "unknown")
            distribution[status] = distribution.get(status, 0) + 1

        return distribution
