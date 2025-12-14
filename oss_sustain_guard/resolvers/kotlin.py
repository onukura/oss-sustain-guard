"""
Kotlin package resolver for Maven Central.

Kotlin packages are typically distributed via Maven Central and use Gradle
as the build system. This resolver extends JavaResolver to provide
Kotlin-specific ecosystem identification.
"""

from oss_sustain_guard.resolvers.java import JavaResolver


class KotlinResolver(JavaResolver):
    """Resolver for Kotlin packages via Maven Central."""

    @property
    def ecosystem_name(self) -> str:
        return "kotlin"

    def get_manifest_files(self) -> list[str]:
        """
        Return list of Kotlin manifest files.

        Returns:
            List of manifest file names prioritizing Kotlin-specific files.
        """
        # Prioritize Kotlin DSL build files
        return ["build.gradle.kts", "build.gradle", "pom.xml"]
