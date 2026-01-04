# Scan Depth and Time Window Configuration

OSS Sustain Guard provides flexible data sampling controls to balance analysis depth, speed, and API usage.

## Scan Depth Options

Control how much data is collected from GitHub/GitLab APIs with the `--scan-depth` option:

### Shallow (`--scan-depth shallow`)

Quick scan with minimal data collection (~50% of default samples).

**Use when:**

- Quick health checks
- CI/CD pipelines with strict time limits
- Rate limit concerns
- Large number of packages to analyze

**Sample sizes:**

- Commits: 50
- Merged PRs: 20
- Closed PRs: 20
- Open Issues: 10
- Closed Issues: 20
- Releases: 5
- Reviews: 3

**Example:**

```bash
os4g check --scan-depth shallow
os4g check django flask --scan-depth shallow
```

### Default (`--scan-depth default`)

Balanced sampling for typical analysis (default behavior).

**Use when:**

- Standard dependency audits
- General sustainability evaluation
- Most use cases

**Sample sizes:**

- Commits: 100
- Merged PRs: 50
- Closed PRs: 50
- Open Issues: 20
- Closed Issues: 50
- Releases: 10
- Reviews: 10

**Example:**

```bash
os4g check  # default depth is used
os4g check --scan-depth default  # explicit
```

### Deep (`--scan-depth deep`)

Comprehensive analysis with maximum data collection (~2x default samples).

**Use when:**

- Detailed investigation of specific projects
- Critical dependency evaluation
- Research and in-depth analysis
- You have generous API rate limits

**Sample sizes (API limits: 100 per query):**

- Commits: 100
- Merged PRs/MRs: 100
- Closed PRs/MRs: 100
- Open Issues: 50
- Closed Issues: 100
- Releases: 20
- Reviews: 20

**Example:**

```bash
os4g check requests --scan-depth deep
os4g check --recursive --scan-depth deep
```

### Very Deep (`--scan-depth very_deep`)

Maximum detail analysis with highest sample counts for all data types.

**Use when:**

- Critical security audits
- Extensive research projects
- Maximum data collection needed
- Comprehensive historical analysis
- API rate limits are not a concern

**Sample sizes (API limits: 100 per query):**

- Commits: 100
- Merged PRs/MRs: 100
- Closed PRs/MRs: 100
- Open Issues: 100
- Closed Issues: 100
- Releases: 50
- Vulnerability Alerts: 50 (GitHub only)
- Forks: 100
- Reviews: 50

**Differences from Deep:**

- 2x more open issues (50 → 100)
- 2.5x more releases (20 → 50)
- 2.5x more vulnerability alerts (20 → 50, GitHub only)
- 2x more forks (50 → 100)
- 2.5x more reviews (20 → 50)

**Example:**

```bash
os4g check critical-dependency --scan-depth very_deep
os4g check --scan-depth very_deep --days-lookback 180
```

**Note:** Both GitHub GraphQL API and GitLab REST API limit to 100 records per query for most data types. Very deep mode maximizes data collection for all fields while respecting these constraints.

## Time Window Filtering

Limit analysis to recent activity with the `--days-lookback` option.

### Usage

```bash
# Analyze only the last 30 days
os4g check --days-lookback 30

# Last 3 months (90 days)
os4g check --days-lookback 90

# Last 6 months (180 days)
os4g check --days-lookback 180

# Last year (365 days)
os4g check --days-lookback 365
```

### When to Use Time Filtering

**Short windows (30-90 days):**

- Focus on recent project activity
- Evaluate current maintainer responsiveness
- Check if a project is actively maintained
- Fast-moving projects where older data is less relevant

**Medium windows (90-180 days):**

- Seasonal projects
- Balanced view of recent trends
- Most general-purpose analyses

**Long windows (180-365 days):**

- Projects with slower release cycles
- Academic or research projects
- Comprehensive historical analysis

**No time limit (default):**

- Full project history within sample limits
- Best for comprehensive evaluation
- Recommended for most analyses

### How Time Filtering Works

When you specify `--days-lookback N`:

1. **API-level filtering** - GitHub/GitLab APIs receive 'since' parameter to fetch only recent data
2. **Data is collected** according to scan depth (shallow/default/deep/very_deep) within the time window
3. **Metrics calculated** based on the time-filtered data

**Example:** With `--scan-depth deep --days-lookback 90`:

- API fetches commits from the last 90 days only (API-level filtering)
- Up to 100 commits within that period (deep mode limit)
- Calculate metrics based on the 90-day window

**Benefits of API-level filtering:**

- More efficient: Only relevant data is fetched
- Better accuracy: True representation of time window activity
- No missed data: Not limited by scan depth for recent activity

**Note:** For some data types (issues, PRs), client-side filtering supplements API-level filtering to ensure accuracy.

## Combining Options

You can combine scan depth and time windows for targeted analysis:

```bash
# Quick check of recent activity
os4g check --scan-depth shallow --days-lookback 30

# Deep dive into last quarter
os4g check important-package --scan-depth deep --days-lookback 90

# Comprehensive recent analysis across all deps
os4g check --recursive --scan-depth deep --days-lookback 180

# Fast CI check of last month
os4g check --scan-depth shallow --days-lookback 30 --output-style compact
```

## Performance Considerations

### API Rate Limits

- **Shallow**: ~40% fewer API calls than default
- **Default**: Balanced API usage
- **Deep**: Similar API calls to default (more data per call)
- **Very Deep**: Similar API calls, but larger responses

GitHub API rate limits (with token):

- 5,000 requests per hour
- Each package analysis uses 1-2 requests
- Scan depth affects response size, not request count

## Verbose Output

Use `--verbose` to see scan configuration:

```bash
os4g check --scan-depth deep --days-lookback 90 --verbose
```

Output shows:

```shell
📊 Scan depth: deep
📅 Time window: last 90 days
🔍 Analyzing 10 package(s)...
```

## Best Practices

### For CI/CD Pipelines

```bash
# Fast, focused check
os4g check --scan-depth shallow --days-lookback 30 --output-style compact
```

### For Regular Audits

```bash
# Balanced, comprehensive
os4g check --scan-depth default --days-lookback 90
```

### For Deep Investigation

```bash
# Thorough analysis
os4g check specific-package --scan-depth deep --output-style detail
```

### For Large Projects

```bash
# Efficient recursive scanning
os4g check --recursive --scan-depth shallow --days-lookback 60
```

## Cache Behavior

Scan depth and time window settings **do not** invalidate cache:

- Cache stores raw data samples
- Settings control what data is fetched and filtered
- Different settings may reuse cached data
- Use `--no-cache` to force fresh analysis

**Example:**

```bash
# First run: fetches and caches data (default depth)
os4g check requests

# Second run: uses cache, same data
os4g check requests --scan-depth shallow

# Third run: forces fresh fetch with deep sampling
os4g check requests --scan-depth deep --no-cache
```

## Configuration File Support

Currently, scan depth and time window are **CLI-only** options. Future versions may support configuration file settings:

```toml
# Future: .oss-sustain-guard.toml
[tool.oss-sustain-guard]
scan_depth = "deep"
days_lookback = 90
```

## Troubleshooting

### "Rate limit exceeded" errors

**Solution:** Use `--scan-depth shallow` or analyze fewer packages:

```bash
os4g check --scan-depth shallow
```

### Analysis too slow

**Solutions:**

- Use `--scan-depth shallow`
- Add `--days-lookback` to focus on recent data
- Reduce number of packages
- Use `--no-cache` less frequently

### Insufficient data warnings

If you see "Not enough data for metric X":

**Solutions:**

- Use `--scan-depth deep` to collect more samples
- Remove or increase `--days-lookback`
- Check if project is actually active

## Examples

### Quick Health Check

```bash
os4g check --scan-depth shallow --output-style compact
```

### Monthly Review

```bash
os4g check --days-lookback 30 --output-format html --output-file monthly-report.html
```

### Comprehensive Audit

```bash
os4g check --scan-depth deep --output-style detail --verbose
```

### Maximum Detail Analysis

```bash
os4g check critical-package --scan-depth very_deep --days-lookback 180 --output-style detail
```

### CI/CD Integration

```bash
os4g check --scan-depth shallow --days-lookback 30 --no-cache --output-style compact
```

## See Also

- [Getting Started](GETTING_STARTED.md)
- [Caching Guide](CACHING_GUIDE.md)
- [GitHub Actions Integration](GITHUB_ACTIONS_GUIDE.md)
- [Scoring Profiles](SCORING_PROFILES_GUIDE.md)
