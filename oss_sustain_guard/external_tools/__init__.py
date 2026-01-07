"""External tool wrappers for resolving dependency trees."""

from enum import Enum

from oss_sustain_guard.external_tools.base import ExternalTool


class ExternalToolName(str, Enum):
    """Available external package manager tools for dependency resolution.

    These tools are used in package mode to resolve dependency trees.
    Each tool is associated with a specific ecosystem:
    - Python: uv
    - JavaScript: npm, pnpm, bun
    - Rust: cargo
    - Ruby: bundler
    """

    UV = "uv"
    NPM = "npm"
    PNPM = "pnpm"
    BUN = "bun"
    CARGO = "cargo"
    BUNDLER = "bundler"


__all__ = ["ExternalTool", "ExternalToolName"]
