"""
Resolver registry and factory functions for managing multiple language resolvers.
"""

from pathlib import Path

from oss_sustain_guard.resolvers.base import LanguageResolver
from oss_sustain_guard.resolvers.csharp import CSharpResolver
from oss_sustain_guard.resolvers.go import GoResolver
from oss_sustain_guard.resolvers.java import JavaResolver
from oss_sustain_guard.resolvers.javascript import JavaScriptResolver
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
        _RESOLVERS["kotlin"] = JavaResolver()  # Alias (uses Maven Central)
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


def detect_ecosystems(directory: str | Path = ".") -> list[str]:
    """
    Auto-detect ecosystems present in the directory.

    Scans for lockfiles and manifest files to determine which ecosystems
    are being used in the project.

    Args:
        directory: Directory to scan for ecosystem indicators.

    Returns:
        List of ecosystem names (e.g., ['python', 'javascript']).
    """
    _initialize_resolvers()
    directory = Path(directory)
    detected = []

    for resolver in get_all_resolvers():
        lockfiles = resolver.detect_lockfiles(str(directory))
        if any(lf.exists() for lf in lockfiles):
            detected.append(resolver.ecosystem_name)

        # Also check for manifest files as a fallback
        for manifest in resolver.get_manifest_files():
            if (directory / manifest).exists():
                if resolver.ecosystem_name not in detected:
                    detected.append(resolver.ecosystem_name)
                break

    return sorted(detected)
