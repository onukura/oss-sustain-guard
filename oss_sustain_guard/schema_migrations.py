"""
Schema version migrations for OSS Sustain Guard.

This module manages backward compatibility between different schema versions
of the metric database. As metrics evolve, this mapping ensures old data
can be correctly interpreted by new code.

Schema Versions:
- v1.x: Original schema with simplified metric names
- v2.0: CHAOSS-aligned metric names with extended metric set (21 metrics)

Future versions should add new mappings here.
"""

from typing import Final

# Current schema version
CURRENT_SCHEMA_VERSION: Final[str] = "2.0"

# Metric name migrations: {version: {old_name: new_name}}
# Each version maps from previous schema to current schema
METRIC_NAME_MIGRATIONS: Final[dict[str, dict[str, str]]] = {
    # v1.x to v2.0 migration
    "1.x": {
        # Core sustainability metrics (original 9)
        "Bus Factor": "Contributor Redundancy",
        "Maintainer Drain": "Maintainer Retention",
        "Zombie Check": "Recent Activity",
        "Merge Velocity": "Change Request Resolution",
        "CI Status": "Build Health",
        "Funding": "Funding Signals",
        "Release Cadence": "Release Rhythm",
        "Security Posture": "Security Signals",
        "Community Health": "Issue Responsiveness",
    },
    # Future migrations can be added here:
    # "2.x": {
    #     "Old Metric Name": "New Metric Name",
    # },
}


def normalize_metric_name(metric_name: str, from_version: str = "1.x") -> str:
    """
    Normalize a metric name from an older schema version to current schema.

    Args:
        metric_name: The metric name to normalize
        from_version: Source schema version (default: "1.x")

    Returns:
        Normalized metric name for current schema, or original name if no mapping exists

    Examples:
        >>> normalize_metric_name("Bus Factor")
        'Contributor Redundancy'
        >>> normalize_metric_name("Unknown Metric")
        'Unknown Metric'
    """
    if from_version in METRIC_NAME_MIGRATIONS:
        return METRIC_NAME_MIGRATIONS[from_version].get(metric_name, metric_name)
    return metric_name


def get_all_legacy_names() -> set[str]:
    """
    Get all legacy metric names across all schema versions.

    Returns:
        Set of all old metric names that have migrations defined

    Example:
        >>> legacy_names = get_all_legacy_names()
        >>> "Bus Factor" in legacy_names
        True
    """
    all_names = set()
    for migration_map in METRIC_NAME_MIGRATIONS.values():
        all_names.update(migration_map.keys())
    return all_names


def is_legacy_metric_name(metric_name: str) -> bool:
    """
    Check if a metric name is from a legacy schema version.

    Args:
        metric_name: The metric name to check

    Returns:
        True if this is a legacy name that needs migration

    Example:
        >>> is_legacy_metric_name("Bus Factor")
        True
        >>> is_legacy_metric_name("Contributor Redundancy")
        False
    """
    return metric_name in get_all_legacy_names()


def get_migration_info(metric_name: str) -> dict[str, str] | None:
    """
    Get migration information for a legacy metric name.

    Args:
        metric_name: The legacy metric name

    Returns:
        Dictionary with 'from_version' and 'to_name', or None if not a legacy name

    Example:
        >>> info = get_migration_info("Bus Factor")
        >>> info['to_name']
        'Contributor Redundancy'
    """
    for version, migration_map in METRIC_NAME_MIGRATIONS.items():
        if metric_name in migration_map:
            return {
                "from_version": version,
                "to_name": migration_map[metric_name],
                "current_version": CURRENT_SCHEMA_VERSION,
            }
    return None
