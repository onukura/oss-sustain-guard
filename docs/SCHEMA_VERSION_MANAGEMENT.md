# Schema Version Management Guide

## Overview

OSS Sustain Guard uses a **dual version management system** to ensure backward compatibility:

1. **Schema Version** (`_schema_version`) - Tracks changes to data structure and metric names
2. **Analysis Version** (`analysis_version`) - Tracks changes to scoring/calculation logic

This allows old cached data to work seamlessly with new code versions while invalidating cache when computation logic changes.

## Version Types

### Schema Version (`_schema_version`)

- **Purpose**: Tracks changes to data structure (field names, metric names, data format)
- **Location**: Top-level wrapper metadata in database files
- **Current**: `"2.0"`
- **Backward Compatibility**: Automatic migration via `normalize_metric_name()`
- **Example Change**: Renaming "Bus Factor" → "Contributor Redundancy"

### Analysis Version (`analysis_version`)

- **Purpose**: Tracks changes to scoring/calculation logic that affect computed values
- **Location**: Per-package entry in cached data
- **Current**: `"1.0"`
- **Cache Invalidation**: Mismatched versions cause cache entries to be skipped
- **Example Change**: Changing category weights (25%→30%) or metric scoring formulas

**Key Difference**: Schema changes allow migration (old names work), but analysis changes require re-computation (cache must be refreshed).

## Architecture

### Core Components

1. **`oss_sustain_guard/schema_migrations.py`** - Central migration registry
   - `CURRENT_SCHEMA_VERSION`: Current schema version constant (`"2.0"`)
   - `ANALYSIS_VERSION`: Current analysis version constant (`"1.0"`)
   - `METRIC_NAME_MIGRATIONS`: Version-specific metric name mappings
   - `is_analysis_version_compatible()`: Check if cached data is compatible with current analysis version
   - Helper functions for metric name normalization

2. **`oss_sustain_guard/core.py`** - Automatic migration in scoring
   - Uses `normalize_metric_name()` to convert legacy names
   - Transparent backward compatibility in `compute_weighted_total_score()`

3. **`builder/build_db.py`** - Schema and analysis metadata in database
   - Wraps package data with schema version information at top-level
   - Embeds analysis version in each package entry
   - Format: `{"_schema_version": "2.0", "_generated_at": "...", "packages": {"python:requests": {"analysis_version": "1.0", ...}, ...}}`

4. **`oss_sustain_guard/cache.py`** & **`cli.py`** - Multi-version data loading
   - Automatically detects and handles v1.x (flat dict) and v2.0+ (wrapped) formats

## Schema Versions

### v1.x (Legacy)

Original schema with 9 simplified metric names:

- Bus Factor
- Maintainer Drain
- Zombie Check
- Merge Velocity
- CI Status
- Funding
- Release Cadence
- Security Posture
- Community Health

### v2.0 (Current)

CHAOSS-aligned schema with 21 metrics:

- **Maintainer Health**: Contributor Redundancy, Maintainer Retention, Contributor Attraction, Contributor Retention, Organizational Diversity
- **Development Activity**: Recent Activity, Release Rhythm, Build Health, Change Request Resolution
- **Community Engagement**: Issue Responsiveness, PR Acceptance Ratio, PR Responsiveness, Review Health, Issue Resolution Duration
- **Project Maturity**: Documentation Presence, Code of Conduct, License Clarity, Project Popularity, Fork Activity
- **Security & Funding**: Security Signals, Funding Signals

## Usage

### Adding a New Schema Version

To add v3.0 with new metric names:

1. **Update `schema_migrations.py`**:

```python
CURRENT_SCHEMA_VERSION: Final[str] = "3.0"

METRIC_NAME_MIGRATIONS: Final[dict[str, dict[str, str]]] = {
    "1.x": {
        # Existing v1.x -> v2.0 mappings
    },
    "2.x": {
        # New v2.0 -> v3.0 mappings
        "Old Metric Name": "New Metric Name",
        "Another Old Name": "Another New Name",
    },
}
```

2. **Update `normalize_metric_name()`** (if needed):

```python
def normalize_metric_name(metric_name: str, from_version: str = "2.x") -> str:
    # Function already supports multiple versions via METRIC_NAME_MIGRATIONS
    pass
```

3. **Update tests** in `tests/test_schema_migration.py`:

```python
def test_v2_to_v3_migration():
    """Test v2.x to v3.0 metric name migration."""
    assert normalize_metric_name("Old Metric Name", "2.x") == "New Metric Name"
```

### Helper Functions

```python
from oss_sustain_guard.schema_migrations import (
    normalize_metric_name,
    is_legacy_metric_name,
    get_all_legacy_names,
    get_migration_info,
)

# Normalize a metric name
normalized = normalize_metric_name("Bus Factor")  # Returns "Contributor Redundancy"

# Check if metric is legacy
is_old = is_legacy_metric_name("Bus Factor")  # Returns True

# Get all legacy names
legacy = get_all_legacy_names()  # Returns set of all old names

# Get migration details
info = get_migration_info("Bus Factor")
# Returns: {"from_version": "1.x", "to_name": "Contributor Redundancy", "current_version": "2.0"}
```

## Database Format

### v2.0+ Format (Recommended)

```json
{
  "_schema_version": "2.0",
  "_generated_at": "2025-12-10T10:00:00Z",
  "_ecosystem": "python",
  "packages": {
    "python:requests": {
      "repo_url": "https://github.com/psf/requests",
      "total_score": 85,
      "metrics": [...]
    }
  }
}
```

### v1.x Format (Legacy, still supported)

```json
{
  "python:requests": {
    "repo_url": "https://github.com/psf/requests",
    "total_score": 85,
    "metrics": [...]
  }
}
```

Both formats are automatically detected and handled by the loading functions.

## Benefits

1. **Backward Compatibility**: Old cache data works with new code (schema changes)
2. **Cache Invalidation**: Automatic refresh when scoring logic changes (analysis version)
3. **Gradual Migration**: No need to update all databases at once
4. **Transparent**: Users don't need to know about version management
5. **Future-Proof**: Easy to add new versions as metrics evolve
6. **Centralized**: All version logic in one file

## Usage Examples

### Checking Analysis Version Compatibility

```python
from oss_sustain_guard.schema_migrations import (
    ANALYSIS_VERSION,
    is_analysis_version_compatible,
)

# Load cached data
cached_data = load_from_cache("python:requests")
payload_version = cached_data.get("analysis_version")

# Check compatibility
if not is_analysis_version_compatible(payload_version, ANALYSIS_VERSION):
    print(f"Cache outdated (version {payload_version}), performing real-time analysis...")
    # Skip cache, perform fresh analysis
else:
    print("Using cached data")
    # Use cached metrics
```

### When to Update Analysis Version

Update `ANALYSIS_VERSION` in `schema_migrations.py` when:

1. ✅ **Changing category weights** (e.g., Maintainer Health: 25% → 30%)
2. ✅ **Modifying metric scoring formulas** (e.g., changing how Contributor Redundancy is calculated)
3. ✅ **Altering aggregation logic** (e.g., changing how models compute scores)
4. ❌ **Renaming metrics** (use `METRIC_NAME_MIGRATIONS` instead)
5. ❌ **Adding new metrics** (backward compatible, no version bump needed)

### Example: Updating Analysis Version

```python
# schema_migrations.py
ANALYSIS_VERSION: Final[str] = "2.0"  # Increment when scoring logic changes

# After updating, rebuild database and clear caches:
# 1. Run: python builder/build_db.py
# 2. Run: os4g check --clear-cache
```

## Testing

Run schema migration tests:

```bash
uv run pytest tests/test_schema_migration.py -v
```

Current test coverage:

- ✅ Metric name mapping verification
- ✅ v1.x to v2.0 automatic conversion
- ✅ Mixed version metric handling
- ✅ All scoring profiles with legacy names
- ✅ Helper function correctness
- ✅ Analysis version compatibility checks
- ✅ Legacy payload handling (None version)
- ✅ Version mismatch detection
- ✅ 14 comprehensive tests

## Maintenance

When adding new metrics to the schema:

1. Add to `SCORING_CATEGORIES` in `core.py`
2. If renaming existing metrics, add mappings to `METRIC_NAME_MIGRATIONS`
3. Update `CURRENT_SCHEMA_VERSION` if major changes
4. Add corresponding tests
5. Update this documentation

## Example: Full Migration Flow

```python
# User has v1.x cached data with "Bus Factor" metric
cached_metric = {"name": "Bus Factor", "score": 20, "max_score": 20}

# CLI loads cache and creates Metric object
metric = Metric("Bus Factor", 20, 20, "Good", "None")

# Scoring function normalizes the name automatically
def compute_weighted_total_score(metrics, profile="balanced"):
    for m in metrics:
        normalized_name = normalize_metric_name(m.name)  # "Bus Factor" -> "Contributor Redundancy"
        # Use normalized_name for category matching

# Result: Old data works seamlessly with new scoring system!
```

This design ensures smooth evolution of the metric system while maintaining compatibility with existing deployments.
