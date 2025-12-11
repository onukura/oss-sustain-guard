"""
Tests for --root-dir and --manifest options in CLI.
"""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from oss_sustain_guard.cli import app

runner = CliRunner()


class TestRootDirOption:
    """Test --root-dir option functionality."""

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
    """Test --manifest option functionality."""

    def test_manifest_with_package_json(self):
        """Test reading from a specific package.json file."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        manifest_path = fixtures_dir / "package.json"

        if not manifest_path.exists():
            return  # Skip if fixture doesn't exist

        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "--manifest", str(manifest_path), "--insecure"],
            )

            assert "Reading manifest file" in result.output
            assert "Detected ecosystem: javascript" in result.output
            assert "package.json" in result.output

    def test_manifest_with_requirements_txt(self):
        """Test reading from a specific requirements.txt file."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        manifest_path = fixtures_dir / "requirements.txt"

        if not manifest_path.exists():
            return

        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "--manifest", str(manifest_path), "--insecure"],
            )

            assert "Reading manifest file" in result.output
            assert "Detected ecosystem: python" in result.output

    def test_manifest_with_pyproject_toml(self):
        """Test reading from a specific pyproject.toml file."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        manifest_path = fixtures_dir / "pyproject.toml"

        if not manifest_path.exists():
            return

        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "--manifest", str(manifest_path), "--insecure"],
            )

            assert "Reading manifest file" in result.output
            assert "Detected ecosystem: python" in result.output
            assert "pyproject.toml" in result.output

    def test_manifest_with_cargo_toml(self):
        """Test reading from a specific Cargo.toml file."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        manifest_path = fixtures_dir / "Cargo.toml"

        if not manifest_path.exists():
            return

        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "--manifest", str(manifest_path), "--insecure"],
            )

            assert "Reading manifest file" in result.output
            assert "Detected ecosystem: rust" in result.output

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
        # Create a temporary file with unknown extension
        import tempfile

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

    def test_manifest_short_option(self):
        """Test -m short option for --manifest."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        manifest_path = fixtures_dir / "package.json"

        if not manifest_path.exists():
            return

        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "-m", str(manifest_path), "--insecure"],
            )

            assert "Reading manifest file" in result.output
            assert "Detected ecosystem: javascript" in result.output

    def test_manifest_with_pipfile(self):
        """Test --manifest with Pipfile."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        manifest_path = fixtures_dir / "Pipfile"

        if not manifest_path.exists():
            return

        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "-m", str(manifest_path), "--insecure"],
            )

            assert "Reading manifest file" in result.output
            assert "Detected ecosystem: python" in result.output

    def test_manifest_with_absolute_path(self):
        """Test --manifest with absolute path from different directory."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        manifest_path = (fixtures_dir / "package.json").resolve()

        if not manifest_path.exists():
            return

        with patch("oss_sustain_guard.cli.analyze_package") as mock_analyze:
            mock_analyze.return_value = None

            result = runner.invoke(
                app,
                ["check", "--manifest", str(manifest_path), "--insecure"],
            )

            assert "Reading manifest file" in result.output
            assert result.exit_code == 0 or "No results" in result.output
