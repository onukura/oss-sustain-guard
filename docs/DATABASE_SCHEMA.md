# Database Schema

## Overview

**Note**: As of v2.1+, package data is stored in **Cloudflare KV** for fast, distributed access worldwide. The data is no longer primarily served from git repository files.

### Data Storage Architecture

| Storage | Purpose | Access |
|---------|---------|--------|
| **Cloudflare KV** | Primary shared cache for all users | Public read, authenticated write |
| **Local cache** (`~/.cache/oss-sustain-guard/`) | User-specific cache | Read/write |
| **`data/` (build artifacts)** | Build-time temporary files (not committed to git) | CI/CD only |

### Key Format

Cloudflare KV uses content-addressable keys:
```
{schema_version}:{ecosystem}:{package_name}
```

Examples:
- `2.0:python:requests`
- `2.0:javascript:react`
- `2.0:rust:tokio`

### Data Loading Priority

1. **Local cache** - Fastest, user-specific
2. **Cloudflare KV** - Fast, globally distributed shared cache
3. **Real-time analysis** - Slowest, used when cache misses

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

**Note**: The database stores metrics and models. Scores are calculated at runtime based on the user's selected scoring profile.

## Field Descriptions

### Top-Level

| Field | Type | Description |
|----------|-----|------|
| `ecosystem` | string | Ecosystem name: `python`, `javascript`, `go`, `rust`, `php`, `java`, `csharp`, `ruby` |
| `package_name` | string | Package name within the ecosystem |
| `github_url` | string | GitHub repository URL |
| `metrics` | array | Array of individual metrics (raw data for runtime scoring) |
| `models` | array | Array of metric models (CHAOSS-aligned aggregations) |
| `signals` | object | Raw signal values for transparency |

### Runtime Fields (Computed When Needed)

The following fields are computed at runtime based on the user's selected scoring profile:

| Field | Type | When Computed | Description |
|----------|-------|--------------|------|
| `total_score` | integer | CLI/API call | Calculated from metrics using the selected scoring profile |
| `funding_links` | array | CLI/API call | Extracted from GitHub repository data |
| `is_community_driven` | boolean | CLI/API call | Determined by ownership structure |

**Important**: `total_score` is profile-dependent and not stored in the database. It is always calculated at runtime based on:

- Selected scoring profile (`balanced`, `security_first`, `contributor_experience`, `long_term_stability`)
- Available metrics in the database
- Category weights from the selected profile

This ensures the same raw metric data can produce different scores for different risk assessment priorities.

### Metrics

| Field | Type | Description |
|----------|-----|------|
| `name` | string | Metric name (see [Metrics Reference](#metrics-reference)) |
| `score` | integer | Score obtained |
| `max_score` | integer | Maximum score |
| `message` | string | Detailed message |
| `risk` | string | Risk level: `Critical`, `High`, `Medium`, `Low`, `None` |

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
| `new_contributors_6mo` | integer | New contributors in last 6 months |
| `contributor_retention_rate` | integer | Contributor retention rate percentage |
| `avg_review_time_hours` | float | Average time to first PR review in hours |
| `organizational_diversity_count` | integer | Number of different organizations/domains |
| `star_count` | integer | GitHub star count |
| `fork_count` | integer | GitHub fork count |
| `watcher_count` | integer | GitHub watcher count |
| `pr_acceptance_rate` | float | Pull request acceptance ratio (0-100) |
| `avg_issue_resolution_days` | float | Average issue resolution time in days |
| `has_documentation` | boolean | Whether documentation is present |
| `has_code_of_conduct` | boolean | Whether Code of Conduct is present |
| `license_type` | string | License SPDX ID (e.g., "MIT", "Apache-2.0") |
| _(extensible)_ | any | Additional raw signals as needed |

## Metrics Reference

### 21 Sustainability Metrics (Complete System)

#### Category: Maintainer Health (25% of total score)

| Metric | Max Score | Risk Range | Description |
|--------|----------|----------|------|
| Contributor Redundancy | 20 | Low score is risky | Single maintainer dependency risk |
| Maintainer Retention | 10 | Number of inactive maintainers | Active maintainer continuity |
| Contributor Attraction | 10 | New contributor trend | New contributors in last 6 months |
| Contributor Retention | 10 | Retention rate | Repeat contributors over 6 months |
| Organizational Diversity | 10 | Single-org dominance | Multi-organization contribution diversity |

#### Category: Development Activity (20% of total score)

| Metric | Max Score | Risk Range | Description |
|--------|----------|----------|------|
| Recent Activity | 20 | Inactivity period | Days since last activity |
| Release Rhythm | 10 | Release frequency | Days since last release |
| Build Health | 5 | CI failure is risky | CI test execution status |
| Change Request Resolution | 10 | Slow merge is risky | Average PR merge time |

#### Category: Community Engagement (20% of total score)

| Metric | Max Score | Risk Range | Description |
|--------|----------|----------|------|
| Issue Responsiveness | 5 | Issue response time | Average issue response time |
| PR Acceptance Ratio | 10 | Low acceptance rate | Pull request acceptance rate |
| PR Responsiveness | 5 | Slow first response | Time to first PR response |
| Review Health | 10 | PR review quality | Time to first review & review count |
| Issue Resolution Duration | 10 | Slow issue closure | Average time to close issues |

#### Category: Project Maturity (15% of total score)

| Metric | Max Score | Risk Range | Description |
|--------|----------|----------|------|
| Documentation Presence | 10 | Missing docs | README, CONTRIBUTING, Wiki, documentation |
| Code of Conduct | 5 | No CoC | Community guidelines presence |
| License Clarity | 5 | No/unclear license | OSI-approved license status |
| Project Popularity | 10 | Low community interest | Stars, watchers, community adoption |
| Fork Activity | 5 | No forks | Fork count and recent fork activity |

#### Category: Security & Funding (20% of total score)

| Metric | Max Score | Risk Range | Description |
|--------|----------|----------|------|
| Security Signals | 15 | Security policy | Security policy, vulnerability alerts |
| Funding Signals | 10 (community) / 5 (corporate) | Sponsorship status | Number and type of funding links |

### Metric Models (CHAOSS-aligned)

| Model | Description | Weighted Metrics |
|-------|-------------|------------------|
| Risk Model | Project stability and security | Contributor Redundancy (40%), Security Signals (30%), Change Request Resolution (20%), Issue Responsiveness (10%) |
| Sustainability Model | Long-term viability | Funding Signals (30%), Maintainer Retention (25%), Release Rhythm (25%), Recent Activity (20%) |
| Community Engagement Model | Community health and responsiveness | Contributor Attraction (30%), Contributor Retention (30%), Review Health (25%), Issue Responsiveness (15%) |
| **Project Maturity Model** | **Documentation and governance** | **Documentation Presence (30%), Project Popularity (20%), License Clarity (20%), Code of Conduct (15%), Fork Activity (15%)** |
| **Contributor Experience Model** | **PR handling and satisfaction** | **PR Acceptance Ratio (30%), PR Responsiveness (25%), Issue Resolution Duration (25%), Review Health (20%)** |

### Scoring System

The total score (0-100) is calculated using **category-weighted aggregation**:

1. Each category's metrics are normalized to 0-100 scale
2. Category scores are weighted:
   - Maintainer Health: 25%
   - Development Activity: 20%
   - Community Engagement: 20%
   - Project Maturity: 15%
   - Security & Funding: 20%
3. Final score = sum of (category_score × category_weight)

### Risk Levels

```text
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

```text
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

The database is automatically updated daily at UTC 00:00 via `.github/workflows/update_database.yml`. The workflow:

1. Fetches the latest packages from each ecosystem (Libraries.io)
2. Analyzes them using GitHub GraphQL API
3. **Uploads directly to Cloudflare KV** (globally distributed cache)
4. Stores build artifacts locally (not committed to git)

This ensures all users get fresh data from the global cache without needing GitHub access.

## Version History

### v2.0 (Current)

- Multi-language support (Python, JavaScript, Go, Rust, PHP, Java, C#, Ruby)
- Cloudflare KV-based data distribution (v2.1+)
- Key format: `{schema_version}:{ecosystem}:{package_name}` (e.g., `2.0:python:requests`)
- Added `ecosystem` and `package_name` fields
- Runtime computation of `funding_links` and `is_community_driven` in `core.py`

### v1.0 (Initial Release)

- Python packages only
- Single database file
- Flat key structure without ecosystem prefix
