# Caching Guide

OSS Sustain Guard uses intelligent local caching to minimize API calls to GitHub and package registries, reducing analysis time and respecting API rate limits.

## Overview

The tool caches analysis results locally to avoid redundant API calls. This means:

- **Faster Analysis**: Subsequent checks of the same packages are nearly instant
- **Rate Limit Friendly**: Fewer API calls means you stay well within rate limits
- **Offline Support**: Use cached results without internet (for previously analyzed packages)

## Cache Location

Cache is stored in your user's cache directory:

```bash
# Linux/macOS
~/.cache/oss-sustain-guard/

# Windows
%APPDATA%\oss-sustain-guard\
```

Each ecosystem (Python, JavaScript, Rust, etc.) has its own gzip-compressed JSON file:

```
~/.cache/oss-sustain-guard/
  python.json.gz          # Python (PyPI) cache
  javascript.json.gz      # JavaScript (npm) cache
  rust.json.gz            # Rust (Cargo) cache
  java.json.gz            # Java (Maven) cache
  ... (other ecosystems)
```

## Cache Validity & TTL

Each cached entry includes metadata about when it was cached. The cache is automatically updated when:

- The entry is older than its TTL (time-to-live)
- Analysis version changes (indicating metric changes)
- The `--no-cache` flag is used

### Automatic Cache Invalidation

The tool automatically invalidates old cache when:

1. **Metric changes detected**: When `ANALYSIS_VERSION` increments (new metrics, scoring changes, etc.), all cached data is regenerated
2. **TTL expires**: Entries older than their TTL are refreshed
3. **Manual bypass**: Using `--no-cache` flag

## Using Cache

### Default: Use Cache (Recommended)

```bash
# Uses cache when available, fetches fresh data if needed
os4g check requests
os4g check --include-lock
```

### Bypass Cache (Force Fresh Analysis)

```bash
# Always fetch fresh data from GitHub, ignore cache
os4g check requests --no-cache

# Apply to multiple packages
os4g check --include-lock --no-cache
```

## Cache Management

### View Cache Statistics

```bash
# Display overall cache statistics
os4g cache stats

# Show statistics for a specific ecosystem
os4g cache stats python
os4g cache stats javascript
```

Output shows:
- Total entries cached
- Valid vs expired entries
- Per-ecosystem breakdown

### List Cached Packages

```bash
# List all cached packages (top 100 by default)
os4g cache list

# List packages from a specific ecosystem
os4g cache list python
os4g cache list javascript

# Show all cached packages (including expired)
os4g cache list --all

# Sort by different criteria
os4g cache list --sort name          # Sort by package name
os4g cache list --sort date          # Sort by cache date
os4g cache list --sort ecosystem     # Sort by ecosystem then score

# Filter packages by keyword
os4g cache list --filter requests     # Find packages with "requests" in the name
os4g cache list --filter github.com   # Find packages from a specific URL

# Limit results
os4g cache list --limit 50           # Show top 50 packages
os4g cache list --limit 0            # Show all packages (unlimited)

# Use different scoring profile for recalculation
os4g cache list --profile security_first
```

### Clear Cache

```bash
# Clear all caches
os4g cache clear

# Clear specific ecosystem
os4g cache clear python
os4g cache clear javascript

# Remove only expired entries (keep valid ones)
os4g cache clear --expired-only
os4g cache clear python --expired-only

# Manual removal (filesystem)
rm -rf ~/.cache/oss-sustain-guard/  # Linux/macOS
rmdir /s %APPDATA%\oss-sustain-guard  # Windows PowerShell

# Clear specific ecosystem (filesystem)
rm ~/.cache/oss-sustain-guard/python.json.gz  # Python only
```

## Cache and CI/CD

When using OSS Sustain Guard in CI/CD pipelines, consider:

### Option 1: Use Fresh Data (Recommended for CI)

```bash
# GitHub Actions example
- name: Analyze dependencies
  run: os4g check --include-lock --no-cache
```

Always using fresh data ensures consistency across CI runs.

### Option 2: Persist Cache (For Performance)

```yaml
# GitHub Actions example with cache persistence
- name: Restore cache
  uses: actions/cache@v3
  with:
    path: ~/.cache/oss-sustain-guard
    key: oss-sustain-guard-cache

- name: Analyze dependencies
  run: os4g check --include-lock
```

This improves performance for repeated CI runs while still fetching updates when TTL expires.

## Verbose Logging

Enable verbose output to see cache operations:

```bash
# Shows cache hits, misses, and metric reconstruction
os4g check requests -v

# Combine with output style
os4g check requests -v -o detail
```

Output will show:
- Whether results came from cache or fresh analysis
- Cache file paths and operations
- TTL and validity information

## Troubleshooting

### Cache Returns Old Data

**Issue**: Results seem outdated

**Solution**: Clear cache and re-analyze:

```bash
rm ~/.cache/oss-sustain-guard/python.json.gz
os4g check requests
```

### Cache Corrupted

**Issue**: Error reading cache or invalid data

**Solution**: Clear all caches:

```bash
rm -rf ~/.cache/oss-sustain-guard/
```

The tool will recreate cache on next run.

### Cache File Too Large

**Issue**: Cache directory taking up significant disk space

**Solution**: Cache is automatically managed and compresses efficiently. If needed:

```bash
# View cache size
du -sh ~/.cache/oss-sustain-guard/

# Clear old caches (individual ecosystems)
rm ~/.cache/oss-sustain-guard/javascript.json.gz  # Remove specific ecosystem
```

## Best Practices

1. **Local Development**: Use cache for faster iteration during development
2. **CI/CD**: Use `--no-cache` for consistency, or combine with cache persistence for performance
3. **Cache Clearing**: Clear cache if you suspect stale data or after major metric changes
4. **Monitoring**: Use verbose mode (`-v`) to understand cache behavior
5. **Regular Updates**: Let cache TTL work naturally; don't manually clear unless needed

## How Caching Works Internally

When you run `os4g check`:

1. **Check if package is in cache** → If cached and not expired, use cached result
2. **Fetch fresh data** → If not cached or expired, query GitHub and registries
3. **Save to cache** → Store result with TTL metadata
4. **Display results** → Show analysis to user

This process ensures you get accurate data while minimizing API calls.

## Environment Variable Override

For advanced users, you can override the cache directory:

```bash
# Linux/macOS
export XDG_CACHE_HOME=/custom/cache/path
os4g check requests

# Windows PowerShell
$env:XDG_CACHE_HOME="C:\Custom\Cache"
os4g check requests
```

The tool will use `$XDG_CACHE_HOME/oss-sustain-guard/` as the cache directory.
