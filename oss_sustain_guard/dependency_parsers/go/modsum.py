"""Go lockfile dependency parser spec."""

from oss_sustain_guard.dependency_parsers.resolver_helpers import make_resolver_parser

PARSER = make_resolver_parser(
    name="go",
    ecosystem="go",
    lockfile_names={"go.sum"},
)
