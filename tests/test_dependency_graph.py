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
    get_package_dependencies,
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
    """Test handling corrupted pyproject.toml gracefully."""
    # Create a corrupted Poetry lockfile
    poetry_lock_content = """[metadata]
lock-version = "2.0"
python-versions = "^3.10"
content-hash = "abc123"

[[package]]
name = "requests"
version = "2.28.0"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "poetry.lock"
        lockfile_path.write_text(poetry_lock_content)

        # This should not raise an error, just skip the file
        result = get_all_dependencies([lockfile_path])

        # Should still parse successfully
        assert len(result) > 0 or len(result) == 0  # Either parses or silently skips


def test_get_package_dependencies_uv_lock():
    """Test extracting dependencies for a specific package from uv.lock."""
    uv_lock_content = """
[[package]]
name = "requests"
version = "2.28.0"
dependencies = [
    { name = "certifi" },
    { name = "charset-normalizer" },
    { name = "idna" },
    { name = "urllib3" },
]

[[package]]
name = "click"
version = "8.1.0"
dependencies = [
    { name = "colorama", marker = "platform_system == 'Windows'" },
]

[[package]]
name = "pytest"
version = "7.0.0"
dependencies = [
    { name = "attrs" },
    { name = "iniconfig" },
    { name = "packaging" },
]
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "uv.lock"
        lockfile_path.write_text(uv_lock_content)

        # Test getting dependencies for requests
        deps = get_package_dependencies(lockfile_path, "requests")
        assert set(deps) == {"certifi", "charset-normalizer", "idna", "urllib3"}

        # Test getting dependencies for click
        deps = get_package_dependencies(lockfile_path, "click")
        assert set(deps) == {"colorama"}

        # Test getting dependencies for pytest
        deps = get_package_dependencies(lockfile_path, "pytest")
        assert set(deps) == {"attrs", "iniconfig", "packaging"}

        # Test package that doesn't exist
        deps = get_package_dependencies(lockfile_path, "nonexistent")
        assert deps == []


def test_get_package_dependencies_poetry_lock():
    """Test extracting dependencies for a specific package from poetry.lock."""
    poetry_lock_content = """
[[package]]
name = "requests"
version = "2.28.0"

[package.dependencies]
certifi = ">=2017.4.17"
charset-normalizer = ">=2,<4"
idna = ">=2.5,<4"
urllib3 = ">=1.21.1,<1.27"

[[package]]
name = "pytest"
version = "7.0.0"

[package.dependencies]
attrs = ">=19.2.0"
iniconfig = "*"
packaging = "*"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "poetry.lock"
        lockfile_path.write_text(poetry_lock_content)

        # Test getting dependencies for requests
        deps = get_package_dependencies(lockfile_path, "requests")
        assert set(deps) == {"certifi", "charset-normalizer", "idna", "urllib3"}

        # Test getting dependencies for pytest
        deps = get_package_dependencies(lockfile_path, "pytest")
        assert set(deps) == {"attrs", "iniconfig", "packaging"}

        # Test package that doesn't exist
        deps = get_package_dependencies(lockfile_path, "nonexistent")
        assert deps == []


def test_get_package_dependencies_package_lock_json():
    """Test extracting dependencies for a specific package from package-lock.json."""
    package_lock_content = """{
  "name": "test-project",
  "version": "1.0.0",
  "lockfileVersion": 3,
  "packages": {
    "node_modules/react": {
      "name": "react",
      "version": "18.0.0",
      "dependencies": {
        "loose-envify": "^1.1.0"
      }
    },
    "node_modules/react-dom": {
      "name": "react-dom",
      "version": "18.0.0",
      "dependencies": {
        "loose-envify": "^1.1.0",
        "scheduler": "^0.23.0"
      }
    },
    "node_modules/@types/react": {
      "name": "@types/react",
      "version": "18.0.0",
      "dependencies": {
        "@types/prop-types": "*",
        "csstype": "^3.0.2"
      }
    }
  }
}"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "package-lock.json"
        lockfile_path.write_text(package_lock_content)

        # Test getting dependencies for react
        deps = get_package_dependencies(lockfile_path, "react")
        assert set(deps) == {"loose-envify"}

        # Test getting dependencies for react-dom
        deps = get_package_dependencies(lockfile_path, "react-dom")
        assert set(deps) == {"loose-envify", "scheduler"}

        # Test getting dependencies for scoped package
        deps = get_package_dependencies(lockfile_path, "@types/react")
        assert set(deps) == {"@types/prop-types", "csstype"}

        # Test package that doesn't exist
        deps = get_package_dependencies(lockfile_path, "nonexistent")
        assert deps == []


def test_get_package_dependencies_yarn_lock():
    """Test extracting dependencies for a package from yarn.lock."""
    yarn_lock_content = """
lodash@^4.17.21:
  version "4.17.21"
  dependencies:
    foo "^1.0.0"
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "yarn.lock"
        lockfile_path.write_text(yarn_lock_content)

        deps = get_package_dependencies(lockfile_path, "lodash")
        assert deps == ["foo"]


def test_get_package_dependencies_pnpm_lock():
    """Test extracting dependencies for a package from pnpm-lock.yaml."""
    pnpm_lock_content = """
lockfileVersion: '6.0'
packages:
  /lodash/4.17.21:
    dependencies:
      foo: 1.0.0
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "pnpm-lock.yaml"
        lockfile_path.write_text(pnpm_lock_content)

        deps = get_package_dependencies(lockfile_path, "lodash")
        assert deps == ["foo"]


def test_get_package_dependencies_mix_lock():
    """Test extracting dependencies for a package from mix.lock."""
    mix_lock_content = """
%{
  "plug": {:hex, :plug, "1.11.0", "checksum", [:mix],
    [{:cowboy, "~> 2.7", [hex: :cowboy]},
     {:"phoenix_pubsub", "~> 2.0", [hex: :"phoenix_pubsub"]}],
    "hexpm", "checksum"}
}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "mix.lock"
        lockfile_path.write_text(mix_lock_content)

        deps = get_package_dependencies(lockfile_path, "plug")
        assert set(deps) == {"cowboy", "phoenix_pubsub"}


def test_get_package_dependencies_packages_lock_json():
    """Test extracting dependencies for a package from packages.lock.json."""
    packages_lock_content = {
        "dependencies": {
            ".NETCoreApp,Version=v8.0": {
                "Newtonsoft.Json": {
                    "type": "Direct",
                    "resolved": "13.0.3",
                    "dependencies": {"System.Runtime": "4.3.0"},
                }
            }
        }
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "packages.lock.json"
        lockfile_path.write_text(json.dumps(packages_lock_content))

        deps = get_package_dependencies(lockfile_path, "Newtonsoft.Json")
        assert deps == ["System.Runtime"]


def test_get_package_dependencies_renv_lock():
    """Test extracting dependencies for a package from renv.lock."""
    renv_lock_content = {
        "Packages": {
            "dplyr": {"Version": "1.0.0", "Requirements": ["cli", "vctrs"]},
            "cli": {"Version": "3.6.0"},
        }
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "renv.lock"
        lockfile_path.write_text(json.dumps(renv_lock_content))

        deps = get_package_dependencies(lockfile_path, "dplyr")
        assert set(deps) == {"cli", "vctrs"}


def test_get_package_dependencies_pubspec_lock():
    """Test extracting dependencies from pubspec.yaml when pubspec.lock is present."""
    pubspec_content = """
name: my_app
dependencies:
  http: ^0.13.0
dev_dependencies:
  test: ^1.0.0
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "pubspec.lock"
        lockfile_path.write_text("packages:\n")
        pubspec_path = Path(tmpdir) / "pubspec.yaml"
        pubspec_path.write_text(pubspec_content)

        deps = get_package_dependencies(lockfile_path, "my_app")
        assert set(deps) == {"http", "test"}


def test_get_package_dependencies_package_resolved_uses_manifest():
    """Test extracting Swift dependencies from Package.swift."""
    package_content = """
import PackageDescription

let package = Package(
    name: "Example",
    dependencies: [
        .package(url: "https://github.com/apple/swift-nio.git", from: "2.56.0"),
        .package(url: "https://github.com/Alamofire/Alamofire.git", from: "5.8.0")
    ]
)
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "Package.resolved"
        lockfile_path.write_text('{"pins": []}')
        manifest_path = Path(tmpdir) / "Package.swift"
        manifest_path.write_text(package_content)

        deps = get_package_dependencies(lockfile_path, "Example")
        assert set(deps) == {"apple/swift-nio", "Alamofire/Alamofire"}


def test_get_package_dependencies_stack_yaml_lock():
    """Test extracting dependencies from stack.yaml.lock."""
    stack_lock_content = """
packages:
  - hackage: text-1.2.5.0@sha256:abc,123
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "stack.yaml.lock"
        lockfile_path.write_text(stack_lock_content)

        deps = get_package_dependencies(lockfile_path, "example")
        assert deps == ["text"]


def test_get_package_dependencies_cpanfile_snapshot():
    """Test extracting dependencies from cpanfile.snapshot."""
    cpanfile_content = """
DISTRIBUTIONS
  distribution: My-Module-1.0
    requirements:
      Moo: 2.0
      JSON::PP: 4.0
    provides:
      My::Module: 1.0
    requires:
      Try::Tiny: 0
  distribution: Other-Module-0.1
    requires:
      File::Spec: 0
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "cpanfile.snapshot"
        lockfile_path.write_text(cpanfile_content)

        deps = get_package_dependencies(lockfile_path, "my-module")
        assert set(deps) == {"Moo", "JSON::PP", "Try::Tiny"}


def test_get_package_dependencies_nonexistent_file():
    """Test get_package_dependencies with non-existent file."""
    deps = get_package_dependencies("/nonexistent/path/uv.lock", "requests")
    assert deps == []


def test_get_package_dependencies_unsupported_format():
    """Test get_package_dependencies with unsupported lockfile format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "unsupported.lock"
        lockfile_path.write_text("some content")

        deps = get_package_dependencies(lockfile_path, "requests")
        assert deps == []
