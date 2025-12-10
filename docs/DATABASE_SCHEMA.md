# Database Schema

## Overview

`data/latest/{language}.json` stores pre-computed sustainability analysis results, enabling fast lookups without real-time analysis. Each ecosystem maintains its own JSON file.

## Schema Specification (v2.0 - Multi-Language Support)

### Top-Level Structure

```json
{
  "python:requests": { ... },
  "python:django": { ... },
  "npm:react": { ... },
  "go:github.com/golang/go": { ... },
  "rust:tokio": { ... }
}
```

**Key Format**: `{ecosystem}:{package_name}`

### Entry Structure

```json
{
  "ecosystem": "python|javascript|go|rust|php|java|csharp|ruby",
  "package_name": "string",
  "github_url": "https://github.com/{owner}/{repo}",
  "total_score": 0-100,
  "metrics": [
    {
      "name": "Contributor Redundancy",
      "score": integer,
      "max_score": integer,
      "message": "string",
      "risk": "Critical|High|Medium|Low|None"
    },
    ...
  ],
  "models": [
    {
      "name": "Risk Model",
      "score": integer,
      "max_score": integer,
      "observation": "string"
    },
    ...
  ],
  "signals": {
    "contributor_count": integer,
    "funding_link_count": integer,
    "last_activity_days": integer,
    ...
  }
}
```

**Note**: The database files (`data/latest/{language}.json`) now store both individual metrics and aggregated models. Fields like `funding_links` and `is_community_driven` are computed at runtime by the `analyze_repository()` function in `core.py` when needed for CLI display.

## Field Descriptions

### Top-Level

| Field | Type | Description |
|----------|-----|------|
| `ecosystem` | string | Ecosystem name: `python`, `javascript`, `go`, `rust`, `php`, `java`, `csharp`, `ruby` |
| `package_name` | string | Package name within the ecosystem |
| `github_url` | string | GitHub repository URL |
| `total_score` | integer | Total score (0-100) |
| `metrics` | array | Array of individual metrics |
| `models` | array | Array of metric models (CHAOSS-aligned aggregations) |
| `signals` | object | Raw signal values for transparency |

### Runtime Fields (Not Stored in Database)

The following fields are computed at runtime by `analyze_repository()` in `core.py`:

| Field | Type | Description |
|----------|-----|------|
| `funding_links` | array | List of funding platforms and URLs (computed from GitHub repository data) |
| `is_community_driven` | boolean | Whether project is community-driven (vs corporate-backed) |

### Metrics

| Field | Type | Description |
|----------|-----|------|
| `name` | string | Metric name |
| `score` | integer | Score obtained |
| `max_score` | integer | Maximum score |
| `message` | string | Detailed message |
| `risk` | string | Risk level |

### Metric Models

| Field | Type | Description |
|----------|-----|------|
| `name` | string | Model name (e.g., "Risk Model", "Sustainability Model") |
| `score` | integer | Aggregated score |
| `max_score` | integer | Maximum aggregated score |
| `observation` | string | Supportive observation about the model |

### Signals

| Field | Type | Description |
|----------|-----|------|
| `contributor_count` | integer | Number of unique contributors (recent history) |
| `funding_link_count` | integer | Number of funding links detected |
| `last_activity_days` | integer | Days since last repository activity |
| `new_contributors_6mo` | integer | New contributors in last 6 months (Phase 4) |
| `contributor_retention_rate` | integer | Contributor retention rate percentage (Phase 4) |
| `avg_review_time_hours` | float | Average time to first PR review in hours (Phase 4) |
| _(extensible)_ | any | Additional raw signals as needed |

## Metrics Reference

### 12 Sustainability Metrics (Phase 1-4)

| Metric | Max Score | Risk Range | Description |
|--------|----------|----------|------|
| Contributor Redundancy | 20 | Low score is risky | Single maintainer dependency |
| Maintainer Retention | 10 | Number of inactive maintainers | Long-inactive maintainers |
| Recent Activity | 20 | Inactivity period | Days since last activity |
| Change Request Resolution | 10 | Slow merge is risky | Average PR merge time |
| Build Health | 5 | CI failure is risky | CI test execution status |
| Funding Signals | 10 | Sponsorship status | Number of funding links |
| Release Rhythm | 10 | Release frequency | Days since last release |
| Security Signals | 15 | Security policy | Security policy, alert status |
| Issue Responsiveness | 5 | Issue response time | Average issue response time |
| **Contributor Attraction** | **10** | **New contributor trend** | **New contributors in last 6 months (Phase 4)** |
| **Contributor Retention** | **10** | **Retention rate** | **Repeat contributors over 6 months (Phase 4)** |
| **Review Health** | **10** | **PR review quality** | **Time to first review & review count (Phase 4)** |

### Metric Models (CHAOSS-aligned)

| Model | Description | Weighted Metrics |
|-------|-------------|------------------|
| Risk Model | Project stability and security | Contributor Redundancy (40%), Security Signals (30%), Change Request Resolution (20%), Issue Responsiveness (10%) |
| Sustainability Model | Long-term viability | Funding Signals (30%), Maintainer Retention (25%), Release Rhythm (25%), Recent Activity (20%) |
| **Community Engagement Model** | **Community health (Phase 4)** | **Contributor Attraction (30%), Contributor Retention (30%), Review Health (25%), Issue Responsiveness (15%)** |

### Risk Levels

```
"Critical" - Critical risk (score < 20%)
"High"     - High risk (score < 40%)
"Medium"   - Medium risk (score < 70%)
"Low"      - Low risk (score < 90%)
"None"     - No risk (score >= 90% or not applicable)
```

## Usage Examples

### Python Package

```json
{
  "ecosystem": "python",
  "package_name": "requests",
  "github_url": "https://github.com/psf/requests",
  "total_score": 85,
  "metrics": [
    {
      "name": "Contributor Redundancy",
      "score": 20,
      "max_score": 20,
      "message": "Healthy: 21 active contributors.",
      "risk": "None"
    },
    ...
  ]
}
```

### JavaScript Package

```json
{
  "ecosystem": "javascript",
  "package_name": "react",
  "github_url": "https://github.com/facebook/react",
  "total_score": 90,
  "metrics": [
    {
      "name": "Contributor Redundancy",
      "score": 20,
      "max_score": 20,
      "message": "Healthy: 20 active contributors.",
      "risk": "None"
    },
    ...
  ]
}
```

### Rust Package

```json
{
  "ecosystem": "rust",
  "package_name": "tokio",
  "github_url": "https://github.com/tokio-rs/tokio",
  "total_score": 96,
  "metrics": [
    {
      "name": "Contributor Redundancy",
      "score": 20,
      "max_score": 20,
      "message": "Healthy: 38 active contributors.",
      "risk": "None"
    },
    ...
  ]
}
```

## Score Ranges

```
0-49:   🔴 Critical   (Critical Risk)
50-79:  🟡 Warning    (Warning)
80-100: 🟢 Excellent  (Excellent)
```

## Migration Guide (v1.0 → v2.0)

### v1.0 Format (Python Only)

```json
{
  "requests": {
    "github_url": "...",
    "total_score": 85,
    "metrics": [...]
  }
}
```

### v2.0 Format (Multi-Language Support)

```json
{
  "python:requests": {
    "ecosystem": "python",
    "package_name": "requests",
    "github_url": "...",
    "total_score": 85,
    "metrics": [...]
  }
}
```

**Update Steps**:

1. Add `ecosystem:` prefix to key names
2. Add `ecosystem` field
3. Add `package_name` field

## Database Generation

### Development Environment

```bash
# Run builder/build_db.py
uv run python builder/build_db.py
```

### Automatic Updates (GitHub Actions)

The database is automatically updated daily at UTC 00:00 via `.github/workflows/update_database.yml`.

## Version History

### v2.0 (Current)

- Multi-language support (Python, JavaScript, Go, Rust, PHP, Java, C#, Ruby)
- Separate files per ecosystem: `data/latest/{language}.json`
- Key format: `{ecosystem}:{package_name}`
- Added `ecosystem` and `package_name` fields
- Runtime computation of `funding_links` and `is_community_driven` in `core.py`

### v1.0 (Initial Release)

- Python packages only
- Single database file
- Flat key structure without ecosystem prefix
