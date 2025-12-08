"""
Tests for the PyPI to GitHub URL resolver.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx

from oss_sustain_guard.resolver import (
    detect_lockfiles,
    get_github_url_from_pypi,
    get_packages_from_lockfile,
    parse_lockfile_pipenv,
    parse_lockfile_poetry,
    parse_lockfile_uv,
)

# --- Mock Data ---


def mock_pypi_response(project_urls: dict, status_code: int = 200):
    """Creates a mock httpx.Response for the PyPI API."""
    mock_request = httpx.Request(method="GET", url="https://pypi.org/pypi/test/json")
    if status_code != 200:
        return httpx.Response(status_code=status_code, request=mock_request)

    mock_json = {"info": {"project_urls": project_urls}}
    return httpx.Response(status_code=200, json=mock_json, request=mock_request)


# --- Tests ---


@patch("httpx.Client.get")
def test_get_github_url_from_source(mock_get):
    """Test that the GitHub URL is correctly extracted from the 'Source' field."""
    mock_get.return_value = mock_pypi_response(
        {"Source": "https://github.com/psf/requests"}
    )
    result = get_github_url_from_pypi("requests")
    assert result is not None
    owner, repo = result
    assert owner == "psf"
    assert repo == "requests"


@patch("httpx.Client.get")
def test_get_github_url_from_homepage(mock_get):
    """Test that the GitHub URL is correctly extracted from the 'Homepage' field."""
    mock_get.return_value = mock_pypi_response(
        {"Homepage": "https://github.com/django/django"}
    )
    result = get_github_url_from_pypi("django")
    assert result is not None
    owner, repo = result
    assert owner == "django"
    assert repo == "django"


@patch("httpx.Client.get")
def test_no_github_url(mock_get):
    """Test that None is returned when no GitHub URL is present."""
    mock_get.return_value = mock_pypi_response(
        {"Documentation": "https://www.google.com"}
    )
    result = get_github_url_from_pypi("no-github")
    assert result is None


@patch("httpx.Client.get")
def test_package_not_found(mock_get):
    """Test that None is returned for a 404 error."""
    mock_get.return_value = mock_pypi_response({}, status_code=404)
    result = get_github_url_from_pypi("non-existent-package")
    assert result is None


@patch("httpx.Client.get")
def test_malformed_github_url(mock_get):
    """Test that a malformed GitHub URL is handled gracefully."""
    mock_get.return_value = mock_pypi_response(
        {"Source": "https://github.com/just-an-owner"}
    )
    result = get_github_url_from_pypi("malformed")
    assert result is None


@patch("httpx.Client.get")
def test_github_url_with_fragment(mock_get):
    """Test that URL fragments are correctly stripped."""
    mock_get.return_value = mock_pypi_response(
        {"Repository": "https://github.com/pallets/flask#readme"}
    )
    result = get_github_url_from_pypi("flask")
    assert result is not None
    owner, repo = result
    assert owner == "pallets"
    assert repo == "flask"


@patch("httpx.Client.get")
def test_empty_project_urls(mock_get):
    """Test that an empty project_urls dictionary is handled correctly."""
    mock_get.return_value = mock_pypi_response({})
    result = get_github_url_from_pypi("empty-urls")
    assert result is None


# --- Lockfile Tests ---


def test_parse_lockfile_poetry():
    """Test parsing a poetry.lock file."""
    poetry_lock_content = b"""
[[package]]
name = "requests"
version = "2.31.0"

[[package]]
name = "django"
version = "4.2.0"
"""
    with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
        f.write(poetry_lock_content)
        f.flush()
        temp_path = f.name
    # Close file before deletion (Windows requirement)
    try:
        packages = parse_lockfile_poetry(temp_path)
        assert "requests" in packages
        assert "django" in packages
        assert len(packages) == 2
    finally:
        Path(temp_path).unlink()


def test_parse_lockfile_uv():
    """Test parsing a uv.lock file."""
    uv_lock_content = b"""
[[package]]
name = "fastapi"
version = "0.104.0"

[[package]]
name = "pydantic"
version = "2.0.0"
"""
    with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
        f.write(uv_lock_content)
        f.flush()
        temp_path = f.name
    # Close file before deletion (Windows requirement)
    try:
        packages = parse_lockfile_uv(temp_path)
        assert "fastapi" in packages
        assert "pydantic" in packages
        assert len(packages) == 2
    finally:
        Path(temp_path).unlink()


def test_parse_lockfile_pipenv():
    """Test parsing a Pipfile.lock file."""
    pipfile_lock_data = {
        "default": {
            "requests": {"version": "==2.31.0"},
            "flask": {"version": "==2.3.0"},
        },
        "develop": {"pytest": {"version": "==7.4.0"}},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".lock", delete=False) as f:
        json.dump(pipfile_lock_data, f)
        f.flush()
        temp_path = f.name
    # Close file before deletion (Windows requirement)
    try:
        packages = parse_lockfile_pipenv(temp_path)
        assert "requests" in packages
        assert "flask" in packages
        assert "pytest" in packages
        assert len(packages) == 3
    finally:
        Path(temp_path).unlink()


def test_get_packages_from_lockfile_poetry():
    """Test auto-detection and parsing of poetry.lock."""
    poetry_lock_content = b"""
[[package]]
name = "numpy"
version = "1.24.0"
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "poetry.lock"
        lockfile_path.write_bytes(poetry_lock_content)
        packages = get_packages_from_lockfile(lockfile_path)
        assert "numpy" in packages


def test_detect_lockfiles():
    """Test detection of multiple lockfiles in a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        # Create mock lockfiles
        (tmpdir_path / "poetry.lock").write_text("[[package]]\nname = 'test'")
        (tmpdir_path / "uv.lock").write_text("[[package]]\nname = 'test'")
        detected = detect_lockfiles(tmpdir_path)
        assert len(detected) == 2
        filenames = {f.name for f in detected}
        assert "poetry.lock" in filenames
        assert "uv.lock" in filenames


def test_detect_lockfiles_empty_directory():
    """Test detection in a directory with no lockfiles."""
    with tempfile.TemporaryDirectory() as tmpdir:
        detected = detect_lockfiles(tmpdir)
        assert len(detected) == 0


def test_parse_lockfile_poetry_empty():
    """Test parsing an empty poetry.lock file."""
    with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
        f.write(b"")
        f.flush()
        temp_path = f.name
    # Close file before deletion (Windows requirement)
    try:
        packages = parse_lockfile_poetry(temp_path)
        assert len(packages) == 0
    finally:
        Path(temp_path).unlink()


def test_parse_lockfile_pipenv_empty():
    """Test parsing an empty Pipfile.lock file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".lock", delete=False) as f:
        json.dump({}, f)
        f.flush()
        temp_path = f.name
    # Close file before deletion (Windows requirement)
    try:
        packages = parse_lockfile_pipenv(temp_path)
        assert len(packages) == 0
    finally:
        Path(temp_path).unlink()


@patch("httpx.Client.get")
def test_network_error(mock_get):
    """Test that network errors are handled."""
    mock_get.side_effect = httpx.RequestError("A network error occurred")
    result = get_github_url_from_pypi("network-error-package")
    assert result is None
