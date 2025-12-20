"""
Test dependency graph analysis functionality.
"""

import json
import tempfile
from pathlib import Path

from oss_sustain_guard.dependency_graph import (
    DependencyGraph,
    DependencyInfo,
    filter_high_value_dependencies,
    get_all_dependencies,
    parse_javascript_lockfile,
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


def test_parse_poetry_lock():
    """Test parsing a Poetry lock file."""
    poetry_lock_content = """
[[package]]
name = "click"
version = "8.1.0"

[[package]]
name = "requests"
version = "2.28.0"

[[package]]
name = "certifi"
version = "2022.9.24"
"""

    pyproject_content = """
[tool.poetry]
name = "test-poetry-project"

[tool.poetry.dependencies]
python = "^3.10"
click = "^8.1.0"
requests = "^2.28.0"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "poetry.lock"
        lockfile_path.write_text(poetry_lock_content)

        pyproject_path = Path(tmpdir) / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)

        result = parse_python_lockfile(lockfile_path)

        assert result is not None
        assert result.ecosystem == "python"
        assert result.root_package == "test-poetry-project"
        assert len(result.direct_dependencies) == 2
        assert len(result.transitive_dependencies) == 1


def test_parse_pipfile_lock():
    """Test parsing a Pipfile.lock file."""
    pipfile_lock_content = {
        "_meta": {
            "hash": {"sha256": "example"},
            "pipfile-spec": 6,
            "requires": {"python_version": "3.10"},
        },
        "default": {
            "click": {"version": "==8.1.0"},
            "requests": {"version": "==2.28.0"},
        },
        "develop": {
            "pytest": {"version": "==7.2.0"},
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "Pipfile.lock"
        lockfile_path.write_text(json.dumps(pipfile_lock_content))

        result = parse_python_lockfile(lockfile_path)

        assert result is not None
        assert result.ecosystem == "python"
        assert len(result.direct_dependencies) == 2
        assert len(result.transitive_dependencies) == 1
        assert result.direct_dependencies[0].version == "8.1.0"


def test_parse_unsupported_lockfile():
    """Test parsing an unsupported lockfile returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "unsupported.lock"
        lockfile_path.write_text("# unsupported format")

        result = parse_python_lockfile(lockfile_path)

        assert result is None


def test_parse_corrupted_lockfile():
    """Test parsing a corrupted lockfile returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "poetry.lock"
        lockfile_path.write_text("invalid toml content {{[[")

        result = parse_python_lockfile(lockfile_path)

        assert result is None


def test_parse_npm_lock():
    """Test parsing a package-lock.json file."""
    npm_lock_content = {
        "name": "test-npm-project",
        "version": "1.0.0",
        "lockfileVersion": 3,
        "packages": {
            "": {
                "name": "test-npm-project",
                "version": "1.0.0",
            },
            "node_modules/lodash": {
                "version": "4.17.21",
            },
            "node_modules/axios": {
                "version": "1.4.0",
            },
            "node_modules/axios/node_modules/follow-redirects": {
                "version": "1.15.2",
            },
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "package-lock.json"
        lockfile_path.write_text(json.dumps(npm_lock_content))

        package_json_path = Path(tmpdir) / "package.json"
        package_json_path.write_text(json.dumps({"name": "test-npm-project"}))

        result = parse_javascript_lockfile(lockfile_path)

        assert result is not None
        assert result.ecosystem == "javascript"
        assert result.root_package == "test-npm-project"
        assert len(result.direct_dependencies) == 2
        assert len(result.transitive_dependencies) == 1


def test_parse_yarn_lock():
    """Test parsing a yarn.lock file."""
    yarn_lock_content = """
# THIS IS AN AUTOGENERATED FILE. DO NOT EDIT THIS FILE DIRECTLY.
# yarn lockfile v1

lodash@^4.17.21:
  version "4.17.21"
  resolved "https://registry.yarnpkg.com/lodash/-/lodash-4.17.21.tgz"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "yarn.lock"
        lockfile_path.write_text(yarn_lock_content)

        package_json_path = Path(tmpdir) / "package.json"
        package_json_path.write_text(json.dumps({"name": "test-yarn-project"}))

        result = parse_javascript_lockfile(lockfile_path)

        assert result is not None
        assert result.ecosystem == "javascript"
        assert result.root_package == "test-yarn-project"


def test_parse_pnpm_lock():
    """Test parsing a pnpm-lock.yaml file."""
    pnpm_lock_content = """
lockfileVersion: '6.0'

dependencies:
  lodash:
    specifier: ^4.17.21
    version: 4.17.21
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "pnpm-lock.yaml"
        lockfile_path.write_text(pnpm_lock_content)

        package_json_path = Path(tmpdir) / "package.json"
        package_json_path.write_text(json.dumps({"name": "test-pnpm-project"}))

        result = parse_javascript_lockfile(lockfile_path)

        assert result is not None
        assert result.ecosystem == "javascript"
        assert result.root_package == "test-pnpm-project"


def test_get_all_dependencies_multiple_lockfiles():
    """Test extracting dependencies from multiple lockfiles."""
    uv_lock_content = """
[[package]]
name = "click"
version = "8.1.0"
"""

    npm_lock_content = {
        "name": "test-project",
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "test-project"},
            "node_modules/lodash": {"version": "4.17.21"},
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        uv_lock_path = Path(tmpdir) / "uv.lock"
        uv_lock_path.write_text(uv_lock_content)

        npm_lock_path = Path(tmpdir) / "package-lock.json"
        npm_lock_path.write_text(json.dumps(npm_lock_content))

        (Path(tmpdir) / "pyproject.toml").write_text(
            '[project]\nname = "test-python"\n'
        )
        (Path(tmpdir) / "package.json").write_text(json.dumps({"name": "test-js"}))

        results = get_all_dependencies([uv_lock_path, npm_lock_path])

        assert len(results) == 2
        assert results[0].ecosystem == "python"
        assert results[1].ecosystem == "javascript"


def test_get_all_dependencies_with_nonexistent():
    """Test extracting dependencies with non-existent files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        uv_lock_path = Path(tmpdir) / "uv.lock"
        uv_lock_path.write_text("[[package]]\nname = 'test'\nversion = '1.0.0'\n")

        (Path(tmpdir) / "pyproject.toml").write_text(
            '[project]\nname = "test-project"\n'
        )

        nonexistent_path = Path(tmpdir) / "nonexistent.lock"

        results = get_all_dependencies([uv_lock_path, nonexistent_path])

        assert len(results) == 1
        assert results[0].ecosystem == "python"


def test_javascript_lockfile_nonexistent():
    """Test parsing a non-existent JavaScript lockfile returns None."""
    result = parse_javascript_lockfile("/nonexistent/package-lock.json")
    assert result is None


def test_javascript_lockfile_unsupported():
    """Test parsing an unsupported JavaScript lockfile returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "unsupported.lock"
        lockfile_path.write_text("# unsupported format")

        result = parse_javascript_lockfile(lockfile_path)

        assert result is None


def test_javascript_lockfile_corrupted():
    """Test parsing a corrupted JavaScript lockfile returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "package-lock.json"
        lockfile_path.write_text("invalid json {[[")

        result = parse_javascript_lockfile(lockfile_path)

        assert result is None


def test_poetry_without_pyproject():
    """Test parsing Poetry lock without pyproject.toml."""
    poetry_lock_content = """
[[package]]
name = "requests"
version = "2.28.0"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "poetry.lock"
        lockfile_path.write_text(poetry_lock_content)

        result = parse_python_lockfile(lockfile_path)

        assert result is not None
        assert result.root_package == "unknown"
        assert len(result.transitive_dependencies) == 1


def test_javascript_without_package_json():
    """Test parsing JavaScript lock without package.json."""
    npm_lock_content = {
        "lockfileVersion": 3,
        "packages": {
            "": {},
            "node_modules/lodash": {"version": "4.17.21"},
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "package-lock.json"
        lockfile_path.write_text(json.dumps(npm_lock_content))

        result = parse_javascript_lockfile(lockfile_path)

        assert result is not None
        assert result.root_package == "unknown"


def test_uv_lock_with_poetry_name():
    """Test uv.lock with pyproject.toml using Poetry format."""
    uv_lock_content = """
[[package]]
name = "click"
version = "8.1.0"
"""

    pyproject_content = """
[tool.poetry]
name = "poetry-style-project"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "uv.lock"
        lockfile_path.write_text(uv_lock_content)

        pyproject_path = Path(tmpdir) / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)

        result = parse_python_lockfile(lockfile_path)

        assert result is not None
        assert result.root_package == "poetry-style-project"


def test_poetry_with_optional_dependencies():
    """Test parsing Poetry lock with optional dependencies."""
    poetry_lock_content = """
[[package]]
name = "click"
version = "8.1.0"

[[package]]
name = "pytest"
version = "7.2.0"
"""

    pyproject_content = """
[tool.poetry]
name = "test-project"

[tool.poetry.dependencies]
python = "^3.10"
click = "^8.1.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.2.0"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "poetry.lock"
        lockfile_path.write_text(poetry_lock_content)

        pyproject_path = Path(tmpdir) / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)

        result = parse_python_lockfile(lockfile_path)

        assert result is not None
        assert result.root_package == "test-project"
        # Both should be treated as direct dependencies
        assert len(result.direct_dependencies) == 2


def test_corrupted_pyproject_toml():
    """Test handling corrupted pyproject.toml gracefully."""
    uv_lock_content = """
[[package]]
name = "click"
version = "8.1.0"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "uv.lock"
        lockfile_path.write_text(uv_lock_content)

        pyproject_path = Path(tmpdir) / "pyproject.toml"
        pyproject_path.write_text("invalid toml {{[[")

        result = parse_python_lockfile(lockfile_path)

        assert result is not None
        assert result.root_package == "unknown"


def test_corrupted_package_json():
    """Test handling corrupted package.json gracefully."""
    npm_lock_content = {
        "lockfileVersion": 3,
        "packages": {
            "": {},
            "node_modules/lodash": {"version": "4.17.21"},
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "package-lock.json"
        lockfile_path.write_text(json.dumps(npm_lock_content))

        package_json_path = Path(tmpdir) / "package.json"
        package_json_path.write_text("invalid json {[[")

        result = parse_javascript_lockfile(lockfile_path)

        assert result is not None
        assert result.root_package == "unknown"


def test_filter_high_value_empty_dependencies():
    """Test filtering with empty dependencies."""
    graph = DependencyGraph(
        root_package="test",
        ecosystem="python",
        direct_dependencies=[],
        transitive_dependencies=[],
    )

    filtered = filter_high_value_dependencies(graph, max_count=5)

    assert len(filtered) == 0


def test_poetry_lock_with_empty_package_name():
    """Test parsing Poetry lock with packages that have empty names."""
    poetry_lock_content = """
[[package]]
name = ""
version = "1.0.0"

[[package]]
name = "click"
version = "8.1.0"
"""

    pyproject_content = """
[tool.poetry]
name = "test-project"

[tool.poetry.dependencies]
python = "^3.10"
click = "^8.1.0"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "poetry.lock"
        lockfile_path.write_text(poetry_lock_content)

        pyproject_path = Path(tmpdir) / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)

        result = parse_python_lockfile(lockfile_path)

        assert result is not None
        # Empty name should be skipped
        assert len(result.direct_dependencies) == 1
        assert result.direct_dependencies[0].name == "click"


def test_poetry_dependencies_with_invalid_group():
    """Test parsing Poetry dependencies with invalid group structure."""
    poetry_lock_content = """
[[package]]
name = "click"
version = "8.1.0"
"""

    pyproject_content = """
[tool.poetry]
name = "test-project"

[tool.poetry.dependencies]
python = "^3.10"
click = "^8.1.0"

[tool.poetry.group.dev]
invalid = "not a dict"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "poetry.lock"
        lockfile_path.write_text(poetry_lock_content)

        pyproject_path = Path(tmpdir) / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)

        result = parse_python_lockfile(lockfile_path)

        assert result is not None
        assert len(result.direct_dependencies) == 1


def test_corrupted_pyproject_for_poetry_dependencies():
    """Test handling corrupted pyproject.toml when extracting Poetry dependencies."""
    from oss_sustain_guard.dependency_graph import _get_poetry_direct_dependencies

    with tempfile.TemporaryDirectory() as tmpdir:
        pyproject_path = Path(tmpdir) / "pyproject.toml"
        # Create a file that will cause an exception when parsing
        pyproject_path.write_text("invalid toml content {{[[")

        result = _get_poetry_direct_dependencies(Path(tmpdir))

        assert result == set()
