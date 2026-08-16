# Trend Analysis Guide

Track how repository sustainability scores change over time with OSS Sustain Guard's trend analysis feature.

## Overview

The `trend` command analyzes a repository across multiple time windows to show how its sustainability score has evolved. This helps you identify improving/declining projects, validate migration decisions, and monitor long-term health.

## Quick Start

```bash
# Basic usage - 6 monthly periods (defaults to Python)
os4g trend requests

# With ecosystem prefix
os4g trend python:requests

# Specific ecosystem with options
os4g trend requests -e python --periods 12 --interval weekly --window-days 7

# Direct repository URL
os4g trend https://github.com/psf/requests
```

## Command Syntax

```bash
os4g trend <package-or-url> [OPTIONS]
```

**Package formats:**

- `package-name` - Defaults to Python (e.g., `requests`)
- `ecosystem:package-name` - Explicit ecosystem (e.g., `python:requests`, `javascript:react`)
- `https://github.com/owner/repo` - Direct repository URL

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `-e, --ecosystem` | Package ecosystem | python |
| `-n, --periods` | Number of time periods | 6 |
| `-i, --interval` | Display interval (daily/weekly/monthly/quarterly/annual) | monthly |
| `-w, --window-days` | Days per time window | 30 |
| `-p, --profile` | Scoring profile (balanced, security_first, etc.) | balanced |
| `--profile-file` | Custom scoring profile TOML | None |
| `--scan-depth` | Data sampling depth (shallow/default/deep) | default |
| `--no-cache` | Disable caching | False |
| `-v, --verbose` | Verbose logging | False |

## Examples

### Weekly Trend (Recent Activity)

```bash
os4g trend requests --periods 12 --interval weekly --window-days 7
```

Shows 12 weeks of recent activity with change indicators.

### Quarterly Trend (Long-term View)

```bash
os4g trend flask --periods 8 --interval quarterly --window-days 90
```

Analyze 2 years of history with 90-day periods.

## Understanding the Output

### Score Trend Table

Displays period-by-period scores with change indicators:

```shell
            Score Trend
┏━━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━┓
┃ Period  ┃ Score ┃ Change ┃ Trend ┃
┡━━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━┩
│ 2025-03 │    62 │        │       │
│ 2025-04 │    62 │      0 │   →   │
│ 2025-05 │    72 │    +10 │   ↑   │
│ 2025-06 │    49 │    -23 │   ↓   │
│ 2025-07 │    67 │    +18 │   ↑   │
│ 2025-08 │    71 │     +4 │   ↑   │
│ 2025-09 │    60 │    -11 │   ↓   │
│ 2025-10 │    78 │    +18 │   ↑   │
│ 2025-11 │    52 │    -26 │   ↓   │
│ 2025-12 │    58 │     +6 │   ↑   │
└─────────┴───────┴────────┴───────┘
```

- **↑** Score increased | **↓** Score decreased | **→** Score unchanged

### ASCII Chart

Visual representation of score changes over time:

```shell
57 ┤ ─ ─ ─ ─ ─ ─ ─ ─●─
56 ┤ ─ ─ ─ ─ ─ ─ ─ ─│─│
55 ┤●─ ─ ─ ─ ─ ─ ─ ─│─●
55 ┤ ─│─ ─ ─ ─ ─ ─ ─│─
54 ┤ ─│─ ─ ─ ─ ─ ─●─ ─
54 ┤ ─│─ ─ ─ ─ ─ ─│─ ─
53 ┤ ─●─ ─ ─ ─ ─●─ ─ ─
53 ┤ ─ ─│─ ─ ─ ─│─ ─ ─
52 ┤ ─ ─│─ ─ ─ ─│─ ─ ─
52 ┤ ─ ─●─●─●─●─ ─ ─ ─
```

### Top Metric Changes

Shows metrics with largest changes between first and last period:

```shell
Top Metric Changes:

  Contributor Redundancy: 8 → 0  (-8 ↓)
  Contributor Retention: 10 → 5  (-5 ↓)
  PR Responsiveness: 5 → 0  (-5 ↓)
  Stale Issue Ratio: 5 → 10  (+5 ↑)
  Maintainer Load Distribution: 5 → 10  (+5 ↑)
```

## Time-Dependent Metrics

Trend analysis includes **16 time-dependent metrics** that can be calculated from historical data (commits, PRs, issues, releases) and excludes **8 time-independent metrics** (current state only: vulnerabilities, funding links, documentation, CI status, etc.).

See [Built-in Metrics Guide](BUILT_IN_METRICS_GUIDE.md) for complete metric list and descriptions.

## Best Practices & Limitations

### Choosing Time Windows

- **Active projects**: Use shorter windows (7-30 days) with weekly/monthly intervals
- **Stable/mature projects**: Use longer windows (90-365 days) with quarterly/annual intervals
- **Incident investigation**: Use daily intervals with short windows

### API Limitations

**GitHub**: 5,000 requests/hour (authenticated) | **GitLab**: 2,000 requests/hour

Use `--no-cache` for fresh data, or rely on caching (`--cache-ttl`) to reduce API calls.

### Interpreting Trends

- **Rising scores (↑↑↑)**: New contributors, increased releases, improving response times → healthy dependency
- **Declining scores (↓↓↓)**: Reduced activity, slower response times → consider alternatives
- **Stable scores (→→→)**: Mature/consistent project → depends on absolute score level

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Unexpected score changes** | Check if excluded metrics are included; verify time window alignment; use `--verbose` flag |
| **"Insufficient data" warnings** | Increase `--window-days` for older projects; reduce `--periods` |
| **API rate limit errors** | Reduce `--periods`; enable caching with `--cache-ttl`; or increase window size |
| **All scores identical** | Project may be too young; try longer `--window-days` or fewer `--periods` |

## Next Steps

- **[Getting Started](GETTING_STARTED.md)** - Basic usage and installation
- **[Scoring Profiles Guide](SCORING_PROFILES_GUIDE.md)** - Custom evaluation priorities
- **[Built-in Metrics Guide](BUILT_IN_METRICS_GUIDE.md)** - Metric descriptions and calculations
- **[Troubleshooting FAQ](TROUBLESHOOTING_FAQ.md)** - Common issues and solutions
