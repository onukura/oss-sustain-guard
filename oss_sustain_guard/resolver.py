"""
Resolves PyPI package names to their corresponding GitHub repository URLs.

DEPRECATED: This module is maintained for backward compatibility.
Use oss_sustain_guard.resolvers instead.
"""

# Re-export from new location for backward compatibility
from oss_sustain_guard.resolvers.python import (
    detect_lockfiles,
    get_github_url_from_pypi,
    get_packages_from_lockfile,
    parse_lockfile_pipenv,
    parse_lockfile_poetry,
    parse_lockfile_uv,
)

__all__ = [
    "get_github_url_from_pypi",
    "parse_lockfile_poetry",
    "parse_lockfile_uv",
    "parse_lockfile_pipenv",
    "get_packages_from_lockfile",
    "detect_lockfiles",
]
