"""
Resolver registry and factory functions for managing multiple language resolvers.
"""

from pathlib import Path

from oss_sustain_guard.config import get_exclusion_patterns
from oss_sustain_guard.resolvers.base import LanguageResolver
from oss_sustain_guard.resolvers.csharp import CSharpResolver
from oss_sustain_guard.resolvers.go import GoResolver
from oss_sustain_guard.resolvers.java import JavaResolver
from oss_sustain_guard.resolvers.javascript import JavaScriptResolver
from oss_sustain_guard.resolvers.kotlin import KotlinResolver
from oss_sustain_guard.resolvers.php import PhpResolver
from oss_sustain_guard.resolvers.python import PythonResolver
from oss_sustain_guard.resolvers.ruby import RubyResolver
from oss_sustain_guard.resolvers.rust import RustResolver

# Global registry of resolvers
_RESOLVERS: dict[str, LanguageResolver] = {}


def _initialize_resolvers() -> None:
    """Initialize all registered resolvers."""
    global _RESOLVERS
    if not _RESOLVERS:
        _RESOLVERS["python"] = PythonResolver()
        _RESOLVERS["py"] = PythonResolver()  # Alias
        _RESOLVERS["javascript"] = JavaScriptResolver()
        _RESOLVERS["typescript"] = JavaScriptResolver()  # Alias
        _RESOLVERS["js"] = JavaScriptResolver()  # Alias
        _RESOLVERS["npm"] = JavaScriptResolver()  # Alias
        _RESOLVERS["go"] = GoResolver()
        _RESOLVERS["ruby"] = RubyResolver()
        _RESOLVERS["gem"] = RubyResolver()  # Alias
        _RESOLVERS["rust"] = RustResolver()
        _RESOLVERS["php"] = PhpResolver()
        _RESOLVERS["composer"] = PhpResolver()  # Alias
        _RESOLVERS["java"] = JavaResolver()
        _RESOLVERS["kotlin"] = KotlinResolver()
        _RESOLVERS["scala"] = JavaResolver()  # Alias (uses Maven Central/sbt)
        _RESOLVERS["maven"] = JavaResolver()  # Alias
        _RESOLVERS["csharp"] = CSharpResolver()
        _RESOLVERS["dotnet"] = CSharpResolver()  # Alias
        _RESOLVERS["nuget"] = CSharpResolver()  # Alias


def get_resolver(ecosystem: str) -> LanguageResolver | None:
    """
    Get resolver for the specified ecosystem.

    Args:
        ecosystem: Ecosystem name (e.g., 'python', 'javascript', 'go', 'rust').

    Returns:
        LanguageResolver instance or None if ecosystem is not registered.
    """
    _initialize_resolvers()
    return _RESOLVERS.get(ecosystem.lower())


def register_resolver(ecosystem: str, resolver: LanguageResolver) -> None:
    """
    Register a new resolver for an ecosystem.

    Args:
        ecosystem: Ecosystem name to register.
        resolver: LanguageResolver instance.
    """
    _initialize_resolvers()
    _RESOLVERS[ecosystem.lower()] = resolver


def get_all_resolvers() -> list[LanguageResolver]:
    """
    Get all registered resolvers (deduplicated).

    Returns:
        List of unique LanguageResolver instances.
    """
    _initialize_resolvers()
    # Deduplicate by resolver class to avoid returning the same resolver multiple times
    seen = set()
    unique_resolvers = []
    for resolver in _RESOLVERS.values():
        resolver_id = id(resolver)
        if resolver_id not in seen:
            seen.add(resolver_id)
            unique_resolvers.append(resolver)
    return unique_resolvers


def detect_ecosystems(
    directory: str | Path = ".", recursive: bool = False, max_depth: int | None = None
) -> list[str]:
    """
    Auto-detect ecosystems present in the directory.

    Scans for lockfiles and manifest files to determine which ecosystems
    are being used in the project.

    Args:
        directory: Directory to scan for ecosystem indicators.
        recursive: If True, scan subdirectories recursively.
        max_depth: Maximum recursion depth (None for unlimited).

    Returns:
        List of ecosystem names (e.g., ['python', 'javascript']).
    """
    _initialize_resolvers()
    directory = Path(directory)
    detected = []

    if recursive:
        # Recursive scan with depth limit
        directories_to_scan = _get_directories_recursive(directory, max_depth)
    else:
        # Only scan the specified directory
        directories_to_scan = [directory]

    for scan_dir in directories_to_scan:
        for resolver in get_all_resolvers():
            lockfiles = resolver.detect_lockfiles(str(scan_dir))
            if any(lf.exists() for lf in lockfiles):
                if resolver.ecosystem_name not in detected:
                    detected.append(resolver.ecosystem_name)

            # Also check for manifest files as a fallback
            for manifest in resolver.get_manifest_files():
                if (scan_dir / manifest).exists():
                    if resolver.ecosystem_name not in detected:
                        detected.append(resolver.ecosystem_name)
                    break

    return sorted(detected)


def _get_directories_recursive(
    directory: Path, max_depth: int | None = None
) -> list[Path]:
    """
    Get all directories recursively up to max_depth.

    Uses exclusion patterns from configuration, .gitignore, and defaults.

    Args:
        directory: Root directory to start from.
        max_depth: Maximum recursion depth (None for unlimited).

    Returns:
        List of directory paths including the root.
    """
    directories = [directory]
    # Get exclusion patterns (includes defaults, config, and .gitignore)
    skip_patterns = get_exclusion_patterns(directory)

    def _scan_recursive(current_dir: Path, current_depth: int) -> None:
        # Check depth limit
        if max_depth is not None and current_depth >= max_depth:
            return

        try:
            for item in current_dir.iterdir():
                # Skip hidden directories (starting with .)
                if item.is_dir() and not item.name.startswith("."):
                    # Check against exclusion patterns
                    if item.name not in skip_patterns:
                        directories.append(item)
                        _scan_recursive(item, current_depth + 1)
        except PermissionError:
            # Skip directories we don't have permission to read
            pass

    _scan_recursive(directory, 0)
    return directories


def find_manifest_files(
    directory: str | Path = ".",
    ecosystem: str | None = None,
    recursive: bool = False,
    max_depth: int | None = None,
) -> dict[str, list[Path]]:
    """
    Find all manifest files in the directory.

    Args:
        directory: Directory to scan.
        ecosystem: If specified, only scan for this ecosystem's manifests.
        recursive: If True, scan subdirectories recursively.
        max_depth: Maximum recursion depth (None for unlimited).

    Returns:
        Dictionary mapping ecosystem name to list of manifest file paths.
    """
    _initialize_resolvers()
    directory = Path(directory)
    manifest_files: dict[str, list[Path]] = {}

    if recursive:
        directories_to_scan = _get_directories_recursive(directory, max_depth)
    else:
        directories_to_scan = [directory]

    # Get resolvers to scan
    if ecosystem:
        resolver = get_resolver(ecosystem)
        resolvers = [resolver] if resolver else []
    else:
        resolvers = get_all_resolvers()

    for scan_dir in directories_to_scan:
        for resolver in resolvers:
            eco_name = resolver.ecosystem_name
            if eco_name not in manifest_files:
                manifest_files[eco_name] = []

            for manifest_name in resolver.get_manifest_files():
                manifest_path = scan_dir / manifest_name
                if (
                    manifest_path.exists()
                    and manifest_path not in manifest_files[eco_name]
                ):
                    manifest_files[eco_name].append(manifest_path)

    return {k: v for k, v in manifest_files.items() if v}  # Remove empty entries


def find_lockfiles(
    directory: str | Path = ".",
    ecosystem: str | None = None,
    recursive: bool = False,
    max_depth: int | None = None,
) -> dict[str, list[Path]]:
    """
    Find all lockfiles in the directory.

    Args:
        directory: Directory to scan.
        ecosystem: If specified, only scan for this ecosystem's lockfiles.
        recursive: If True, scan subdirectories recursively.
        max_depth: Maximum recursion depth (None for unlimited).

    Returns:
        Dictionary mapping ecosystem name to list of lockfile paths.
    """
    _initialize_resolvers()
    directory = Path(directory)
    lockfiles: dict[str, list[Path]] = {}

    if recursive:
        directories_to_scan = _get_directories_recursive(directory, max_depth)
    else:
        directories_to_scan = [directory]

    # Get resolvers to scan
    if ecosystem:
        resolver = get_resolver(ecosystem)
        resolvers = [resolver] if resolver else []
    else:
        resolvers = get_all_resolvers()

    for scan_dir in directories_to_scan:
        for resolver in resolvers:
            eco_name = resolver.ecosystem_name
            if eco_name not in lockfiles:
                lockfiles[eco_name] = []

            detected_locks = resolver.detect_lockfiles(str(scan_dir))
            for lockfile in detected_locks:
                if lockfile.exists() and lockfile not in lockfiles[eco_name]:
                    lockfiles[eco_name].append(lockfile)

    return {k: v for k, v in lockfiles.items() if v}  # Remove empty entries
