"""Tests for Bun and Deno lockfile parsers."""

import json
import tempfile
from pathlib import Path

from oss_sustain_guard.dependency_graph import (
    get_all_dependencies,
)
from oss_sustain_guard.dependency_parsers.javascript.bun import parse_bun_lockfile
from oss_sustain_guard.dependency_parsers.javascript.deno import (
    _extract_deno_package_info,
    parse_deno_lockfile,
)


def test_parse_bun_lock():
    """Test parsing a minimal bun.lock file."""
    bun_lock_content = {
        "lockfileVersion": 0,
        "packages": {
            "react": {
                "name": "react",
                "version": "18.2.0",
                "resolved": "https://registry.npmjs.org/react/-/react-18.2.0.tgz",
            },
            "react-dom": {
                "name": "react-dom",
                "version": "18.2.0",
                "resolved": "https://registry.npmjs.org/react-dom/-/react-dom-18.2.0.tgz",
            },
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "bun.lock"
        lockfile_path.write_text(json.dumps(bun_lock_content))

        # Create package.json with direct dependencies
        package_json = {"name": "test-app", "dependencies": {"react": "^18.2.0"}}
        (Path(tmpdir) / "package.json").write_text(json.dumps(package_json))

        result = parse_bun_lockfile(lockfile_path)

        assert result is not None
        assert result.ecosystem == "javascript"
        assert result.root_package == "test-app"
        # React is direct, react-dom is transitive
        assert any(
            d.name == "react" and d.is_direct for d in result.direct_dependencies
        )


def test_parse_deno_lock():
    """Test parsing a minimal deno.lock file."""
    deno_lock_content = {
        "version": "3",
        "remote": {
            "https://deno.land/std@0.208.0/fs/mod.ts": {"integrity": "sha256-abc123"},
            "npm:react@18.2.0": {"integrity": "sha256-def456"},
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "deno.lock"
        lockfile_path.write_text(json.dumps(deno_lock_content))

        # Create deno.json with imports
        deno_json = {
            "name": "test-app",
            "imports": {"std/": "https://deno.land/std@0.208.0/"},
        }
        (Path(tmpdir) / "deno.json").write_text(json.dumps(deno_json))

        result = parse_deno_lockfile(lockfile_path)

        assert result is not None
        assert result.ecosystem == "javascript"
        assert result.root_package == "test-app"


def test_extract_deno_package_info():
    """Test extracting package info from various Deno URL formats."""
    test_cases = [
        ("npm:react@18.2.0", ("react", "18.2.0")),
        ("npm:@scope/package@1.0.0", ("@scope/package", "1.0.0")),
        ("https://deno.land/std@0.208.0/fs/mod.ts", ("std", "0.208.0")),
        ("https://deno.land/x/fresh@1.4.0/dev.ts", ("fresh", "1.4.0")),
    ]

    for url, expected in test_cases:
        result = _extract_deno_package_info(url)
        assert result == expected, (
            f"Failed for {url}: got {result}, expected {expected}"
        )


def test_get_all_dependencies_with_bun_lock():
    """Test auto-detection and parsing of bun.lock."""
    bun_lock_content = {
        "lockfileVersion": 0,
        "packages": {
            "typescript": {"name": "typescript", "version": "5.3.0"},
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "bun.lock"
        lockfile_path.write_text(json.dumps(bun_lock_content))

        package_json = {
            "name": "my-app",
            "devDependencies": {"typescript": "^5.3.0"},
        }
        (Path(tmpdir) / "package.json").write_text(json.dumps(package_json))

        results = get_all_dependencies([lockfile_path])

        assert len(results) == 1
        assert results[0].ecosystem == "javascript"
        assert results[0].root_package == "my-app"


def test_get_all_dependencies_with_deno_lock():
    """Test auto-detection and parsing of deno.lock."""
    deno_lock_content = {
        "version": "3",
        "remote": {
            "npm:typescript@5.3.0": {"integrity": "sha256-xyz"},
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "deno.lock"
        lockfile_path.write_text(json.dumps(deno_lock_content))

        deno_json = {
            "name": "my-deno-app",
            "dependencies": {"typescript": "npm:typescript@5.3.0"},
        }
        (Path(tmpdir) / "deno.json").write_text(json.dumps(deno_json))

        results = get_all_dependencies([lockfile_path])

        assert len(results) == 1
        assert results[0].ecosystem == "javascript"
        assert results[0].root_package == "my-deno-app"


def test_parse_nonexistent_bun_lock():
    """Test parsing non-existent bun.lock returns None."""
    result = parse_bun_lockfile("/nonexistent/path/bun.lock")
    assert result is None


def test_parse_nonexistent_deno_lock():
    """Test parsing non-existent deno.lock returns None."""
    result = parse_deno_lockfile("/nonexistent/path/deno.lock")
    assert result is None


def test_parse_invalid_bun_lock():
    """Test parsing invalid JSON in bun.lock returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "bun.lock"
        lockfile_path.write_text("invalid json {{{")

        result = parse_bun_lockfile(lockfile_path)
        assert result is None


def test_parse_invalid_deno_lock():
    """Test parsing invalid JSON in deno.lock returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lockfile_path = Path(tmpdir) / "deno.lock"
        lockfile_path.write_text("invalid json {{{")

        result = parse_deno_lockfile(lockfile_path)
        assert result is None
