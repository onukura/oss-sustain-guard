# Dependency Analysis Guide

The `trace` command provides comprehensive dependency tree analysis and visualization with health scores for all your dependencies.

> ℹ️ **Migration Notice**: The `--show-dependencies` flag has been removed from the `check` command. Use the `trace` command instead for superior dependency analysis capabilities.

## Migration from `--show-dependencies`

If you were previously using `check --show-dependencies`, here's how to migrate:

```bash
# Before (deprecated)
os4g check requests --show-dependencies

# After (recommended)
os4g trace requests                    # Full dependency tree
os4g trace requests --max-depth 1      # Direct dependencies only
os4g trace requirements.txt            # From lockfile
os4g trace javascript:react            # JavaScript packages
```

**Benefits of `trace` command:**

- Full tree structure visualization (not just statistics)
- Terminal, HTML, and JSON output formats
- Depth control and filtering options
- Support for package names and lockfiles
- Multi-ecosystem support (Python, JavaScript, Rust, etc.)

## Requirements

- **For lockfile mode**: A lockfile (see supported formats below)
- **For package mode**: External tool installed (`uv` for Python, `npm` for JavaScript, etc.)
- **API token**: GitHub/GitLab token (`GITHUB_TOKEN` or `GITLAB_TOKEN`)

### Supported Lockfiles

- **Python**: `uv.lock`, `poetry.lock`, `Pipfile.lock`
- **JavaScript**: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lock`, `deno.lock`
- **Rust**: `Cargo.lock`
- **Go**: `go.mod`, `go.sum`
- **Other**: `Gemfile.lock` (Ruby), `composer.lock` (PHP), `mix.lock` (Elixir), `cabal.project.freeze`/`stack.yaml.lock` (Haskell), `cpanfile.snapshot` (Perl), `pubspec.lock` (Dart), `renv.lock` (R), `Package.resolved` (Swift)

## Usage

### Quick Start (Terminal Output)

```bash
# Trace a package - shows in terminal
os4g trace requests

# Trace from lockfile - shows in terminal
os4g trace uv.lock
os4g trace package.json
```

### Lockfile Mode

```bash
# Trace lockfile dependencies
os4g trace package-lock.json
os4g trace uv.lock
os4g trace Cargo.lock

# Direct dependencies only
os4g trace requirements.txt --direct-only

# Limit depth
os4g trace package.json --max-depth 2
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

# Limit to direct dependencies
os4g trace requests --max-depth 1
```

### Advanced Options

```bash
# Custom scoring profile
os4g trace requests --profile security_first

# Shallow scan (faster)
os4g trace package.json --scan-depth shallow

# No cache (fresh analysis)
os4g trace uv.lock --no-cache

# Verbose logging
os4g trace Cargo.lock --verbose

# Custom number of workers
os4g trace package.json --num-workers 10
```

## Interpreting Results

Scores use the same 0-100 scale as the `check` command:

| Score | Status | Action |
|-------|--------|--------|
| 80-100 | ✓ Healthy | Well-maintained |
| 50-79 | ⚠ Monitor | Review regularly |
| 0-49 | ✗ Needs support | Consider alternatives or contribute |

### Terminal Output

The terminal output shows:

- 🌳 Tree structure showing dependency relationships
- 📊 Scores displayed inline with color coding
- ⭐ Direct dependencies marked with *
- 📈 Summary statistics (total packages, health distribution)

### HTML Output

Interactive HTML visualization with:

- 🟢 Green (≥80): Healthy dependencies
- 🟡 Yellow (50-79): Monitor these dependencies
- 🔴 Red (<50): Needs support or alternatives
- Clickable nodes for details
- Expandable/collapsible tree structure

## Tips

- **Run regularly in CI/CD** to track dependency health changes
- **Combine with security scanners** for comprehensive analysis
- **Focus on high-impact dependencies** (direct or heavily used)
- **Consider supporting low-scoring projects** you rely on
- **Use HTML output** for team reviews and documentation
- **Use JSON output** for integration with other tools

## Comparison: `trace` vs old `--show-dependencies`

| Feature | Old `check --show-dependencies` | New `trace` |
|---------|--------------------------------|-------------|
| Tree visualization | ❌ No | ✅ Yes |
| HTML output | ❌ No | ✅ Yes |
| JSON export | ❌ No | ✅ Yes |
| Depth control | ❌ No | ✅ Yes (`--max-depth`) |
| Package mode | ❌ No | ✅ Yes |
| Statistics only | ✅ avg/min/max/count | ❌ Full tree |
| Multi-ecosystem | ✅ Yes | ✅ Yes |

## Troubleshooting

**Unable to analyze dependencies**: Try with fewer workers (`--num-workers 2`) or use shallow scan (`--scan-depth shallow`)

**Graph data is empty**: Remove `--direct-only` flag or increase `--max-depth`

**Slow analysis**: Use `--scan-depth shallow` and/or `--direct-only`

**Lockfile not detected**: Ensure the lockfile exists and has a supported extension

### Storage and Performance Notes

When using **package mode** (analyzing packages directly without lockfiles), the tool may create temporary directories:

- **JavaScript packages**: Tools like `pnpm`, `npm`, `bun` create temporary `node_modules` during resolution
  - The tool uses minimal install options (`--ignore-scripts`, `--no-optional`, `--prefer-offline`) to reduce disk usage
  - Typical temporary storage: 10-100 MB depending on package size
- **Python packages**: Tool `uv` only generates a lockfile without installing packages
  - Much more storage-efficient than JavaScript (typically <1 MB)
  - No virtual environment or package installation required
- **Automatic cleanup**: All temporary files are automatically cleaned up after analysis
- **Recommendation**: For repeated analyses, prefer lockfile mode or ensure adequate temporary storage space

**Storage savings tips:**
- Use lockfile mode when possible (e.g., `trace package-lock.json` instead of `trace javascript:react`)
- Clear system temp directory regularly if running many package analyses
- Use `--max-depth 1` or `--direct-only` to limit dependency tree size
- Python analysis is more storage-friendly than JavaScript for package mode

## See Also

- [Dependency Graph Visualization Guide](DEPENDENCY_GRAPH_VISUALIZATION.md) - Complete `trace` command reference
- [Getting Started](GETTING_STARTED.md) - Basic usage guide
- [Recursive Scanning](RECURSIVE_SCANNING_GUIDE.md) - Scan multiple projects
- [Exclude Configuration](EXCLUDE_PACKAGES_GUIDE.md) - Filter packages from analysis
- [Scoring Profiles Guide](SCORING_PROFILES_GUIDE.md) - Custom scoring
- [Caching Guide](CACHING_GUIDE.md) - Performance optimization
