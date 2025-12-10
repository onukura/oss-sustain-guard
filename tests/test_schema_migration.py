"""
Tests for schema version migration and backward compatibility.
"""

from oss_sustain_guard.core import Metric, compute_weighted_total_score
from oss_sustain_guard.schema_migrations import (
    METRIC_NAME_MIGRATIONS,
    get_all_legacy_names,
    get_migration_info,
    is_legacy_metric_name,
    normalize_metric_name,
)


def test_metric_name_migration_mapping():
    """Test that all v1.x metric names have migrations defined."""
    expected_v1_names = [
        "Bus Factor",
        "Maintainer Drain",
        "Zombie Check",
        "Merge Velocity",
        "CI Status",
        "Funding",
        "Release Cadence",
        "Security Posture",
        "Community Health",
    ]

    v1_migrations = METRIC_NAME_MIGRATIONS["1.x"]
    for old_name in expected_v1_names:
        assert old_name in v1_migrations, f"{old_name} missing in migration map"
        assert isinstance(v1_migrations[old_name], str)


def test_compute_weighted_total_score_with_v1_names():
    """Test that v1.x metric names are automatically converted to v2.0."""
    # Create metrics with v1.x names (9 core metrics from legacy schema)
    v1_metrics = [
        Metric("Bus Factor", 20, 20, "Healthy", "None"),  # -> Contributor Redundancy
        Metric(
            "Maintainer Drain", 10, 10, "Healthy", "None"
        ),  # -> Maintainer Retention
        Metric("Zombie Check", 20, 20, "Active", "None"),  # -> Recent Activity
        Metric(
            "Merge Velocity", 10, 10, "Good", "None"
        ),  # -> Change Request Resolution
        Metric("CI Status", 10, 10, "Passing", "None"),  # -> Build Health
        Metric("Funding", 10, 10, "Funded", "None"),  # -> Funding Signals
        Metric("Release Cadence", 10, 10, "Regular", "None"),  # -> Release Rhythm
        Metric("Security Posture", 5, 5, "Good", "None"),  # -> Security Signals
        Metric("Community Health", 8, 8, "Healthy", "None"),  # -> Issue Responsiveness
    ]

    # Calculate score - should work with v1.x names
    score = compute_weighted_total_score(v1_metrics, profile="balanced")

    # Should get a valid score
    # Note: Score won't be 100 because we only have 9/21 metrics (not all categories fully covered)
    assert isinstance(score, int)
    assert 0 <= score <= 100
    assert score >= 80  # Should be high since all provided metrics are at max


def test_compute_weighted_total_score_with_v2_names():
    """Test that v2.0 metric names work directly."""
    # Create metrics with v2.0 names (actual names from SCORING_CATEGORIES)
    v2_metrics = [
        Metric("Contributor Redundancy", 20, 20, "Healthy", "None"),
        Metric("Maintainer Retention", 10, 10, "Healthy", "None"),
        Metric("Recent Activity", 20, 20, "Active", "None"),
        Metric("Change Request Resolution", 10, 10, "Good", "None"),
        Metric("Build Health", 10, 10, "Passing", "None"),
        Metric("Funding Signals", 10, 10, "Funded", "None"),
        Metric("Release Rhythm", 10, 10, "Regular", "None"),
        Metric("Security Signals", 5, 5, "Good", "None"),
        Metric("Issue Responsiveness", 8, 8, "Healthy", "None"),
    ]

    # Calculate score - should work with v2.0 names
    score = compute_weighted_total_score(v2_metrics, profile="balanced")

    # Should get a valid score
    assert isinstance(score, int)
    assert 0 <= score <= 100
    assert score >= 80  # High score since all provided metrics are at max


def test_mixed_v1_v2_metrics():
    """Test that mixed v1.x and v2.0 metric names work together."""
    mixed_metrics = [
        # v1.x names
        Metric("Bus Factor", 20, 20, "Healthy", "None"),
        Metric("Zombie Check", 20, 20, "Active", "None"),
        # v2.0 names
        Metric("Maintainer Retention", 10, 10, "Healthy", "None"),
        Metric("Change Request Resolution", 10, 10, "Good", "None"),
        Metric("Build Health", 10, 10, "Passing", "None"),
        Metric("Funding Signals", 10, 10, "Funded", "None"),
        Metric("Release Rhythm", 10, 10, "Regular", "None"),
        Metric("Security Signals", 5, 5, "Good", "None"),
        Metric("Issue Responsiveness", 8, 8, "Healthy", "None"),
    ]

    # Should handle mixed names gracefully
    score = compute_weighted_total_score(mixed_metrics, profile="balanced")

    assert isinstance(score, int)
    assert 0 <= score <= 100
    assert score >= 80  # High score since all provided metrics are at max


def test_v1_metrics_produce_same_score_as_v2():
    """Test that v1.x and v2.0 metric names produce identical scores."""
    # v1.x metrics
    v1_metrics = [
        Metric("Bus Factor", 15, 20, "Medium", "Medium"),
        Metric("Maintainer Drain", 8, 10, "Moderate", "Low"),
        Metric("Zombie Check", 18, 20, "Active", "None"),
    ]

    # Equivalent v2.0 metrics
    v2_metrics = [
        Metric("Contributor Redundancy", 15, 20, "Medium", "Medium"),
        Metric("Maintainer Retention", 8, 10, "Moderate", "Low"),
        Metric("Recent Activity", 18, 20, "Active", "None"),
    ]

    v1_score = compute_weighted_total_score(v1_metrics, profile="balanced")
    v2_score = compute_weighted_total_score(v2_metrics, profile="balanced")

    assert v1_score == v2_score


def test_all_profiles_support_v1_metrics():
    """Test that all scoring profiles work with v1.x metric names."""
    v1_metrics = [
        Metric("Bus Factor", 20, 20, "Healthy", "None"),
        Metric("Maintainer Drain", 10, 10, "Healthy", "None"),
        Metric("Zombie Check", 20, 20, "Active", "None"),
        Metric("Merge Velocity", 10, 10, "Good", "None"),
        Metric("CI Status", 10, 10, "Passing", "None"),
        Metric("Funding", 10, 10, "Funded", "None"),
        Metric("Release Cadence", 10, 10, "Regular", "None"),
        Metric("Security Posture", 5, 5, "Good", "None"),
        Metric("Community Health", 8, 8, "Healthy", "None"),
    ]

    profiles = [
        "balanced",
        "security_first",
        "contributor_experience",
        "long_term_stability",
    ]

    for profile in profiles:
        score = compute_weighted_total_score(v1_metrics, profile=profile)
        assert isinstance(score, int), f"Profile {profile} failed with v1.x metrics"
        assert 0 <= score <= 100
        assert score >= 70  # Should be reasonably high for all profiles


# --- Tests for schema_migrations module helper functions ---


def test_normalize_metric_name():
    """Test metric name normalization function."""
    assert normalize_metric_name("Bus Factor") == "Contributor Redundancy"
    assert normalize_metric_name("Zombie Check") == "Recent Activity"
    assert normalize_metric_name("Unknown Metric") == "Unknown Metric"
    assert normalize_metric_name("Contributor Redundancy") == "Contributor Redundancy"


def test_is_legacy_metric_name():
    """Test legacy metric name detection."""
    assert is_legacy_metric_name("Bus Factor") is True
    assert is_legacy_metric_name("Maintainer Drain") is True
    assert is_legacy_metric_name("Contributor Redundancy") is False
    assert is_legacy_metric_name("Unknown Metric") is False


def test_get_all_legacy_names():
    """Test getting all legacy metric names."""
    legacy_names = get_all_legacy_names()
    assert isinstance(legacy_names, set)
    assert "Bus Factor" in legacy_names
    assert "Maintainer Drain" in legacy_names
    assert "Zombie Check" in legacy_names
    assert len(legacy_names) == 9  # 9 v1.x metrics


def test_get_migration_info():
    """Test getting migration information for a legacy metric."""
    info = get_migration_info("Bus Factor")
    assert info is not None
    assert info["from_version"] == "1.x"
    assert info["to_name"] == "Contributor Redundancy"
    assert info["current_version"] == "2.0"

    # Non-legacy metric should return None
    assert get_migration_info("Contributor Redundancy") is None
    assert get_migration_info("Unknown Metric") is None
