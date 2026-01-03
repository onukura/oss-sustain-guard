"""Tests for Scala dependency parser."""

import tempfile
from pathlib import Path


def test_scala_parser_registered():
    """Test that Scala parser is registered."""
    from oss_sustain_guard.dependency_parsers import load_dependency_parser_specs

    specs = load_dependency_parser_specs()
    scala_parser = next((s for s in specs if s.name == "scala"), None)
    assert scala_parser is not None
    assert "build.sbt.lock" in scala_parser.lockfile_names


def test_scala_lockfile_detection():
    """Test that Scala lockfiles are detected and parsed."""
    # This test verifies that the Scala parser is registered for the correct lockfile names
    from oss_sustain_guard.dependency_parsers import load_dependency_parser_specs

    specs = load_dependency_parser_specs()
    scala_parser = next((s for s in specs if s.name == "scala"), None)

    assert scala_parser is not None
    assert "build.sbt.lock" in scala_parser.lockfile_names
    assert "scala.lock" in scala_parser.lockfile_names


def test_scala_build_sbt_lock_supported():
    """Test that build.sbt.lock files are supported."""
    # Create a minimal build.sbt.lock file (note: actual format would be via resolver)
    with tempfile.TemporaryDirectory() as tmpdir:
        # Just verify the file would be detected
        lockfile_path = Path(tmpdir) / "build.sbt.lock"
        lockfile_path.write_text("")

        from oss_sustain_guard.dependency_parsers import load_dependency_parser_specs

        specs = load_dependency_parser_specs()
        parser = next((s for s in specs if "build.sbt.lock" in s.lockfile_names), None)

        # Should find the parser
        assert parser is not None


def test_kotlin_parser_registered():
    """Test that Kotlin parser is registered."""
    from oss_sustain_guard.dependency_parsers import load_dependency_parser_specs

    specs = load_dependency_parser_specs()
    kotlin_parser = next((s for s in specs if s.name == "kotlin"), None)
    assert kotlin_parser is not None
    assert "gradle.lockfile" in kotlin_parser.lockfile_names


def test_kotlin_lockfile_detection():
    """Test that Kotlin lockfiles are detected."""
    from oss_sustain_guard.dependency_parsers import load_dependency_parser_specs

    specs = load_dependency_parser_specs()
    kotlin_parser = next((s for s in specs if s.name == "kotlin"), None)

    assert kotlin_parser is not None
    assert "gradle.lockfile" in kotlin_parser.lockfile_names
    assert "build.gradle.kts.lock" in kotlin_parser.lockfile_names


def test_jvm_languages_integration():
    """Test that Java, Kotlin, and Scala parsers are all registered."""
    from oss_sustain_guard.dependency_parsers import load_dependency_parser_specs

    specs = load_dependency_parser_specs()
    jvm_parsers = {s.name: s for s in specs if s.name in ["java", "kotlin", "scala"]}

    assert len(jvm_parsers) == 3, "All three JVM language parsers should be registered"
    assert "java" in jvm_parsers
    assert "kotlin" in jvm_parsers
    assert "scala" in jvm_parsers
