# Dependency Analysis Guide

The `--show-dependencies` (`-D`) flag analyzes and displays health scores of your project's dependencies.

> ℹ️ **Experimental feature**: Results are provided as helpful reference and may evolve.

## Requirements

Requires a **lockfile** (manifest files alone are insufficient). Supported lockfiles:

- **Python**: `uv.lock`, `poetry.lock`, `Pipfile.lock`
- **JavaScript**: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`
- **Rust**: `Cargo.lock`
- **Go**: `go.mod`, `go.sum`
- **Other**: `Gemfile.lock` (Ruby), `composer.lock` (PHP), `mix.lock` (Elixir), `cabal.project.freeze`/`stack.yaml.lock` (Haskell), `cpanfile.snapshot` (Perl), `pubspec.lock` (Dart), `renv.lock` (R), `Package.resolved` (Swift)

## Usage

```bash
# Analyze project with dependency scores
os4g check --show-dependencies

# With auto-detection
os4g check --show-dependencies --include-lock

# Compact format (CI/CD-friendly)
os4g check --show-dependencies -o compact

# Detail format with all metrics
os4g check --show-dependencies -o detail
```

Dependency scores are only available when analyzing projects with lockfiles. Individual package analysis won't show dependency scores.

## Interpreting Results

Scores use the same 0-100 scale:

| Score | Status | Action |
|-------|--------|--------|
| 80-100 | ✓ Healthy | Well-maintained |
| 50-79 | ⚠ Monitor | Review regularly |
| 0-49 | ✗ Needs support | Consider alternatives or contribute |

## Tips

- Run regularly in CI/CD to track changes
- Combine with security scanners for comprehensive analysis
- Focus on high-impact dependencies
- Consider supporting low-scoring projects you rely on

## Limitations

- Requires lockfiles (not manifest files alone)
- Only direct dependencies analyzed
- GitHub-only (private packages not scored)
- Cross-ecosystem dependencies not included

## See Also

- [Getting Started](GETTING_STARTED.md) - Basic usage guide
- [Recursive Scanning](RECURSIVE_SCANNING_GUIDE.md) - Scan multiple projects
- [Exclude Configuration](EXCLUDE_PACKAGES_GUIDE.md) - Filter packages from analysis
