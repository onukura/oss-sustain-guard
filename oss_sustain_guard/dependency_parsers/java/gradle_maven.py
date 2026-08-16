"""Java lockfile dependency parser spec."""

from oss_sustain_guard.dependency_parsers.resolver_helpers import make_resolver_parser

PARSER = make_resolver_parser(
    name="java",
    ecosystem="java",
    lockfile_names={"gradle.lockfile", "pom.xml.asc", "build.sbt.lock"},
)
