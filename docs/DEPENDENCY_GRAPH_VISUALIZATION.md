# Dependency Tracing and Visualization Guide

The `trace` command traces and visualizes your project's dependency network with health scores in terminal.

## Requirements

- For lockfile mode: A lockfile (see [Dependency Analysis Guide](DEPENDENCY_ANALYSIS_GUIDE.md) for formats)
- For package mode: External tool installed
  - Python: `uv`
  - JavaScript: `npm`, `pnpm`, or `bun`
  - Rust: `cargo`
  - Ruby: `bundler`
- GitHub/GitLab token (`GITHUB_TOKEN` or `GITLAB_TOKEN`)

## Basic Usage

### Quick Start

```bash
# Trace a package
os4g trace requests

# Trace from lockfile
os4g trace uv.lock
os4g trace package.json
```

### Lockfile Mode

```bash
# Trace lockfile dependencies
os4g trace package-lock.json
os4g trace uv.lock
os4g trace Cargo.lock
```

### Package Mode

```bash
# Trace a specific package (Python default)
os4g trace requests

# Trace with specific version
os4g trace requests --version 2.28.0

# Trace from other ecosystems
os4g trace javascript:react
os4g trace -e rust serde
os4g trace -e ruby rails
os4g trace lodash --ecosystem javascript --tool pnpm

# Force specific package manager tool
os4g trace requests --tool uv
os4g trace serde --ecosystem rust --tool cargo
os4g trace rails --ecosystem ruby --tool bundler
```

## Options

| Option | Description |
|--------|-------------|
| `--ecosystem`, `-e` | Package ecosystem (python, javascript, rust, ruby, etc.) - for package mode |
| `--version`, `-V` | Package version (default: latest) - for package mode |
| `--tool`, `-t` | Force specific package manager tool (uv, npm, pnpm, bun, cargo, bundler) - for package mode |
| `--direct-only` | Direct dependencies only (exclude transitive) |
| `--max-depth N` | Limit tree depth (1=direct, 2=direct+1st transitive, etc.) |
| `--profile` | Scoring profile: `balanced`, `security_first`, `contributor_experience`, `long_term_stability` |
| `--profile-file` | Custom TOML profile |
| `--scan-depth` | Data sampling: `shallow`, `default`, `deep`, `very_deep` |
| `--days-lookback N` | Analyze activity from last N days |
| `--no-cache` | Real-time analysis (skip cache) |
| `--num-workers N` | Parallel workers (default: 5) |
| `--verbose` | Detailed logging |

**Examples:**

```bash
# Lockfile mode
os4g trace package.json --direct-only
os4g trace Cargo.lock --max-depth 2 --profile security_first
os4g trace uv.lock --scan-depth shallow --num-workers 3

# Package mode
os4g trace requests --max-depth 2
os4g trace requests --version 2.28.0 --profile security_first
os4g trace serde --ecosystem rust --max-depth 3
os4g trace rails --ecosystem ruby --max-depth 2
os4g trace react --tool npm --max-depth 2
```

### Caching & Performance

| Option | Description |
|--------|-------------|
| `--no-cache` | Perform real-time analysis (skip cache, slower) |
| `--no-local-cache` | Skip local cache but use built-in defaults |
| `--cache-dir` | Custom cache directory path |
| `--cache-ttl` | Cache validity period in seconds (default: 604,800 = 7 days) |

**Examples:**

```bash
# Bypass cache for fresh data
os4g trace uv.lock --no-cache

# Use custom cache location
os4g trace Cargo.lock --cache-dir /tmp/my-cache
```

### Data Sampling & Scope

| Option | Description |
|--------|-------------|
| `--scan-depth` | Data sampling level: `shallow`, `default`, `deep`, `very_deep` |
| `--days-lookback` | Only analyze activity from the last N days |

**Examples:**

```bash
# Quick scan with minimal API calls
os4g trace package-lock.json --scan-depth shallow

# Comprehensive analysis with maximum detail
os4g trace requirements.txt --scan-depth very_deep

# Only analyze recent activity (last 90 days)
os4g trace Cargo.lock --days-lookback 90
```

### SSL & Network

| Option | Description |
|--------|-------------|
| `--insecure` | Disable SSL certificate verification (development only) |
| `--ca-cert` | Path to custom CA certificate file |

**Examples:**

```bash
# For development environments with custom SSL
os4g trace package.json --ca-cert /etc/ssl/my-ca.crt

# Disable SSL verification (not recommended for production)
os4g trace uv.lock --insecure
```

### Verbosity & Debugging

| Option | Description |
|--------|-------------|
| `--verbose`, `-v` | Enable detailed logging (cache operations, API calls, etc.) |
| `--num-workers` | Parallel analysis workers (default: 5) |

**Examples:**

```bash
# See detailed analysis progress and cache info
os4g trace Cargo.lock --verbose

# Increase parallelism for faster analysis
os4g trace package-lock.json --num-workers 10
```

## Output Format

### Terminal Tree Display

Tree display directly in your terminal - fast and convenient!

```bash
# Trace and display dependencies
os4g trace requests
os4g trace uv.lock
```

Features:

- 🎨 Color-coded packages (green/yellow/red based on scores)
- 🌳 Tree structure showing dependency relationships
- 📊 Scores displayed inline
- ⭐ Direct dependencies marked with *
- ⚡ Quick and easy to read

Example output:

```
Dependency Tree:
Total: 6 packages | Healthy: 1 | Monitor: 4 | Needs attention: 0 | Unknown: 1
Legend: ■ Healthy (≥80) | ■ Monitor (50-79) | ■ Needs attention (<50)

temp-os4g-trace 0.1.0 *
└── requests 2.32.5 (score: 85) *
    ├── certifi 2026.1.4 (score: 55) *
    ├── charset-normalizer 3.4.4 (score: 73) *
    ├── idna 3.11 (score: 53) *
    └── urllib3 2.6.2 (score: 76) *
```

## Interpreting Results

- **🟢 Green (≥80)**: Healthy, well-maintained
- **🟡 Yellow (50-79)**: Monitor for updates
- **🔴 Red (<50)**: Needs support

For security-focused analysis, use `--profile security_first`. For contributor experience, use `--profile contributor_experience`.

## Troubleshooting

**Unable to analyze dependencies**: Try with fewer workers (`--num-workers 2`) or use shallow scan (`--scan-depth shallow`)

**Graph data is empty**: Remove `--direct-only` flag or increase `--max-depth`

**Slow analysis**: Use `--scan-depth shallow` and/or `--direct-only`

## See Also

- [Dependency Analysis Guide](DEPENDENCY_ANALYSIS_GUIDE.md) - Migration from `--show-dependencies` and comprehensive usage
- [Scoring Profiles Guide](SCORING_PROFILES_GUIDE.md) - Custom scoring
- [Caching Guide](CACHING_GUIDE.md) - Performance optimization

## API Tokens

Set environment variables for analysis:

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx      # For GitHub
export GITLAB_TOKEN=glpat_xxxxxxxxxx      # For GitLab

# Run trace (terminal output)
os4g trace package-lock.json
os4g trace requests
```

## Mode Detection

The `trace` command automatically detects the mode based on input:

- **Lockfile mode**: If input is a file path (exists, contains `/` or `\`, or has lockfile extension)
- **Package mode**: Otherwise, treated as package name

Examples:

```bash
os4g trace requirements.txt    # → Lockfile mode (file exists)
os4g trace requests             # → Package mode (not a file)
os4g trace ./package.json       # → Lockfile mode (contains ./)
os4g trace python:requests      # → Package mode (ecosystem prefix)
```
