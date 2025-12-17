# Dependency Analysis Guide

## Overview

The `--show-dependencies` (`-D`) flag enables OSS Sustain Guard to analyze and display the health scores of your project's dependencies. This provides a **holistic risk assessment** by evaluating not just the primary package, but also the sustainability of its entire dependency tree.

## Why Dependency Analysis Matters

When assessing package sustainability, evaluating only the primary package is incomplete. Dependencies form the foundation of your project:

- **Transitive Risks**: Unmaintained dependencies can introduce security vulnerabilities and technical debt
- **Supply Chain Health**: A healthy package built on unstable dependencies is like a "thin toothpick supporting a building"
- **Long-term Viability**: Understanding the health of your entire dependency tree helps you make informed decisions about package adoption

## Requirements

The `--show-dependencies` flag **only works when your project contains a lockfile**. Supported lockfiles include:

### Python

- `uv.lock` (UV package manager)
- `poetry.lock` (Poetry)
- `Pipfile.lock` (Pipenv)

### JavaScript/TypeScript

- `package-lock.json` (npm v7+)
- `yarn.lock` (Yarn)
- `pnpm-lock.yaml` (pnpm)

### Other Ecosystems

- `Cargo.lock` (Rust)
- `go.mod`, `go.sum` (Go modules)
- `Gemfile.lock` (Ruby)
- `composer.lock` (PHP)

## Usage

### Basic Usage

Analyze your project with dependency scores:

```bash
oss-guard check --show-dependencies
```

Or with auto-detection:

```bash
oss-guard check --show-dependencies --include-lock
```

### With Specific Packages

Dependency scores are **only available when analyzing your project directory with lockfiles present**. Specifying individual packages will show a warning:

```bash
cd /path/to/your/project
oss-guard check requests --show-dependencies
# ℹ️  --show-dependencies specified but no lockfiles found in .
#    Dependency scores are only available when analyzing projects with lockfiles.
```

### Compact Format

Display dependency statistics in compact format (ideal for CI/CD):

```bash
oss-guard check --show-dependencies -c
```

Output:

```shell
✓ my-project (87/100) - Healthy
  🔗 Dependencies: avg=75, min=45, max=92, count=23
```

### Verbose Format

Display detailed dependency tables:

```bash
oss-guard check --show-dependencies --verbose
```

Output:

```shell
🔗 my-project - Dependency Reference Scores (Top 15):
┏━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Package        ┃ Score  ┃ Health          ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ click          │ 87/100 │ Healthy ✓       │
│ requests       │ 76/100 │ Needs attention │
│ urllib3        │ 68/100 │ Needs attention │
│ ...            │        │                 │
└────────────────┴────────┴─────────────────┘
```

### Standard Format

Display top 10 dependencies with health status:

```bash
oss-guard check --show-dependencies
```

Output:

```shell
🔗 my-project - Dependency Reference Scores (Top 10):
   • click 87/100 ✓ Healthy
   • requests 76/100 ⚠ Needs attention
   • urllib3 68/100 ⚠ Needs attention
   • ...
```

## Interpreting Results

Dependency scores use the same 0-100 scale as primary packages:

| Score Range | Status | Interpretation |
|-------------|--------|-----------------|
| 80-100 | ✓ Healthy | Well-maintained, actively developed |
| 50-79 | ⚠ Needs attention | Monitor for updates, consider alternatives |
| 0-49 | ✗ Needs support | High risk, prioritize replacement or support |

## Real-World Example

```bash
# Analyze your project with dependency insights
cd my-python-project
oss-guard check --show-dependencies --verbose

# Results show:
# ✓ my-project (85/100) - Healthy
#
# 🔗 Dependency Reference Scores (Top 10):
#    • click 87/100 ✓ Healthy
#    • charset-normalizer 80/100 ✓ Healthy
#    • coverage 74/100 ⚠ Needs attention
#    • anyio 66/100 ⚠ Needs attention
#    • ...
```

This reveals that while your project is healthy, some dependencies need monitoring. You can then:

1. Check if updated versions are available
2. Evaluate alternative packages with better sustainability scores
3. Consider contributing to low-scoring dependencies you rely on
4. Adjust your risk tolerance based on your use case

## Tips & Best Practices

1. **Run regularly**: Dependency health changes over time. Include this in your CI/CD pipeline.

2. **Combine with other tools**: Use alongside security scanners and vulnerability databases for comprehensive analysis.

3. **Prioritize critical dependencies**: Focus on dependencies that are:
   - Core to your application logic
   - Frequently updated or actively used
   - On the critical path of your system

4. **Support low-scoring projects**: If a low-scoring dependency is critical to your project, consider:
   - Contributing code or documentation
   - Sponsoring the maintainer
   - Volunteering as a maintainer

5. **Track trends**: Monitor how your dependency scores change over time to identify emerging risks.

## Limitations

- Dependency analysis requires lockfiles (manifest files alone are insufficient)
- Only direct dependencies are analyzed (not transitive dependencies)
- Scores are based on GitHub repository metrics (private packages won't be scored)
- Cross-ecosystem dependencies (e.g., Python calling Rust native code) are not analyzed

## See Also

- [Getting Started](GETTING_STARTED.md) - Basic usage guide
- [Recursive Scanning](RECURSIVE_SCANNING_GUIDE.md) - Scan multiple projects
- [Exclude Configuration](EXCLUDE_PACKAGES_GUIDE.md) - Filter packages from analysis
