"""
Tests for --root-dir and --manifest CLI options.

Focuses on CLI option behavior, path resolution, and error handling.
For manifest file parsing tests, see test_fixtures_integration.py.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from oss_sustain_guard.cli import app

runner = CliRunner()


class TestRootDirOption:
    """Test --root-dir option functionality."""

    @pytest.mark.slow
    def test_root_dir_with_fixtures(self):
        """Test auto-detection with --root-dir pointing to fixtures."""
        fixtures_dir = Path(__file__).parent / "fixtures"

        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            # Mock analyze_package to return None (simulating cache miss)
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "--root-dir", str(fixtures_dir), "--insecure"],
            )

            # Should detect manifest files and attempt to analyze
            assert "Auto-detecting from manifest files" in result.output
            assert (
                fixtures_dir.name in result.output or str(fixtures_dir) in result.output
            )

    def test_root_dir_nonexistent(self):
        """Test error handling for non-existent directory."""
        result = runner.invoke(
            app,
            ["check", "--root-dir", "/nonexistent/directory"],
        )

        assert result.exit_code == 1
        assert "Directory not found:" in result.output
        assert "nonexistent" in result.output and "directory" in result.output

    @pytest.mark.slow
    def test_root_dir_file_instead_of_directory(self):
        """Test error handling when root-dir is a file."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        file_path = fixtures_dir / "package.json"

        if file_path.exists():
            result = runner.invoke(
                app,
                ["check", "--root-dir", str(file_path)],
            )

            assert result.exit_code == 1
            assert "Path is not a directory" in result.output

    @pytest.mark.slow
    def test_root_dir_default_current_directory(self):
        """Test that default root-dir is current directory."""
        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "--insecure"],
            )

            # Should auto-detect from current directory (may find nothing)
            assert result.exit_code in (0, 1)  # 0 if files found, 1 if error

    @pytest.mark.slow
    def test_root_dir_with_relative_path(self):
        """Test --root-dir with relative path."""
        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "--root-dir", "tests/fixtures", "--insecure"],
            )

            # Should resolve relative path and detect files
            assert "Auto-detecting from manifest files" in result.output

    @pytest.mark.slow
    def test_root_dir_short_option(self):
        """Test -r short option for --root-dir."""
        fixtures_dir = Path(__file__).parent / "fixtures"

        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "-r", str(fixtures_dir), "--insecure"],
            )

            # Should work the same as --root-dir
            assert "Auto-detecting from manifest files" in result.output


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

    @pytest.mark.slow
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

    @pytest.mark.slow
    def test_manifest_short_option(self):
        """Test -m short option for --manifest."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        # Use any existing manifest file
        manifest_path = None
        for candidate in ["package.json", "requirements.txt", "Cargo.toml"]:
            path = fixtures_dir / candidate
            if path.exists():
                manifest_path = path
                break

        if not manifest_path:
            pytest.skip("No manifest fixtures available")

        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "-m", str(manifest_path), "--insecure"],
            )

            # Should work the same as --manifest
            assert "Reading manifest file" in result.output

    @pytest.mark.slow
    def test_manifest_with_absolute_path(self):
        """Test --manifest with absolute path."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        # Use any existing manifest file
        manifest_path = None
        for candidate in ["package.json", "requirements.txt", "Cargo.toml"]:
            path = fixtures_dir / candidate
            if path.exists():
                manifest_path = path.resolve()
                break

        if not manifest_path:
            pytest.skip("No manifest fixtures available")

        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "--manifest", str(manifest_path), "--insecure"],
            )

            # Should resolve absolute path correctly
            assert "Reading manifest file" in result.output
            assert result.exit_code == 0 or "No results" in result.output
