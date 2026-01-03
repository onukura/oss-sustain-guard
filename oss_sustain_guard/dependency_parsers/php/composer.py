"""PHP lockfile dependency parser spec."""

from oss_sustain_guard.dependency_parsers.resolver_helpers import make_resolver_parser

PARSER = make_resolver_parser(
    name="php",
    ecosystem="php",
    lockfile_names={"composer.lock"},
)
