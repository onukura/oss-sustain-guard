# Database Schema

## Overview

`data/database.json` is the cache database for OSS Sustain Guard. It stores pre-computed sustainability analysis results, enabling fast lookups without real-time analysis.

## Schema Specification (v2.1 - Multi-Language Support with Cache Metadata)

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
      "name": "Bus Factor",
      "score": integer,
      "max_score": integer,
      "message": "string",
      "risk": "Critical|High|Medium|Low|None"
    },
    ...
  ],
  "cache_metadata": {
    "fetched_at": "ISO 8601 datetime",
    "ttl_seconds": integer,
    "source": "github|local|api"
  }
}
```

## Field Descriptions

### Top-Level

| Field | Type | Description |
|----------|-----|------|
| `ecosystem` | string | Ecosystem name: `python`, `javascript`, `go`, `rust`, `php`, `java`, `csharp`, `ruby` |
| `package_name` | string | Package name within the ecosystem |
| `github_url` | string | GitHub repository URL |
| `total_score` | integer | Total score (0-100) |
| `metrics` | array | Array of individual metrics |
| `cache_metadata` | object | Cache metadata (v2.1+) |

### Cache Metadata (v2.1+)

| Field | Type | Description |
|----------|-----|------|
| `fetched_at` | string | ISO 8601 timestamp when data was fetched |
| `ttl_seconds` | integer | Time-to-live in seconds (default: 604800 = 7 days) |
| `source` | string | Data source: `github` (remote), `local` (fallback), `api` (Libraries.io) |

### Metrics

| Field | Type | Description |
|----------|-----|------|
| `name` | string | Metric name |
| `score` | integer | Score obtained |
| `max_score` | integer | Maximum score |
| `message` | string | Detailed message |
| `risk` | string | Risk level |

## Metrics Reference

### 9 Sustainability Metrics

| Metric | Max Score | Risk Range | Description |
|--------|----------|----------|------|
| Bus Factor | 20 | Low score is risky | Single maintainer dependency |
| Maintainer Drain | 10 | Number of inactive maintainers | Long-inactive maintainers |
| Zombie Check | 20 | Inactivity period | Days since last activity |
| Merge Velocity | 10 | Slow merge is risky | Average PR merge time |
| CI Status | 5 | CI failure is risky | CI test execution status |
| Funding | 10 | Sponsorship status | Number of funding links |
| Release Cadence | 10 | Release frequency | Days since last release |
| Security Posture | 15 | Security policy | Security policy, alert status |
| Community Health | 5 | Issue response time | Average issue response time |

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
      "name": "Bus Factor",
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
      "name": "Bus Factor",
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
      "name": "Bus Factor",
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

### v2.0 (December 2024)

- Multi-language support (Python, JavaScript, Go, Rust)
- Key format change: `package_name` → `ecosystem:package_name`
- Added `ecosystem` field
- Added `package_name` field

### v1.0 (Initial Release)

- Python packages only
