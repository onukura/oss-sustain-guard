"""
Test integration functionality for dependency graph analysis.
Includes get_all_dependencies, get_package_dependencies for multiple formats.
"""

import json
import tempfile
from pathlib import Path

from oss_sustain_guard.dependency_graph import (
    get_all_dependencies,
    get_package_dependencies,
)


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
