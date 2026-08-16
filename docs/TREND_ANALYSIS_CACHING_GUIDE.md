# Trend Analysis Caching Guide

## Overview

OSS Sustain Guard's trend analysis feature now includes sophisticated caching mechanisms to optimize performance and minimize API calls. Time window VCS data is cached separately from regular package analysis, enabling efficient incremental analysis and reuse across multiple trend analyses with different profiles.

## How Trend Caching Works

### Cache Architecture

Trend data is cached per time window in a dedicated cache subdirectory structure:

```shell
~/.cache/oss-sustain-guard/
├── trends/
│   ├── github/
│   │   ├── owner_repo.json.gz
│   │   └── ...
│   ├── gitlab/
│   │   └── owner_repo.json.gz
│   └── ...
└── python.json.gz  (regular package analysis cache)
```

Each time window for a repository is cached independently as a single gzipped JSON file.

### Time Window Cache Key

The cache uses a composite key combining start and end timestamps:

```shell
since::until
e.g., "2025-01-01T00:00:00+00:00::2025-02-01T00:00:00+00:00"
```

This allows multiple time windows for the same repository to be cached efficiently without conflicts.

### Cache Metadata

Each cached entry includes TTL information:

```json
{
  "2025-01-01T00:00:00+00:00::2025-02-01T00:00:00+00:00": {
    "vcs_data": { ... },
    "cache_metadata": {
      "fetched_at": "2025-01-06T10:30:00+00:00",
      "ttl_seconds": 604800,
      "since": "2025-01-01T00:00:00+00:00",
      "until": "2025-02-01T00:00:00+00:00"
    }
  }
}
```

## Performance Benefits

### Cache Hit Scenarios

When you run trend analysis multiple times for the same repository:

**First run (6 months of data):**

```bash
os4g trend python:requests --periods 6 --interval monthly
# Makes 6 API calls (one per window)
# Cache: 0 hits, 6 API calls
```

**Second run (same parameters):**

```bash
os4g trend python:requests --periods 6 --interval monthly
# Uses cached data from all 6 windows
# Cache: 6 hits, 0 API calls
```

**Different profile, same repository:**

```bash
os4g trend python:requests --periods 6 --interval monthly --profile security_first
# Uses cached VCS data from all 6 windows
# Re-calculates metrics with new profile weights
# Cache: 6 hits, 0 API calls
```

### API Rate Limit Benefits

Each VCS API call typically costs multiple API credits. With caching enabled:

- **Without caching:** 6 periods × multiple API calls = high rate limit consumption
- **With caching:** First analysis costs full amount, subsequent analyses are nearly free

## Usage

### Enable Caching (Default)

Caching is enabled by default:

```bash
os4g trend requests
```

### Disable Caching

Force real-time analysis without using cache:

```bash
os4g trend requests --no-cache
```

### View Cache Statistics

When using `--verbose` with caching enabled, cache statistics are displayed:

```bash
os4g trend requests --verbose
# Output includes:
# 💾 Cache: 4 windows from cache, 2 fresh API calls
```

### Clear Trend Cache

Clear all cached trend data:

```bash
# Clear all trend cache
os4g cache clear --trend-only

# Or use the cache module functions
python -c "from oss_sustain_guard.cache import clear_trend_cache; clear_trend_cache()"
```

Clear for a specific repository:

```python
from oss_sustain_guard.cache import clear_trend_cache

# Clear all windows for psf/requests
clear_trend_cache(owner="psf", repo="requests")

# Clear all repos by psf (across all VCS platforms)
clear_trend_cache(owner="psf")

# Clear all trend cache for GitHub
clear_trend_cache(vcs_platform="github")
```

## Configuration

### Cache TTL

The default cache TTL is 7 days (604800 seconds). Configure it globally:

```bash
os4g trend requests --cache-ttl 1209600  # 14 days

# Or in config file:
# [cache]
# ttl_seconds = 1209600
```

### Cache Directory

Default: `~/.cache/oss-sustain-guard`

Override:

```bash
os4g trend requests --cache-dir /custom/cache/path
```

## Implementation Details

### Key Functions

**Cache Storage:**

```python
from oss_sustain_guard.cache import save_trend_vcs_data

save_trend_vcs_data(
    owner="psf",
    repo="requests",
    since="2025-01-01T00:00:00+00:00",
    until="2025-02-01T00:00:00+00:00",
    vcs_data={...},
    vcs_platform="github"
)
```

**Cache Retrieval:**

```python
from oss_sustain_guard.cache import load_trend_vcs_data

data = load_trend_vcs_data(
    owner="psf",
    repo="requests",
    since="2025-01-01T00:00:00+00:00",
    until="2025-02-01T00:00:00+00:00",
    vcs_platform="github"
)
```

**Trend Analysis with Caching:**

```python
from oss_sustain_guard.trend import analyze_repository_trend

result = await analyze_repository_trend(
    owner="psf",
    name="requests",
    interval=TrendInterval.MONTHLY,
    periods=6,
    window_days=30,
    profile="balanced",
    vcs_platform="github",
    scan_depth="default",
    use_cache=True  # Enable caching
)
```

**Cache Statistics:**

```python
from oss_sustain_guard.trend import get_trend_cache_stats

stats = get_trend_cache_stats()
# {'cached': 4, 'api': 2}

print(f"Cached: {stats['cached']}, Fresh API: {stats['api']}")
```

### Cache Invalidation

Cache entries are automatically invalidated when:

1. **TTL Expires:** Default 7 days after fetch
2. **Manual Clear:** `clear_trend_cache()` function
3. **Analysis Version Changes:** If trend analysis logic changes significantly

## Best Practices

### For CI/CD Pipelines

```bash
# First run: builds cache for future runs
os4g trend python:requests --periods 6 --output-format json

# Subsequent runs: much faster (cache hits)
os4g trend python:requests --periods 6 --output-format json
```

### For Multiple Repositories

```bash
# Analyze multiple repos - later runs benefit from cached data
os4g check requests django flask

# Or with trend:
for repo in requests django flask; do
  os4g trend python:$repo --periods 3
done
```

### For Development

```bash
# Disable cache during development for real-time data
os4g trend requests --no-cache --verbose

# Re-enable for testing performance
os4g trend requests --verbose
```

## Troubleshooting

### Cache Not Working

Check if caching is enabled:

```bash
os4g trend requests --verbose
# Should see "Cache: enabled"
```

Verify cache directory exists:

```bash
ls -la ~/.cache/oss-sustain-guard/trends/
```

### Stale Cache

Clear cache for specific repository:

```bash
python -c "from oss_sustain_guard.cache import clear_trend_cache; clear_trend_cache(owner='psf', repo='requests')"
```

Reduce TTL for faster refresh:

```bash
os4g trend requests --cache-ttl 3600  # 1 hour
```

### High Disk Usage

Monitor cache size:

```bash
du -sh ~/.cache/oss-sustain-guard/trends/
```

Clear old caches:

```bash
# Clear all trend cache
python -c "from oss_sustain_guard.cache import clear_trend_cache; clear_trend_cache()"
```

## Maintenance Notes

- **Cache files are gzip-compressed** to minimize disk usage
- **Filesystem names are sanitized** to handle special characters in owner/repo names
- **Cache is per-VCS-platform** to support multi-platform analyses
- **TTL is checked on load** to ensure data freshness

## See Also

- [TREND_ANALYSIS_GUIDE.md](TREND_ANALYSIS_GUIDE.md) - Trend analysis overview
- [CACHING_GUIDE.md](CACHING_GUIDE.md) - General caching configuration
