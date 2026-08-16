"""
Resolver registry and factory functions for managing multiple language resolvers.
"""

from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path
from warnings import warn

from oss_sustain_guard.config import get_exclusion_patterns
from oss_sustain_guard.resolvers.base import LanguageResolver

_BUILTIN_MODULES = [
    "oss_sustain_guard.resolvers.python",
    "oss_sustain_guard.resolvers.javascript",
    "oss_sustain_guard.resolvers.dart",
    "oss_sustain_guard.resolvers.elixir",
    "oss_sustain_guard.resolvers.go",
    "oss_sustain_guard.resolvers.haskell",
    "oss_sustain_guard.resolvers.java",
    "oss_sustain_guard.resolvers.kotlin",
    "oss_sustain_guard.resolvers.perl",
    "oss_sustain_guard.resolvers.php",
    "oss_sustain_guard.resolvers.r",
    "oss_sustain_guard.resolvers.ruby",
    "oss_sustain_guard.resolvers.rust",
    "oss_sustain_guard.resolvers.csharp",
    "oss_sustain_guard.resolvers.swift",
]


def _load_builtin_resolvers() -> list[LanguageResolver]:
    resolvers: list[LanguageResolver] = []
    for module_path in _BUILTIN_MODULES:
        module = import_module(module_path)
        resolver = getattr(module, "RESOLVER", None)
        if resolver is not None:
            resolvers.append(resolver)
    return resolvers


def _load_entrypoint_resolvers() -> list[LanguageResolver]:
    resolvers: list[LanguageResolver] = []
    for entry_point in entry_points(group="oss_sustain_guard.resolvers"):
        try:
            loaded = entry_point.load()
        except Exception as exc:
            warn(
                f"Note: Unable to load resolver plugin '{entry_point.name}': {exc}",
                stacklevel=2,
            )
            continue
        if isinstance(loaded, LanguageResolver):
            resolvers.append(loaded)
            continue
        if callable(loaded):
            try:
                resolver = loaded()
            except Exception as exc:
                warn(
                    "Note: Unable to initialize resolver plugin "
                    f"'{entry_point.name}': {exc}",
                    stacklevel=2,
                )
                continue
            if isinstance(resolver, LanguageResolver):
                resolvers.append(resolver)
    return resolvers


def load_resolvers() -> list[LanguageResolver]:
    """Load built-in and entrypoint resolvers.

    Built-in resolvers are always loaded. Entrypoint resolvers are added if they do
    not share an ecosystem name with an existing built-in resolver.
    """
    resolvers = _load_builtin_resolvers()
    existing = {resolver.ecosystem_name for resolver in resolvers}

    for resolver in _load_entrypoint_resolvers():
        if resolver.ecosystem_name in existing:
            continue
        resolvers.append(resolver)
        existing.add(resolver.ecosystem_name)

    return resolvers


# Global registry of resolvers
_RESOLVERS: dict[str, LanguageResolver] = {}


def _initialize_resolvers() -> None:
    """Initialize all registered resolvers."""
    global _RESOLVERS
    if not _RESOLVERS:
        for resolver in load_resolvers():
            _RESOLVERS[resolver.ecosystem_name] = resolver
            # Add aliases
            if resolver.ecosystem_name == "python":
                _RESOLVERS["py"] = resolver
            elif resolver.ecosystem_name == "javascript":
                _RESOLVERS["typescript"] = resolver
                _RESOLVERS["js"] = resolver
                _RESOLVERS["npm"] = resolver
            elif resolver.ecosystem_name == "dart":
                _RESOLVERS["pub"] = resolver
            elif resolver.ecosystem_name == "elixir":
                _RESOLVERS["hex"] = resolver
            elif resolver.ecosystem_name == "go":
                pass  # No aliases
            elif resolver.ecosystem_name == "haskell":
                _RESOLVERS["hackage"] = resolver
            elif resolver.ecosystem_name == "java":
                _RESOLVERS["kotlin"] = resolver  # Kotlin uses JavaResolver
                _RESOLVERS["scala"] = resolver
                _RESOLVERS["maven"] = resolver
            elif resolver.ecosystem_name == "kotlin":
                pass  # Handled above
            elif resolver.ecosystem_name == "perl":
                _RESOLVERS["cpan"] = resolver
            elif resolver.ecosystem_name == "php":
                _RESOLVERS["composer"] = resolver
            elif resolver.ecosystem_name == "r":
                _RESOLVERS["cran"] = resolver
            elif resolver.ecosystem_name == "ruby":
                _RESOLVERS["gem"] = resolver
            elif resolver.ecosystem_name == "rust":
                pass  # No aliases
            elif resolver.ecosystem_name == "csharp":
                _RESOLVERS["dotnet"] = resolver
                _RESOLVERS["nuget"] = resolver
            elif resolver.ecosystem_name == "swift":
                _RESOLVERS["spm"] = resolver


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
    seen_classes = set()
    unique_resolvers = []
    for resolver in _RESOLVERS.values():
        if resolver.__class__ not in seen_classes:
            seen_classes.add(resolver.__class__)
            unique_resolvers.append(resolver)
    return unique_resolvers


__all__ = [
    "LanguageResolver",
    "get_resolver",
    "register_resolver",
    "get_all_resolvers",
    "detect_ecosystems",
    "find_manifest_files",
    "find_lockfiles",
]


async def detect_ecosystems(
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
            lockfiles = await resolver.detect_lockfiles(str(scan_dir))
            if any(lf.exists() for lf in lockfiles):
                if resolver.ecosystem_name not in detected:
                    detected.append(resolver.ecosystem_name)

            # Also check for manifest files as a fallback
            for manifest in await resolver.get_manifest_files():
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


async def find_manifest_files(
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

            for manifest_name in await resolver.get_manifest_files():
                manifest_path = scan_dir / manifest_name
                if (
                    manifest_path.exists()
                    and manifest_path not in manifest_files[eco_name]
                ):
                    manifest_files[eco_name].append(manifest_path)

    return {k: v for k, v in manifest_files.items() if v}  # Remove empty entries


async def find_lockfiles(
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

            detected_locks = await resolver.detect_lockfiles(str(scan_dir))
            for lockfile in detected_locks:
                if lockfile.exists() and lockfile not in lockfiles[eco_name]:
                    lockfiles[eco_name].append(lockfile)

    return {k: v for k, v in lockfiles.items() if v}  # Remove empty entries
