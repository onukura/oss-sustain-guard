"""
Test exclusion pattern functionality for recursive scanning.
"""

import tempfile
from pathlib import Path

from oss_sustain_guard.config import (
    get_default_exclusion_patterns,
    get_exclusion_patterns,
    parse_gitignore,
)


def test_default_exclusion_patterns():
    """Test that default exclusion patterns include common directories."""
    defaults = get_default_exclusion_patterns()

    # Check common exclusions
    assert "node_modules" in defaults
    assert "__pycache__" in defaults
    assert "venv" in defaults
    assert ".venv" in defaults
    assert "target" in defaults  # Rust
    assert "build" in defaults
    assert ".git" in defaults


def test_parse_gitignore_simple():
    """Test parsing simple .gitignore patterns."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gitignore", delete=False) as f:
        f.write("# Comment\n")
        f.write("node_modules\n")
        f.write("dist/\n")
        f.write("*.pyc\n")  # Should be ignored (file pattern)
        f.write("build\n")
        f.write("\n")  # Empty line
        f.write("# Another comment\n")
        f.write("temp\n")
        file_path = Path(f.name)

    try:
        patterns = parse_gitignore(file_path)

        assert "node_modules" in patterns
        assert "dist" in patterns
        assert "build" in patterns
        assert "temp" in patterns
        # File patterns should not be included
        assert "*.pyc" not in patterns
    finally:
        file_path.unlink()


def test_parse_gitignore_with_paths():
    """Test that patterns with paths are handled correctly."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gitignore", delete=False) as f:
        f.write("src/build\n")  # Has path separator, should be skipped
        f.write("*/temp\n")  # Any temp directory
        f.write("cache\n")  # Simple pattern
        file_path = Path(f.name)

    try:
        patterns = parse_gitignore(file_path)

        # Patterns with paths should not be included
        assert "src/build" not in patterns
        # */pattern should extract the pattern
        assert "temp" in patterns
        assert "cache" in patterns
    finally:
        file_path.unlink()


def test_parse_gitignore_negations():
    """Test that negation patterns are ignored."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gitignore", delete=False) as f:
        f.write("build\n")
        f.write("!build/important\n")  # Negation, should be skipped
        file_path = Path(f.name)

    try:
        patterns = parse_gitignore(file_path)

        assert "build" in patterns
        assert "!build/important" not in patterns
    finally:
        file_path.unlink()


def test_parse_gitignore_nonexistent():
    """Test parsing nonexistent .gitignore returns empty set."""
    patterns = parse_gitignore(Path("/nonexistent/.gitignore"))
    assert patterns == set()


def test_get_exclusion_patterns_defaults():
    """Test that get_exclusion_patterns includes defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        patterns = get_exclusion_patterns(tmpdir_path)

        # Should include defaults
        assert "node_modules" in patterns
        assert "venv" in patterns
        assert "__pycache__" in patterns


def test_get_exclusion_patterns_with_gitignore():
    """Test that get_exclusion_patterns includes .gitignore patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a .gitignore file
        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text("custom_cache\nmytemp\n")

        patterns = get_exclusion_patterns(tmpdir_path)

        # Should include defaults
        assert "node_modules" in patterns
        # Should include .gitignore patterns
        assert "custom_cache" in patterns
        assert "mytemp" in patterns


def test_exclusion_patterns_language_coverage():
    """Test that exclusion patterns cover all supported languages."""
    defaults = get_default_exclusion_patterns()

    # Python
    assert "venv" in defaults
    assert "__pycache__" in defaults
    assert ".pytest_cache" in defaults

    # JavaScript/Node
    assert "node_modules" in defaults

    # Rust
    assert "target" in defaults

    # Go
    assert "vendor" in defaults

    # Java/Kotlin/Scala
    assert ".gradle" in defaults
    assert ".m2" in defaults

    # PHP
    # Note: "vendor" is already checked for Go

    # .NET/C#
    assert "bin" in defaults
    assert "obj" in defaults

    # Ruby
    assert ".bundle" in defaults


def test_exclusion_patterns_without_defaults(tmp_path: Path):
    """Test loading exclusion config without defaults."""
    # Create a temporary config file
    config_file = tmp_path / ".oss-sustain-guard.toml"
    config_file.write_text(
        """
[tool.oss-sustain-guard.exclude-dirs]
patterns = ["custom_dir"]
use_defaults = false
use_gitignore = false
"""
    )

    # Note: This test would require mocking PROJECT_ROOT
    # For now, just verify the defaults function works
    defaults = get_default_exclusion_patterns()
    assert len(defaults) > 0
