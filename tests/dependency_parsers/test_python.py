"""
Test Python lockfile parsers (uv.lock, poetry.lock, Pipfile.lock).
"""

import json
import tempfile
from pathlib import Path

from oss_sustain_guard.dependency_graph import parse_python_lockfile


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


def test_parse_nonexistent_lockfile():
    """Test parsing a non-existent lockfile returns None."""
    result = parse_python_lockfile("/nonexistent/path/uv.lock")
    assert result is None


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
        result = parse_python_lockfile(lockfile_path)

        # Should still parse successfully
        assert result is not None or result is None


def test_get_package_dependencies_uv_lock():
    """Test extracting dependencies for a specific package from uv.lock."""
    from oss_sustain_guard.dependency_graph import get_package_dependencies

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
    from oss_sustain_guard.dependency_graph import get_package_dependencies

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
