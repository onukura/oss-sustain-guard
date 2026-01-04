"""Dependency parser registry and discovery helpers."""

from importlib import import_module
from importlib.metadata import entry_points
from warnings import warn

from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec

_BUILTIN_MODULES = [
    "oss_sustain_guard.dependency_parsers.python.pip",
    "oss_sustain_guard.dependency_parsers.python.pipenv",
    "oss_sustain_guard.dependency_parsers.python.poetry",
    "oss_sustain_guard.dependency_parsers.python.uv",
    "oss_sustain_guard.dependency_parsers.javascript.npm",
    "oss_sustain_guard.dependency_parsers.javascript.yarn",
    "oss_sustain_guard.dependency_parsers.javascript.pnpm",
    "oss_sustain_guard.dependency_parsers.javascript.bun",
    "oss_sustain_guard.dependency_parsers.javascript.deno",
    "oss_sustain_guard.dependency_parsers.rust.cargo_lock",
    "oss_sustain_guard.dependency_parsers.go.gomod",
    "oss_sustain_guard.dependency_parsers.ruby.bundler",
    "oss_sustain_guard.dependency_parsers.php.composer",
    "oss_sustain_guard.dependency_parsers.csharp.nuget",
    "oss_sustain_guard.dependency_parsers.dart.pub",
    "oss_sustain_guard.dependency_parsers.r.renv",
    "oss_sustain_guard.dependency_parsers.elixir.mix",
    "oss_sustain_guard.dependency_parsers.perl.cpanfile",
    "oss_sustain_guard.dependency_parsers.swift.spm",
    "oss_sustain_guard.dependency_parsers.java.gradle_maven",
    "oss_sustain_guard.dependency_parsers.kotlin",
    "oss_sustain_guard.dependency_parsers.scala",
    "oss_sustain_guard.dependency_parsers.haskell.cabal_stack",
]


def _load_builtin_dependency_parsers() -> list[DependencyParserSpec]:
    specs: list[DependencyParserSpec] = []
    for module_path in _BUILTIN_MODULES:
        module = import_module(module_path)
        parser = getattr(module, "PARSER", None)
        if parser is not None:
            specs.append(parser)
    return specs


def _load_entrypoint_dependency_parsers() -> list[DependencyParserSpec]:
    specs: list[DependencyParserSpec] = []
    for entry_point in entry_points(group="oss_sustain_guard.dependency_parsers"):
        try:
            loaded = entry_point.load()
        except Exception as exc:
            warn(
                f"Note: Unable to load dependency parser plugin '{entry_point.name}': "
                f"{exc}",
                stacklevel=2,
            )
            continue
        if isinstance(loaded, DependencyParserSpec):
            specs.append(loaded)
            continue
        if callable(loaded):
            try:
                spec = loaded()
            except Exception as exc:
                warn(
                    "Note: Unable to initialize dependency parser plugin "
                    f"'{entry_point.name}': {exc}",
                    stacklevel=2,
                )
                continue
            if isinstance(spec, DependencyParserSpec):
                specs.append(spec)
    return specs


def load_dependency_parser_specs() -> list[DependencyParserSpec]:
    """Load built-in and entrypoint dependency parser specs."""
    specs = _load_builtin_dependency_parsers()
    existing = {spec.name for spec in specs}

    for spec in _load_entrypoint_dependency_parsers():
        if spec.name in existing:
            continue
        specs.append(spec)
        existing.add(spec.name)

    return specs


__all__ = [
    "DependencyParserSpec",
    "load_dependency_parser_specs",
]
