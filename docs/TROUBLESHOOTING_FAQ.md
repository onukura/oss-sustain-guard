# Troubleshooting & FAQ

This section covers common issues and solutions when using OSS Sustain Guard.

## 🔴 Common Errors

### 1. "GitHub token not found" Error

**Error Message:**

```shell
ValueError: GitHub token not found. Set GITHUB_TOKEN environment variable.
```

**When This Happens:** You're analyzing a package not in the cache without providing a GitHub token.

**Solution:**

Option A: Use cached packages (recommended, no token needed):
```bash
oss-guard check requests  # Works instantly if in cache
```

Option B: Set a GitHub token to analyze new packages:
```bash
export GITHUB_TOKEN="your_github_token_here"
oss-guard check new-package  # Analyzes uncached packages
```

**How to Create a GitHub Token:**

1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select `public_repo` scope (read-only, sufficient for analysis)
4. Copy the token and set it: `export GITHUB_TOKEN="your_token"`

### 2. "Package not found" Error

**Error Message:**

```shell
PackageNotFoundError: Package 'my-package' not found in python ecosystem
```

**Cause:** Package name is incorrect or doesn't exist in the registry

**Solution:**

```shell
# Double-check package name (case-sensitive)
oss-guard check requests  # ✅ Correct

# Explicitly specify the ecosystem
oss-guard check python:requests

# Verify on the package registry
# https://pypi.org/project/requests/
```

### 3. "SSL certificate verification failed"

**Error Message:**

```shell
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
```

**Cause:** Firewall or proxy settings prevent SSL certificate verification

**Solution:**

```shell
# Disable SSL verification (development only)
oss-guard check requests --insecure

# Or set environment variable
export OSS_SUSTAIN_GUARD_INSECURE=true
oss-guard check requests

# Warning: Do not use in production
```

### 4. "Rate limit exceeded"

**Error Message:**

```shell
HTTPStatusError: 403 Forbidden - Rate limit exceeded
```

**Cause:** Hit GitHub API rate limit (unauthenticated: 60 req/h, authenticated: 5000 req/h)

**Solution:**

```shell
# Set GitHub token (much higher rate limit)
export GITHUB_TOKEN="your_token"
oss-guard check package1 package2 package3

# Use cache (cached packages don't require API calls)
oss-guard check requests  # Loads from cache, no API call

# Cache default TTL
# Default: 7 days
# Manual reset
oss-guard check --clear-cache
```

## ❓ Frequently Asked Questions

### Q1: Where is the cache stored?

**A:** Default location is `~/.cache/oss-sustain-guard`

```bash
# Change cache directory
oss-guard check requests --cache-dir /path/to/custom/cache

# Clear cache
oss-guard check --clear-cache

# Change cache TTL (seconds)
oss-guard check requests --cache-ttl 2592000  # 30 days
```

### Q2: How is the score calculated?

**A:** Scores vary by scoring profile

| Profile | Use Case |
|---------|----------|
| **balanced** (default) | General health check |
| **security_first** | Prioritize security |
| **contributor_experience** | Prioritize contributor experience |
| **long_term_stability** | Prioritize long-term stability |

```bash
# Switch profiles
oss-guard check requests --profile security_first
```

See [Scoring Profiles Guide](SCORING_PROFILES_GUIDE.md) for details.

### Q3: Can I check packages from multiple languages at once?

**A:** Yes, specify the ecosystem explicitly

```bash
# Mix languages
oss-guard check \
  python:django \
  npm:react \
  rust:tokio \
  go:github.com/golang/go

# Or rely on auto-detection
oss-guard check django react tokio
```

### Q4: How do I exclude specific packages?

**A:** Use `.oss-sustain-guard.toml` or `pyproject.toml`

```toml
# .oss-sustain-guard.toml
[tool.oss-sustain-guard]
exclude = [
    "internal-package",
    "legacy-lib",
    "proprietary-code"
]
```

See [Exclude Configuration Guide](EXCLUDE_PACKAGES_GUIDE.md) for details.

### Q5: How do I pass the GitHub token in GitHub Actions?

**A:** Use `secrets.GITHUB_TOKEN`

```yaml
name: Check Dependencies

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check package sustainability
        uses: onukura/oss-sustain-guard@main
        with:
          packages: 'requests django flask'
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

See [GitHub Actions Guide](GITHUB_ACTIONS_GUIDE.md) for details.

### Q6: How do I scan multiple projects in a monorepo?

**A:** Use the `--recursive` option

```bash
cd monorepo-root
oss-guard check --recursive

# Limit depth
oss-guard check --recursive --depth 2
```

See [Recursive Scanning Guide](RECURSIVE_SCANNING_GUIDE.md) for details.

### Q7: How do I track changes in package health over time?

**A:** Use the trend analysis feature

```bash
# View historical data
oss-guard trend requests

# Compare specific dates
oss-guard compare requests 2025-12-11 2025-12-12

# List available snapshots
oss-guard list-snapshots
```

See [Time Series Analysis Guide](TREND_ANALYSIS_GUIDE.md) for details.

### Q8: What do the metrics mean?

**A:** Each metric is CHAOSS-based

| Metric | Meaning |
|--------|---------|
| **Contributor Redundancy** | Risk of depending on a single maintainer |
| **Recent Activity** | Is the project actively developed? |
| **Release Rhythm** | Release frequency and consistency |
| **Maintainer Retention** | Are maintainers staying with the project? |
| **Issue Responsiveness** | How fast are issues addressed? |
| **Funding Signals** | Does the project have funding options? |

See [CHAOSS Metrics Alignment](CHAOSS_METRICS_ALIGNMENT_VALIDATION.md) for details.

### Q9: What does "Needs attention" mean?

**A:** The project shows signals that it needs support

```shell
🟢 Healthy (80+)     : Good state - continue monitoring
🟡 Monitor (50-79)   : Requires attention - regular checks recommended
🔴 Needs attention   : Support or migration recommended
```

This is an **observation**, not a judgment. Every project has unique circumstances.

### Q10: What is the Gratitude Vending Machine?

**A:** Discovers projects that need support and helps you contribute

```bash
# Show projects that would appreciate support
oss-guard gratitude

# Show top 5
oss-guard gratitude --top 5
```

See [Gratitude Vending Machine](GRATITUDE_VENDING_MACHINE.md) for details.

## 🔍 Debugging Methods

### View Detailed Logs

```bash
# Display detailed metrics
oss-guard check requests --verbose

# Display debug information
export RUST_LOG=debug
oss-guard check requests
```

### Inspect Cache

```bash
# Check cache directory
ls -la ~/.cache/oss-sustain-guard/

# View cache for a specific package
cat ~/.cache/oss-sustain-guard/requests.json
```

### Test API Connectivity

```bash
# Check GitHub API availability
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user

# Run without cache
oss-guard check requests --no-cache
```

## 🚀 Performance Optimization

### If Execution is Slow

```bash
# 1. Enable cache and retry
oss-guard check requests  # Uses cache

# 2. Skip unnecessary details
oss-guard check requests  # Remove --verbose

# 3. Use compact output
oss-guard check requests --compact

# 4. Set GitHub token (improves rate limits)
export GITHUB_TOKEN="your_token"
```

### CI/CD Optimization

```yaml
# Preserve cache
- uses: actions/cache@v3
  with:
    path: ~/.cache/oss-sustain-guard
    key: oss-guard-cache

- name: Check
  run: oss-guard check --recursive --compact
```

## 📚 Learn More

- [Getting Started](GETTING_STARTED.md) - Beginner's guide
- [Recursive Scanning Guide](RECURSIVE_SCANNING_GUIDE.md) - Scan entire projects
- [Time Series Analysis Guide](TREND_ANALYSIS_GUIDE.md) - Track changes
- [GitHub Actions Guide](GITHUB_ACTIONS_GUIDE.md) - CI/CD integration
- [All Documentation](index.md) - Complete documentation

## 🤝 Still Having Issues?

- Report on GitHub Issues: [Issues](https://github.com/onukura/oss-sustain-guard/issues)
- Contributing: [Contributing Guide](GETTING_STARTED.md)
