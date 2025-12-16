# OSS Sustain Guard Documentation

OSS Sustain Guard is a multi-language package sustainability analyzer that helps you observe the health of your dependencies across ecosystems. The tool surfaces constructive insights about maintainer activity, community engagement, security posture, and funding signals so teams can support the projects they rely on.

![CLI demo showing an analyzed package](assets/demo01..png)

## Why OSS Sustain Guard?

- **Token-less experience:** Cached snapshots for popular packages let you view sustainability insights without any tokens.
- **Multi-ecosystem awareness:** Python, JavaScript, Go, Rust, PHP, Java, Kotlin, C#, and Ruby package formats are supported.
- **Actionable signals:** Metrics are grouped by sustainability dimensions with empathetic language that encourages collaboration with maintainers.
- **Time-travel friendly:** Historical snapshots enable time-series analysis and comparisons between releases.

## Installation

Install from PyPI:

```bash
pip install oss-sustain-guard
```

If you plan to build the documentation locally, install the documentation extras:

```bash
pip install mkdocs mkdocs-material
```

## Quickstart

Run a single package check:

```bash
oss-guard check requests
```

Mix ecosystems in one command:

```bash
oss-guard check python:django npm:react rust:tokio
```

Auto-detect manifests and lockfiles in the current directory:

```bash
oss-guard check --include-lock
```

### GitHub token and caching

- Cached packages are served instantly from `data/latest/*.json` and do not require network calls.
- Uncached packages use the GitHub API for repository data. Set `GITHUB_TOKEN` in your environment to enable those lookups while staying within GitHub rate limits.
- Use `--clear-cache` to refresh local cache entries when you need the latest snapshot.

### Recursive and manifest-driven scanning

Monorepos and multi-service codebases are supported through recursive scanning and manifest detection:

```bash
# Scan a project tree, respecting common exclusion defaults
oss-guard check --recursive

# Limit recursion depth and include lock files
oss-guard check --recursive --include-lock --depth 2

# Analyze a specific manifest file
oss-guard check --manifest package.json
```

### Funding awareness

When a community-driven project publishes funding links, OSS Sustain Guard highlights them with encouraging language so you can consider giving back. Corporate-backed projects skip funding prompts because they typically rely on other sustainability models.

## GitHub Actions

Automate checks in CI with the GitHub Action:

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    packages: "requests django"
    verbose: "true"
```

See the [GitHub Actions Integration guide](GITHUB_ACTIONS_GUIDE.md) for configuration details and caching tips.

## Additional Guides

The documentation set includes focused guides for deeper exploration:

- [CHAOSS Metrics Alignment Validation](CHAOSS_METRICS_ALIGNMENT_VALIDATION.md)
- [Database Schema](DATABASE_SCHEMA.md)
- [Directory Exclusion Examples](DIRECTORY_EXCLUSION_EXAMPLES.md)
- [Excluding Packages](EXCLUDE_PACKAGES_GUIDE.md)
- [Pre-commit Integration](PRE_COMMIT_INTEGRATION.md)
- [Recursive Scanning](RECURSIVE_SCANNING_GUIDE.md)
- [Scoring Profiles](SCORING_PROFILES_GUIDE.md)
- [Schema Version Management](SCHEMA_VERSION_MANAGEMENT.md)
- [Trend Analysis](TREND_ANALYSIS_GUIDE.md)
- [Gratitude Vending Machine](GRATITUDE_VENDING_MACHINE.md)

## Community standards

OSS Sustain Guard uses encouraging, respectful language across all user-facing surfaces. Observations are framed to help teams collaborate with maintainers and improve sustainability together.
