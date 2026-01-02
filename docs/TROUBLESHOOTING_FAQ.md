# Troubleshooting & FAQ

This section covers common issues and solutions when using OSS Sustain Guard.

## 🔴 Common Errors

### 1. "GITHUB_TOKEN environment variable is required" Error

**Error Message:**

```shell
ValueError: GITHUB_TOKEN environment variable is required.

To get started:
1. Create a GitHub Personal Access Token (classic):
   → https://github.com/settings/tokens/new
2. Select scopes: 'public_repo' and 'security_events'
3. Set the token:
   export GITHUB_TOKEN='your_token_here'  # Linux/macOS
   or add to your .env file: GITHUB_TOKEN=your_token_here
```

**When This Happens:** Every time you run `os4g check` without a GitHub token set.

**Solution:**

OSS Sustain Guard requires a GitHub token for all analyses:

```bash
# Create token at: https://github.com/settings/tokens/new
export GITHUB_TOKEN="your_github_token_here"
os4g check requests  # Now works
```

**How to Create a GitHub Token:**

1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens/new)
2. Click "Generate new token (classic)"
3. Token name: `oss-sustain-guard` (or any name you prefer)
4. Select `public_repo` and `security_events` scopes (read-only access to public repositories)
5. Click "Generate token" and **copy it immediately** (you won't see it again)
6. Set the environment variable:

   ```bash
   export GITHUB_TOKEN="your_token"  # Linux/macOS
   ```

   Or add to `.env` file in your project:

   ```shell
   GITHUB_TOKEN=your_token_here
   ```

**Why Required:** GitHub's API requires authentication to query repository data (contributors, releases, issues, funding, etc.).

### 2. "Package not found" Error

**Error Message:**

```shell
PackageNotFoundError: Package 'my-package' not found in python ecosystem
```

**Cause:** Package name is incorrect or doesn't exist in the registry

**Solution:**

```shell
# Double-check package name (case-sensitive)
os4g check requests  # ✅ Correct

# Explicitly specify the ecosystem
os4g check python:requests
os4g check r:ggplot2
os4g check haskell:text
os4g check swift:apple/swift-nio
os4g check dart:http
os4g check elixir:phoenix
os4g check perl:Mojolicious

# Verify on the package registry
# https://pypi.org/project/requests/
```

### 3. "SSL certificate verification failed"

**Error Message:**

```shell
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
```

**Cause:** Firewall or proxy settings prevent SSL certificate verification, or system CA certificates are outdated

**Solution:**

**Recommended: Fix certificate configuration properly**

```shell
# Update system CA certificates (Ubuntu/Debian)
sudo apt update && sudo apt install --reinstall ca-certificates

# Or update certificates (Red Hat/CentOS)
sudo yum reinstall ca-certificates

# If using a corporate proxy that inspects SSL traffic (e.g., Zscaler):
# 1. Obtain the proxy's CA certificate from your IT department
# 2. Add it to system trust store (example for Ubuntu)
sudo cp proxy-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates

# Or specify custom CA certificate file directly
os4g check requests --ca-cert /path/to/custom-ca.crt

# Or set environment variable (affects all commands)
export OSS_SUSTAIN_GUARD_CA_CERT=/path/to/custom-ca.crt
os4g check requests

# For corporate proxies with multiple certificates, use system trust store instead:
# Add all required certificates to /usr/local/share/ca-certificates/ and run:
sudo update-ca-certificates
os4g check requests  # Will use system trust store
```

**Temporary workaround (development only):**

```shell
# Disable SSL verification (NOT recommended for production)
os4g check requests --insecure

# Or set environment variable
export OSS_SUSTAIN_GUARD_INSECURE=true
os4g check requests
```

**Warning:** Avoid `--insecure` in production as it disables all SSL verification, making connections vulnerable to man-in-the-middle attacks.

### 4. "Rate limit exceeded"

**Error Message:**

```shell
HTTPStatusError: 403 Forbidden - Rate limit exceeded
```

**Cause:** Hit GitHub API rate limit (unauthenticated: 60 req/h, authenticated: 5000 req/h)

**Solution:**

```shell
# Set GitHub token (required)
export GITHUB_TOKEN="your_token"
os4g check package1 package2 package3

# Use cache (cached packages don't require API calls)
os4g check requests  # Loads from cache, no API call

# Cache default TTL
# Default: 7 days
# Manual reset
os4g check --clear-cache
```

## ❓ Frequently Asked Questions

### Q1: Where is the cache stored?

**A:** Default location is `~/.cache/oss-sustain-guard`

```bash
# Change cache directory
os4g check requests --cache-dir /path/to/custom/cache

# Clear cache
os4g check --clear-cache

# Change cache TTL (seconds)
os4g check requests --cache-ttl 2592000  # 30 days
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
os4g check requests --profile security_first
```

See [Scoring Profiles Guide](SCORING_PROFILES_GUIDE.md) for details.

### Q3: Can I check packages from multiple languages at once?

**A:** Yes, specify the ecosystem explicitly

```bash
# Mix languages
os4g check \
  python:django \
  npm:react \
  rust:tokio \
  go:github.com/golang/go

# Or rely on auto-detection
os4g check django react tokio
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
os4g check --recursive

# Limit depth
os4g check --recursive --depth 2
```

See [Recursive Scanning Guide](RECURSIVE_SCANNING_GUIDE.md) for details.

### Q7: What do the metrics mean?

**A:** Each metric is CHAOSS-based

| Metric | Meaning |
|--------|---------|
| **Contributor Redundancy** | Concentration of contributions (single-maintainer signal) |
| **Recent Activity** | Is the project actively developed? |
| **Release Rhythm** | Release frequency and consistency |
| **Maintainer Retention** | Are maintainers staying with the project? |
| **Community Health** | How fast are issues addressed? |
| **Funding Signals** | Does the project have funding options? |

See [CHAOSS Metrics Alignment](CHAOSS_METRICS_ALIGNMENT_VALIDATION.md) for details.

### Q8: What does "Needs support" mean?

**A:** The project shows signals that it needs support

```shell
🟢 Healthy (80+)     : Good state - continue monitoring
🟡 Monitor (50-79)   : Requires attention - regular checks recommended
🔴 Needs support     : Support or migration recommended
```

This is an **observation**, not a judgment. Every project has unique circumstances.

### Q9: What is the Gratitude Vending Machine?

**A:** Discovers projects that need support and helps you contribute

```bash
# Show projects that would appreciate support
os4g gratitude

# Show top 5
os4g gratitude --top 5
```

See [Gratitude Vending Machine](GRATITUDE_VENDING_MACHINE.md) for details.

## 🔍 Debugging Methods

### View Detailed Logs

```bash
# Display detailed metrics
os4g check requests -v

# Display debug information
export RUST_LOG=debug
os4g check requests
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
os4g check requests --no-cache
```

## 🚀 Performance Optimization

### If Execution is Slow

```bash
# 1. Enable cache and retry
os4g check requests  # Uses cache

# 2. Skip verbose logging
os4g check requests  # Remove -v flag

# 3. Use compact output
os4g check requests -o compact

# 4. Set GitHub token (required)
export GITHUB_TOKEN="your_token"
```

### CI/CD Optimization

```yaml
# Preserve cache
- uses: actions/cache@v3
  with:
    path: ~/.cache/oss-sustain-guard
    key: os4g-cache

- name: Check
  run: os4g check --recursive --compact
```

## ❓ Frequently Asked Questions

### "Package X is on GitLab/Gitea but wasn't analyzed—why?"

**Answer:** OSS Sustain Guard currently supports **GitHub-hosted repositories only** for real-time analysis.

When a package's source is detected on another platform (GitLab, Gitea, SourceForge, etc.), the tool will:

1. **Detect the non-GitHub host** during package resolution
2. **Display a note** like: "Repository is hosted on GitLab. Real-time analysis currently supports GitHub only."
3. **Skip analysis** for that package (no data is sent to external services)

**Why only GitHub?**
- GitHub's GraphQL API provides deep repository metrics (contributors, activity timeline, PR review patterns, etc.)
- Other platforms have different APIs with varying data availability and rate limits
- We want to maintain consistent metric quality across all analyzed packages

**When will GitLab/other platforms be supported?**
- Support for GitLab, Gitea, and other platforms is under consideration for future releases
- The team is exploring API integration possibilities with other major platforms
- Check [GitHub Issues](https://github.com/onukura/oss-sustain-guard/issues) for progress and feature requests

**Workaround:** If you need to analyze GitLab projects, consider opening an issue or contributing: [Contributing Guide](../CONTRIBUTING.md)

### "Why is my analysis incomplete with 'Note: Unable to access this data'?"

**Common causes:**

| Message | Cause | Solution |
|---------|-------|----------|
| "may require elevated token permissions" | Token lacks required scopes | Recreate token with `public_repo` + `security_events` |
| "GitHub API rate limit reached" | Too many requests in short time | Wait 1 hour or use `--use-cache` for repeated runs |
| "Network timeout" | Connectivity issue | Check your internet connection and try again |
| "Unable to parse response" | API returned unexpected format | Usually temporary; try again in a few minutes |

**Debugging:**

```bash
# Check your token validity
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user

# Verbose output for detailed error info
os4g check requests -v

# Force fresh analysis (skip cache)
os4g check requests --no-cache
```

## 📚 Learn More

- [Getting Started](GETTING_STARTED.md) - Beginner's guide
- [Recursive Scanning Guide](RECURSIVE_SCANNING_GUIDE.md) - Scan entire projects
- [GitHub Actions Guide](GITHUB_ACTIONS_GUIDE.md) - CI/CD integration
- [All Documentation](index.md) - Complete documentation

## 🤝 Still Having Issues?

- Report on GitHub Issues: [Issues](https://github.com/onukura/oss-sustain-guard/issues)
- Contributing: [Contributing Guide](GETTING_STARTED.md)
