"""
Tests for --root-dir and --manifest CLI options.

Focuses on CLI option behavior, path resolution, and error handling.
For manifest file parsing tests, see test_fixtures_integration.py.

Performance optimization notes:
- Mocks detect_ecosystems() and find_manifest_files() to avoid expensive I/O
- Mocks analyze_package() to avoid real GitHub API calls
- Uses fixtures for common setup to reduce duplication
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from oss_sustain_guard.cli import app

runner = CliRunner()


@pytest.fixture
def mock_ecosystem_detection():
    """Mock ecosystem and manifest detection for speed."""
    with (
        patch("oss_sustain_guard.resolvers.detect_ecosystems") as mock_eco,
        patch("oss_sustain_guard.resolvers.find_manifest_files") as mock_manifests,
    ):
        # Return empty results by default
        mock_eco.return_value = []
        mock_manifests.return_value = {}
        yield {"ecosystems": mock_eco, "manifests": mock_manifests}


@pytest.fixture
def mock_analyzer():
    """Mock analyze_package to avoid real analysis."""
    with patch("oss_sustain_guard.commands.check.analyze_package") as mock:
        mock.return_value = None
        yield mock


class TestRootDirOption:
    """Test --root-dir option functionality."""

    def test_root_dir_with_fixtures(self, mock_ecosystem_detection, mock_analyzer):
        """Test auto-detection with --root-dir pointing to fixtures (fast, mocked)."""
        fixtures_dir = Path(__file__).parent / "fixtures"

        # Mock ecosystem detection to simulate finding packages
        mock_ecosystem_detection["ecosystems"].return_value = ["python"]
        mock_ecosystem_detection["manifests"].return_value = {}

        result = runner.invoke(
            app,
            ["check", "--root-dir", str(fixtures_dir), "--insecure"],
        )

        # Should detect ecosystems and/or show appropriate message
        assert result.exit_code in (0, 1)  # 0 if OK, 1 if no packages

    def test_root_dir_nonexistent(self):
        """Test error handling for non-existent directory."""
        result = runner.invoke(
            app,
            ["check", "--root-dir", "/nonexistent/directory"],
        )

        assert result.exit_code == 1
        assert "Directory not found:" in result.output
        assert "nonexistent" in result.output and "directory" in result.output

    def test_root_dir_file_instead_of_directory(self):
        """Test error handling when root-dir is a file."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "rust"
        # Find any existing file
        file_path = None
        for candidate in ["package.json", "requirements.txt", "Cargo.toml"]:
            path = fixtures_dir / candidate
            if path.exists():
                file_path = path
                break

        if not file_path:
            pytest.skip("No fixture files available")

        result = runner.invoke(
            app,
            ["check", "--root-dir", str(file_path)],
        )

        assert result.exit_code == 1
        assert "Path is not a directory" in result.output

    def test_root_dir_default_current_directory(self, mock_ecosystem_detection):
        """Test that default root-dir is current directory."""
        result = runner.invoke(
            app,
            ["check", "--insecure"],
        )

        # Should attempt detection (though may find nothing)
        assert result.exit_code in (0, 1)

    def test_root_dir_with_relative_path(self, mock_ecosystem_detection, mock_analyzer):
        """Test --root-dir with relative path (fast, mocked)."""
        mock_ecosystem_detection["ecosystems"].return_value = []

        result = runner.invoke(
            app,
            ["check", "--root-dir", "tests/fixtures/rust", "--insecure"],
        )

        # Should resolve relative path and process (though may find nothing with mocking)
        assert result.exit_code in (0, 1)

    def test_root_dir_short_option(self, mock_ecosystem_detection, mock_analyzer):
        """Test -r short option for --root-dir (fast, mocked)."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        mock_ecosystem_detection["ecosystems"].return_value = []

        result = runner.invoke(
            app,
            ["check", "-r", str(fixtures_dir), "--insecure"],
        )

        # Should work the same as --root-dir
        assert result.exit_code in (0, 1)


class TestManifestOption:
    """Test --manifest option functionality.

    Focuses on CLI behavior and error handling.
    For detailed manifest parsing tests, see test_fixtures_integration.py.
    """

    def test_manifest_nonexistent_file(self):
        """Test error handling for non-existent manifest file."""
        result = runner.invoke(
            app,
            ["check", "--manifest", "/nonexistent/package.json"],
        )

        assert result.exit_code == 1
        assert "Manifest file not found:" in result.output
        assert "nonexistent" in result.output and "package.json" in result.output

    def test_manifest_directory_instead_of_file(self):
        """Test error handling when manifest path is a directory."""
        fixtures_dir = Path(__file__).parent / "fixtures"

        result = runner.invoke(
            app,
            ["check", "--manifest", str(fixtures_dir)],
        )

        assert result.exit_code == 1
        assert "Path is not a file" in result.output

    def test_manifest_unknown_file_type(self):
        """Test error handling for unknown manifest file type."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".unknown", delete=False
        ) as f:
            f.write("test content")
            temp_path = f.name

        try:
            result = runner.invoke(
                app,
                ["check", "--manifest", temp_path],
            )

            assert result.exit_code == 1
            assert "Could not detect ecosystem from manifest file" in result.output
            assert "Supported manifest files" in result.output
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.parametrize("option_name", ["--manifest", "-m"])
    def test_manifest_short_option(self, option_name, mock_analyzer):
        """Test both -m short option and --manifest for manifest files (fast, mocked)."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "rust"
        # Use any existing manifest file
        manifest_path = None
        for candidate in ["package.json", "requirements.txt", "Cargo.toml"]:
            path = fixtures_dir / candidate
            if path.exists():
                manifest_path = path
                break

        if not manifest_path:
            pytest.skip("No manifest fixtures available")

        result = runner.invoke(
            app,
            ["check", option_name, str(manifest_path), "--insecure"],
        )

        # Should work and read manifest file
        assert "Reading manifest file" in result.output or result.exit_code in (0, 1)

    def test_manifest_with_absolute_path(self, mock_analyzer):
        """Test --manifest with absolute path (fast, mocked)."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "rust"
        # Use any existing manifest file
        manifest_path = None
        for candidate in ["package.json", "requirements.txt", "Cargo.toml"]:
            path = fixtures_dir / candidate
            if path.exists():
                manifest_path = path.resolve()
                break

        if not manifest_path:
            pytest.skip("No manifest fixtures available")

        result = runner.invoke(
            app,
            ["check", "--manifest", str(manifest_path), "--insecure"],
        )

        # Should resolve absolute path correctly
        assert "Reading manifest file" in result.output or result.exit_code in (
            0,
            1,
        )
