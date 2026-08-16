"""Haskell lockfile dependency parser spec."""

from oss_sustain_guard.dependency_parsers.resolver_helpers import make_resolver_parser

PARSER = make_resolver_parser(
    name="haskell",
    ecosystem="haskell",
    lockfile_names={"cabal.project.freeze", "stack.yaml.lock"},
)
