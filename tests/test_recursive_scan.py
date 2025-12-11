"""
Test recursive scanning functionality for manifest and lockfiles.
"""

from pathlib import Path

from oss_sustain_guard.resolvers import (
    detect_ecosystems,
    find_lockfiles,
    find_manifest_files,
)


def test_detect_ecosystems_non_recursive(tmp_path: Path):
    """Test that non-recursive scan only detects root directory files."""
    # Create root manifest
    (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')

    # Create nested manifests that should be ignored
    subdir = tmp_path / "subproject"
    subdir.mkdir()
    (subdir / "requirements.txt").write_text("requests==2.28.0\n")

    detected = detect_ecosystems(str(tmp_path), recursive=False)

    # Should only detect javascript from root
    assert "javascript" in detected
    assert "python" not in detected


def test_detect_ecosystems_recursive(tmp_path: Path):
    """Test that recursive scan detects manifests in subdirectories."""
    # Create root manifest
    (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')

    # Create nested manifests
    subdir = tmp_path / "subproject"
    subdir.mkdir()
    (subdir / "requirements.txt").write_text("requests==2.28.0\n")

    deeper_dir = subdir / "nested"
    deeper_dir.mkdir()
    (deeper_dir / "Cargo.toml").write_text('[package]\nname = "example"\n')

    detected = detect_ecosystems(str(tmp_path), recursive=True)

    # Should detect all ecosystems
    assert "javascript" in detected
    assert "python" in detected
    assert "rust" in detected


def test_detect_ecosystems_with_depth_limit(tmp_path: Path):
    """Test that depth limit is respected."""
    # Root
    (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')

    # Depth 1
    level1 = tmp_path / "level1"
    level1.mkdir()
    (level1 / "requirements.txt").write_text("requests==2.28.0\n")

    # Depth 2
    level2 = level1 / "level2"
    level2.mkdir()
    (level2 / "Cargo.toml").write_text('[package]\nname = "example"\n')

    # With depth=1, should only detect root and level1
    detected = detect_ecosystems(str(tmp_path), recursive=True, max_depth=1)

    assert "javascript" in detected
    assert "python" in detected
    assert "rust" not in detected  # Too deep


def test_find_manifest_files_non_recursive(tmp_path: Path):
    """Test finding manifest files without recursion."""
    (tmp_path / "package.json").write_text('{"dependencies": {}}')
    (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")

    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "Cargo.toml").write_text('[package]\nname = "test"\n')

    manifests = find_manifest_files(str(tmp_path), recursive=False)

    assert "javascript" in manifests
    assert "python" in manifests
    assert "rust" not in manifests
    assert len(manifests["javascript"]) == 1
    assert len(manifests["python"]) == 1


def test_find_manifest_files_recursive(tmp_path: Path):
    """Test finding manifest files with recursion."""
    (tmp_path / "package.json").write_text('{"dependencies": {}}')

    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "requirements.txt").write_text("requests==2.28.0\n")

    manifests = find_manifest_files(str(tmp_path), recursive=True)

    assert "javascript" in manifests
    assert "python" in manifests
    assert len(manifests["javascript"]) == 1
    assert len(manifests["python"]) == 1


def test_find_lockfiles_recursive(tmp_path: Path):
    """Test finding lockfiles with recursion."""
    # Root lockfile
    (tmp_path / "package-lock.json").write_text('{"lockfileVersion": 2}')

    # Nested lockfile
    subdir = tmp_path / "backend"
    subdir.mkdir()
    (subdir / "poetry.lock").write_text("# Poetry lock\n")

    lockfiles = find_lockfiles(str(tmp_path), recursive=True)

    assert "javascript" in lockfiles
    assert "python" in lockfiles


def test_skips_common_directories(tmp_path: Path):
    """Test that common build/cache directories are skipped."""
    # Create manifest in node_modules (should be skipped)
    node_modules = tmp_path / "node_modules" / "@types" / "react"
    node_modules.mkdir(parents=True)
    (node_modules / "package.json").write_text('{"name": "@types/react"}')

    # Create manifest in venv (should be skipped)
    venv = tmp_path / "venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "requirements.txt").write_text("pytest==7.0.0\n")

    # Create manifest in root (should be detected)
    (tmp_path / "package.json").write_text('{"dependencies": {}}')

    manifests = find_manifest_files(str(tmp_path), recursive=True)

    # Should only find root manifest
    assert "javascript" in manifests
    assert len(manifests["javascript"]) == 1
    assert manifests["javascript"][0] == tmp_path / "package.json"


def test_find_manifest_files_with_ecosystem_filter(tmp_path: Path):
    """Test filtering by specific ecosystem."""
    (tmp_path / "package.json").write_text('{"dependencies": {}}')
    (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")

    # Filter for JavaScript only
    manifests = find_manifest_files(str(tmp_path), ecosystem="javascript")

    assert "javascript" in manifests
    assert "python" not in manifests


def test_recursive_depth_zero_means_root_only(tmp_path: Path):
    """Test that depth=0 only scans the root directory."""
    (tmp_path / "package.json").write_text('{"dependencies": {}}')

    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "requirements.txt").write_text("requests==2.28.0\n")

    detected = detect_ecosystems(str(tmp_path), recursive=True, max_depth=0)

    # With depth=0 in recursive mode, should only see root
    assert "javascript" in detected
    assert "python" not in detected


def test_multiple_manifests_same_ecosystem(tmp_path: Path):
    """Test finding multiple manifest files for the same ecosystem."""
    # Create multiple Python projects
    (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")

    proj1 = tmp_path / "project1"
    proj1.mkdir()
    (proj1 / "requirements.txt").write_text("flask==2.0.0\n")

    proj2 = tmp_path / "project2"
    proj2.mkdir()
    (proj2 / "pyproject.toml").write_text('[project]\nname = "example"\n')

    manifests = find_manifest_files(str(tmp_path), recursive=True)

    # Should find all three Python manifests
    assert "python" in manifests
    assert len(manifests["python"]) == 3


def test_respects_gitignore(tmp_path: Path):
    """Test that .gitignore patterns are respected."""
    # Create .gitignore
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("ignored_dir\ncustom_cache\n")

    # Create manifests in ignored directories
    ignored = tmp_path / "ignored_dir"
    ignored.mkdir()
    (ignored / "package.json").write_text('{"name": "ignored"}')

    cache = tmp_path / "custom_cache"
    cache.mkdir()
    (cache / "requirements.txt").write_text("cached==1.0.0\n")

    # Create manifest in non-ignored directory
    (tmp_path / "package.json").write_text('{"dependencies": {}}')

    manifests = find_manifest_files(str(tmp_path), recursive=True)

    # Should only find root manifest
    assert "javascript" in manifests
    assert len(manifests["javascript"]) == 1
    assert manifests["javascript"][0] == tmp_path / "package.json"
    # Should not find Python manifest in ignored dir
    assert "python" not in manifests


def test_skips_hidden_directories(tmp_path: Path):
    """Test that hidden directories (starting with .) are skipped."""
    # Create manifest in hidden directory
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "package.json").write_text('{"name": "hidden"}')

    # Create manifest in root
    (tmp_path / "package.json").write_text('{"dependencies": {}}')

    manifests = find_manifest_files(str(tmp_path), recursive=True)

    # Should only find root manifest
    assert "javascript" in manifests
    assert len(manifests["javascript"]) == 1
    assert manifests["javascript"][0] == tmp_path / "package.json"
