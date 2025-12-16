# GitHub Actions Integration Guide

This guide explains how to integrate **OSS Sustain Guard** into your GitHub Actions workflows for automated package sustainability checks.

## Overview

OSS Sustain Guard provides three ways to integrate with GitHub Actions:

1. **Docker Action** (Recommended) - Pre-built Docker image for fastest execution
2. **Reusable Workflow** (`.github/workflows/check-packages.yml`) - Shared workflow for multiple projects
3. **Composite Action** - Pure shell implementation (legacy)

## Quick Start

### Option 1: Using the Docker Action (Recommended ⭐)

The fastest and most reliable way to use OSS Sustain Guard:

```yaml
- name: Check package sustainability
  uses: onukura/oss-sustain-guard@main
  with:
    packages: 'requests django flask'
```

**Why Docker Action?**

- ⚡ **Instant** - No dependency installation or compilation
- 📦 **Reliable** - Pre-tested Docker image
- 🌍 **Complete** - All languages and ecosystems included
- 🔒 **Secure** - Isolated container environment

**💡 Tip: For CI/CD, use the compact output format**

Add `--compact` to your command for cleaner workflow logs:

```yaml
- name: Check package sustainability
  uses: onukura/oss-sustain-guard@main
  with:
    packages: 'requests django flask --compact'
```

This provides one-line-per-package output, perfect for logs and automated reporting.

### Option 2: Using the Reusable Workflow

```yaml
jobs:
  check-deps:
    uses: onukura/oss-sustain-guard/.github/workflows/check-packages.yml@main
    with:
      packages: 'flask requests numpy'
```

## Action Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `packages` | string | Yes | - | Space-separated package names (e.g., `"requests django npm:react"`) |
| `include-lock` | boolean | No | `false` | Auto-detect packages from lock files in repository |
| `verbose` | boolean | No | `false` | Show detailed metrics for each package |
| `github-token` | string | No | `secrets.GITHUB_TOKEN` | GitHub API token for uncached packages (optional, only if analyzing new packages) |

## Real-World Examples

### 1. Auto-Detect and Check All Repository Dependencies (Recommended)

The most common use case - automatically detect and analyze all dependencies in your repository:

```yaml
name: Dependency Health Check

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check all repository dependencies
        uses: onukura/oss-sustain-guard@main
        with:
          include-lock: 'true'
          compact: 'true'
```

**Automatically detects from:**

- `package-lock.json` / `yarn.lock` / `pnpm-lock.yaml` (JavaScript)
- `requirements.txt` / `poetry.lock` / `uv.lock` (Python)
- `Cargo.lock` (Rust)
- `Gemfile.lock` (Ruby)
- `composer.lock` (PHP)
- `go.sum` (Go)
- And more...

### 2. Multi-Language Stack with Manifest Detection

For projects with multiple package managers, auto-detect all ecosystems:

```yaml
name: Multi-Language Sustainability Check

on: [pull_request]

jobs:
  analyze-dependencies:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Analyze all dependencies from manifests
        uses: onukura/oss-sustain-guard@main
        with:
          include-lock: 'true'
          verbose: 'true'
```

### 3. Check Specific Critical Packages

For security audits or critical dependency reviews:

```yaml
name: Critical Packages Check

on: [pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check critical dependencies
        uses: onukura/oss-sustain-guard@main
        with:
          packages: 'flask django requests'
          compact: 'true'
```

### 4. Fail on Critical Findings

```yaml
name: Critical Dependencies Check

on: [pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check high-risk dependencies
        uses: onukura/oss-sustain-guard@main
        with:
          packages: 'critical-payment-lib authentication-provider'
          verbose: 'true'

      - name: Review critical packages
        if: failure()
        run: echo "⚠️  Critical packages need review!"
```

### 5. Post Results as PR Comment

```yaml
name: Check and Comment

on: [pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Analyze dependencies
        id: analysis
        uses: onukura/oss-sustain-guard@main
        with:
          include-lock: 'true'
          compact: 'true'

      - name: Comment on PR
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '✅ Dependency sustainability check complete!\n\nSee workflow logs for details.'
            })
```

### 6. Scheduled Weekly Audits

```yaml
name: Weekly Dependency Audit

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM UTC
  workflow_dispatch:

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run weekly audit
        uses: onukura/oss-sustain-guard@main
        with:
          include-lock: 'true'
          verbose: 'true'
```

## Ecosystem Prefixes

When specifying packages from different ecosystems:

| Ecosystem | Prefix | Example |
|-----------|--------|---------|
| Python | `python:` or none | `requests` or `python:flask` |
| JavaScript | `npm:` or `js:` | `npm:react` or `js:express` |
| Rust | `rust:` | `rust:tokio` |
| Ruby | `ruby:` or `gem:` | `ruby:rails` |
| Go | `go:` | `go:github.com/golang/go` |
| PHP | `php:` or `composer:` | `php:symfony/console` |
| Java | `java:` | `java:com.google.guava:guava` |
| C# | `csharp:` or `nuget:` | `csharp:Newtonsoft.Json` |

## Output Handling

### Using Action Outputs

```yaml
- name: Check packages
  id: check
  uses: onukura/oss-sustain-guard@main
  with:
    packages: 'requests'

- name: Use results
  run: echo "Result: ${{ steps.check.outputs.summary }}"
```

### Capturing Workflow Output

The action provides the `summary` output which can be used in subsequent steps.

## Authentication

### Default (Recommended)

Most popular packages are cached, so you don't need to configure anything. The action uses `secrets.GITHUB_TOKEN` automatically if needed:

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    packages: 'flask'
  # Works fine for cached packages
  # GITHUB_TOKEN is automatically available if analyzing uncached packages
```

### When You Need a Custom Token

Only required if analyzing many new packages and hitting GitHub API rate limits:

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    packages: 'flask'
    github-token: ${{ secrets.CUSTOM_GITHUB_TOKEN }}
```

## Troubleshooting

### Action Fails with "Repository not found"

The action checks packages against the OSS Sustain Guard database. If a package is not found:

1. Verify the package name spelling
2. Ensure the correct ecosystem prefix is used
3. Check if the package is available in its registry

### High Resource Usage

For large multi-language checks, consider:

1. Breaking into multiple jobs:

```yaml
jobs:
  check-python:
    uses: onukura/oss-sustain-guard/.github/workflows/check-packages.yml@main
    with:
      packages: 'flask django requests'

  check-javascript:
    uses: onukura/oss-sustain-guard/.github/workflows/check-packages.yml@main
    with:
      packages: 'npm:react npm:express npm:vue'
```

2. Using matrix strategy:

```yaml
jobs:
  check:
    strategy:
      matrix:
        packages:
          - 'flask django'
          - 'npm:react npm:express'
          - 'rust:tokio ruby:rails'
    uses: onukura/oss-sustain-guard/.github/workflows/check-packages.yml@main
    with:
      packages: ${{ matrix.packages }}
```

### API Rate Limiting

For large-scale checks, ensure your GitHub token has sufficient permissions:

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    packages: 'requests django flask'
    github-token: ${{ secrets.ELEVATED_TOKEN }}
```

## Performance Tips

1. **Use `--compact` for CI/CD** - Compact output is more readable in logs and faster to process

   ```yaml
   - uses: onukura/oss-sustain-guard@main
     with:
       packages: 'requests django flask --compact'
   ```

2. **Reuse cached data** - First run caches package data for faster subsequent checks
3. **Use `include-lock: 'true'`** - More efficient than listing individual packages
4. **Split large checks** - Use matrix strategy for parallel execution
5. **Schedule off-peak** - Run checks during low-traffic periods

## Security Considerations

1. **Token scoping** - Use read-only GitHub tokens when possible
2. **Sensitive packages** - Don't expose internal package names in logs
3. **PR comments** - Be careful when posting results as PR comments

## Advanced: Using Reusable Workflow

For more control, use the reusable workflow directly:

```yaml
jobs:
  check-packages:
    uses: onukura/oss-sustain-guard/.github/workflows/check-packages.yml@main
    with:
      packages: 'flask requests'
      include-lock: false
      verbose: false
      fail-on-score: 0
```

### Reusable Workflow Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `packages` | string | - | Space-separated packages to check |
| `include-lock` | boolean | `false` | Auto-detect from lock files |
| `verbose` | boolean | `false` | Detailed output |
| `fail-on-score` | number | `0` | Fail if score drops below threshold |

## Support

For issues or questions:

- [GitHub Issues](https://github.com/onukura/oss-sustain-guard/issues)
- [Getting Started](./GETTING_STARTED.md)
- [Documentation](./DATABASE_SCHEMA.md)
