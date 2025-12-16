"""
Test dependency graph analysis functionality.
"""

import tempfile
from pathlib import Path

from oss_sustain_guard.dependency_graph import (
    DependencyGraph,
    DependencyInfo,
    filter_high_value_dependencies,
    parse_python_lockfile,
)


def test_parse_uv_lock():
    """Test parsing a minimal uv.lock file."""
    # Create a minimal uv.lock file
    uv_lock_content = """
[[package]]
name = "click"
version = "8.1.0"

[[package]]
name = "requests"
version = "2.28.0"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "uv.lock"
        lockfile_path.write_text(uv_lock_content)

        # Create empty pyproject.toml for root name detection
        (Path(tmpdir) / "pyproject.toml").write_text(
            '[project]\nname = "test-project"\n'
        )

        result = parse_python_lockfile(lockfile_path)

        assert result is not None
        assert result.ecosystem == "python"
        assert result.root_package == "test-project"
        assert len(result.direct_dependencies) > 0


def test_parse_nonexistent_lockfile():
    """Test parsing a non-existent lockfile returns None."""
    result = parse_python_lockfile("/nonexistent/path/uv.lock")
    assert result is None


def test_dependency_info_creation():
    """Test creating DependencyInfo objects."""
    dep = DependencyInfo(
        name="requests",
        ecosystem="python",
        version="2.28.0",
        is_direct=True,
        depth=0,
    )

    assert dep.name == "requests"
    assert dep.ecosystem == "python"
    assert dep.version == "2.28.0"
    assert dep.is_direct is True
    assert dep.depth == 0


def test_filter_high_value_dependencies():
    """Test filtering dependencies by count."""
    deps = [
        DependencyInfo("a", "python", "1.0", True, 0),
        DependencyInfo("b", "python", "1.0", True, 0),
        DependencyInfo("c", "python", "1.0", True, 0),
    ]

    graph = DependencyGraph(
        root_package="test",
        ecosystem="python",
        direct_dependencies=deps,
        transitive_dependencies=[],
    )

    filtered = filter_high_value_dependencies(graph, max_count=2)

    assert len(filtered) == 2
    assert filtered[0].name == "a"
    assert filtered[1].name == "b"


def test_dependency_graph_creation():
    """Test creating a DependencyGraph object."""
    direct = [
        DependencyInfo("requests", "python", "2.28.0", True, 0),
        DependencyInfo("click", "python", "8.1.0", True, 0),
    ]
    transitive = [DependencyInfo("certifi", "python", "2022.9.24", False, 1)]

    graph = DependencyGraph(
        root_package="myapp",
        ecosystem="python",
        direct_dependencies=direct,
        transitive_dependencies=transitive,
    )

    assert graph.root_package == "myapp"
    assert graph.ecosystem == "python"
    assert len(graph.direct_dependencies) == 2
    assert len(graph.transitive_dependencies) == 1
