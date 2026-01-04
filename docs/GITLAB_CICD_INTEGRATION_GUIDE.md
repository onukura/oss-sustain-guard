# GitLab CI/CD Integration Guide

This guide explains how to integrate **OSS Sustain Guard** into your GitLab CI/CD pipelines for automated package sustainability checks.

## Overview

OSS Sustain Guard integrates with GitLab CI/CD through Docker images or direct Python execution. This guide covers:

1. **Docker-based Pipeline** (Recommended) - Pre-built Docker image for fastest execution
2. **Script-based Pipeline** - Direct Python execution with UV package manager
3. **Merge Request Integration** - Automated comments on MR/PR discussions

**💡 Tip: Use compact output for cleaner CI logs**

Use `--output-style compact` / `-o compact` for one-line-per-package output, perfect for logs.

## Configuration Examples

### 1. Auto-Detect and Check All Repository Dependencies (Recommended)

The most common use case - automatically detect and analyze all dependencies in your repository:

```yaml
stages:
  - test

check-dependencies:
  stage: test
  image: ghcr.io/onukura/oss-sustain-guard
  script:
    - oss-sustain-guard check --recursive -o compact
  allow_failure: true
  variables:
    GITHUB_TOKEN: $GITHUB_TOKEN  # Set this in GitLab CI/CD variables
```

**Automatically detects from:**

- `package-lock.json` / `pnpm-lock.yaml` / `bun.lock` / `deno.lock` (JavaScript)
- `requirements.txt` / `poetry.lock` / `uv.lock` (Python)
- `Cargo.lock` (Rust)
- `Gemfile.lock` (Ruby)
- `composer.lock` (PHP)
- `go.sum` (Go)
- And more...

### 2. With Caching for Performance

Cache the OSS Sustain Guard analysis results to speed up subsequent runs:

```yaml
check-dependencies-cached:
  stage: test
  image: ghcr.io/onukura/oss-sustain-guard
  cache:
    paths:
      - .cache/oss-sustain-guard/
    key: "oss-sustain-guard-cache-${CI_COMMIT_BRANCH}"
  script:
    - oss-sustain-guard check --recursive -o compact
  allow_failure: true
  variables:
    GITHUB_TOKEN: $GITHUB_TOKEN  # Set this in GitLab CI/CD variables
```

### 3. With GitHub Token for Better Rate Limits

Provide a GitHub token for increased API rate limits (recommended for larger repositories):

```yaml
check-dependencies-with-token:
  stage: test
  image: ghcr.io/onukura/oss-sustain-guard
  script:
    - oss-sustain-guard check --recursive -o compact
  allow_failure: true
  variables:
    GITHUB_TOKEN: $GITHUB_TOKEN  # Set this in GitLab CI/CD variables
```

## Best Practices

### 1. Use Scheduled Pipelines for Regular Checks

Check dependencies on a schedule (daily or weekly) to catch issues over time:

```yaml
check-dependencies-scheduled:
  stage: test
  image: ghcr.io/onukura/oss-sustain-guard
  script:
    - oss-sustain-guard check --recursive --output-style=compact
  allow_failure: true
  only:
    - schedules
```

### 2. Parallel Scanning for Faster Results

Split scanning across multiple jobs for monorepos:

```yaml
stages:
  - test

cache:
  paths:
  - .cache/oss-sustain-guard/
  key: "oss-sustain-guard-cache-${CI_COMMIT_BRANCH}"

check-backend:
  stage: test
  image: ghcr.io/onukura/oss-sustain-guard
  script:
    - oss-sustain-guard check --root-dir ./backend/ -o compact --include-lock
  allow_failure: true

check-frontend:
  stage: test
  image: ghcr.io/onukura/oss-sustain-guard
  script:
            - oss-sustain-guard check --root-dir ./frontend/ -o compact --include-lock
  allow_failure: true

check-services:
  stage: test
  image: ghcr.io/onukura/oss-sustain-guard
  script:
    - oss-sustain-guard check --recursive --root-dir ./services/ -o compact --include-lock
  allow_failure: true
```

### 3. Save output Artifacts for Review

Save the output as artifacts for later review:

```yaml
check-dependencies-with-artifacts:
  stage: test
  image: ghcr.io/onukura/oss-sustain-guard
  script:
    - oss-sustain-guard check --recursive -o compact --output-format html --output-file oss-sustain-report.html
  artifacts:
    paths:
      - oss-sustain-report.html
  allow_failure: true
  variables:
    GITHUB_TOKEN: $GITHUB_TOKEN  # Set this in GitLab CI/CD variables
  cache:
    paths:
    - .cache/oss-sustain-guard/
    key: "oss-sustain-guard-cache-${CI_COMMIT_BRANCH}"
```

## Additional Resources

- [OSS Sustain Guard Documentation](./GETTING_STARTED.md)
- [Built-in Metrics Guide](./BUILT_IN_METRICS_GUIDE.md)
- [Caching Guide](./CACHING_GUIDE.md)
- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
