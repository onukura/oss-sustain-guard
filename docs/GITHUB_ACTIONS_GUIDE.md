# GitHub Actions Integration Guide

This guide explains how to integrate **OSS Sustain Guard** into your GitHub Actions workflows for automated package sustainability checks.

## Overview

OSS Sustain Guard provides three ways to integrate with GitHub Actions:

1. **Docker Action** (Recommended) - Pre-built Docker image for fastest execution
2. **Reusable Workflow** (`.github/workflows/check-packages.yml`) - Shared workflow for multiple projects
3. **Composite Action** - Pure shell implementation (legacy)

## Quick Start

The fastest and most reliable way to use OSS Sustain Guard:

```yaml
- name: Check package sustainability
  uses: onukura/oss-sustain-guard@main
  with:
    packages: 'requests django flask'
    output-style: 'compact'
```

**💡 Tip: For CI/CD, use the compact output format**

Use `output-style: 'compact'` for cleaner workflow logs.
This provides one-line-per-package output, perfect for logs and automated reporting.

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
          output-style: 'compact'
```

**Automatically detects from:**

- `package-lock.json` / `yarn.lock` / `pnpm-lock.yaml` (JavaScript)
- `requirements.txt` / `poetry.lock` / `uv.lock` (Python)
- `Cargo.lock` (Rust)
- `Gemfile.lock` (Ruby)
- `composer.lock` (PHP)
- `go.sum` (Go)
- And more...

### 2. Check Specific Critical Packages

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
          output-style: 'compact'
```

### 3. Fail on Critical Findings

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

### 4. Recursive Monorepo Scanning

For monorepo projects, recursively scan all subdirectories:

```yaml
name: Monorepo Dependency Scan

on: [pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Scan all packages in monorepo
        uses: onukura/oss-sustain-guard@main
        with:
          recursive: 'true'
          root-dir: './packages'
          output-style: 'compact'
```

### 5. Specific Manifest File Analysis

Analyze a specific manifest file (useful for multiple environments):

```yaml
name: Production Dependencies Check

on: [pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check production dependencies
        uses: onukura/oss-sustain-guard@main
        with:
          manifest: './requirements/production.txt'
          profile: 'long_term_stability'
          output-style: 'detail'
```

## FAQ

- **Do I need a GitHub token?**: For most cases, no setup is needed. For uncached packages or large scans, set `GITHUB_TOKEN` or a custom token in your workflow secrets.
- **Does it support multiple languages?**: Yes! Python, JavaScript, Rust, Go, Ruby, PHP, and more are supported out of the box.
- **How do I check only specific packages?**: Use the `packages` input: `packages: 'flask django npm:react'`
- **How do I skip the check?**: Remove or comment out the step in your workflow.

For more details or troubleshooting, see the [GitHub repository](https://github.com/onukura/oss-sustain-guard) or [Getting Started](./GETTING_STARTED.md).

## Performance Tips

### Reuse cached data with GitHub Actions cache

You can speed up repeated runs by caching OSS Sustain Guard's local cache directory. Add a step before the scan to restore the cache:

```yaml
    - name: Restore OSS Sustain Guard cache
      uses: actions/cache@v4
      with:
        path: ${{ env.OSS_SUSTAIN_GUARD_CACHE_DIR || '~/.cache/oss-sustain-guard' }}
        key: oss-sg-${{ runner.os }}-${{ github.run_id }}
        restore-keys: |
          oss-sg-${{ runner.os }}-

    # ...run OSS Sustain Guard scan here...
```

#### Customizing the cache location

By default, the cache directory is `~/.cache/oss-sustain-guard`. You can control this location by setting the `OSS_SUSTAIN_GUARD_CACHE_DIR` environment variable in your workflow:

```yaml
    - name: Set custom cache dir
      run: echo "OSS_SUSTAIN_GUARD_CACHE_DIR=$HOME/oss-sg-cache" >> $GITHUB_ENV
```

Then update the cache step to use the same path:

```yaml
    - name: Restore OSS Sustain Guard cache
      uses: actions/cache@v4
      with:
        path: ${{ env.OSS_SUSTAIN_GUARD_CACHE_DIR }}
        # ...
```

This is useful if you want to isolate caches between jobs or workflows.

This ensures that package analysis results are reused between CI runs, making subsequent checks much faster and reducing GitHub API usage.

## Security Considerations

1. **Token scoping** - Use read-only GitHub tokens when possible
1. **Sensitive packages** - Don't expose internal package names in logs
1. **PR comments** - Be careful when posting results as PR comments

## Support

For issues or questions:

- [GitHub Issues](https://github.com/onukura/oss-sustain-guard/issues)
- [Getting Started](./GETTING_STARTED.md)
- Documentation
