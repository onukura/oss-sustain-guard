"""Base class for external tool wrappers."""

from abc import ABC, abstractmethod

from oss_sustain_guard.dependency_graph import DependencyGraph


class ExternalTool(ABC):
    """Abstract base class for external dependency resolution tools."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this tool is available on the system.

        Returns:
            True if the tool is installed and can be executed, False otherwise.
        """
        pass

    @abstractmethod
    async def resolve_tree(
        self, package: str, version: str | None = None
    ) -> DependencyGraph:
        """Resolve the dependency tree for a package.

        Args:
            package: Package name to resolve dependencies for
            version: Optional specific version to resolve (defaults to latest)

        Returns:
            DependencyGraph containing all resolved dependencies

        Raises:
            RuntimeError: If tool execution fails
            ValueError: If package is invalid or not found
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the tool name (e.g., 'uv', 'pip', 'npm')."""
        pass

    @property
    @abstractmethod
    def ecosystem(self) -> str:
        """Get the ecosystem this tool supports (e.g., 'python', 'javascript')."""
        pass
