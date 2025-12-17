# Getting Started with OSS Sustain Guard

OSS Sustain Guard is a multi-language package sustainability analyzer that helps you understand the health of your dependencies. This guide shows you how to get started in just a few minutes.

## 📦 Installation

Install easily from PyPI:

```bash
pip install oss-sustain-guard
```

## 🚀 First Steps

### 1. Check a Single Package

```bash
oss-guard check requests
```

This shows you:

- **Health Score** (0-100): Overall sustainability rating
- **Health Status**: Healthy ✓, Monitor, or Needs attention
- **Key Observations**: Important signals about the project

### 2. Check Multiple Packages

```bash
oss-guard check python:django npm:react rust:tokio
```

Mix any languages you use in one command.

### 3. Auto-Detect Your Project Dependencies

```bash
oss-guard check --include-lock
```

Automatically scans `requirements.txt`, `package.json`, `Cargo.toml`, and other manifest files.

### 4. Scan Entire Projects (Monorepos)

```bash
oss-guard check --recursive
```

Recursively finds and analyzes all dependencies in subdirectories.

### 5. Analyze Your Project's Dependencies

```bash
oss-guard check --show-dependencies
```

Displays health scores of all your project's dependencies (requires lockfiles like `uv.lock`, `package-lock.json`, etc.).

See [Dependency Analysis Guide](DEPENDENCY_ANALYSIS_GUIDE.md) for details.

## 📊 Understanding Scores

Your results show:

- **🟢 80+**: Healthy - Good state, continue monitoring
- **🟡 50-79**: Monitor - Review regularly for changes
- **🔴 ~50**: Needs attention - Consider support or migration

## 🎯 Common Scenarios

### Evaluate a New Library

```bash
oss-guard check library-name --verbose
```

The `--verbose` flag shows all metrics and detailed signals.

### Check Your Project's Dependencies

```bash
cd /path/to/project
oss-guard check --include-lock --verbose
```

### Use Different Scoring Profiles

Recalculate scores based on your priorities:

```bash
# Security-focused evaluation
oss-guard check requests --profile security_first

# Contributor-experience focused
oss-guard check requests --profile contributor_experience

# Long-term stability focused
oss-guard check requests --profile long_term_stability
```

### Bypass Cache (Real-time Analysis)

```bash
oss-guard check requests --no-cache
```

## 💡 Key Concepts

### When Do I Need a GitHub Token?

For most analysis of popular packages, you don't need a GitHub token—OSS Sustain Guard uses **pre-computed caches** for instant results. You'll only need `GITHUB_TOKEN` if:

- Analyzing a new/uncommon package not in the cache
- Analyzing frequently and hitting rate limits

If you see "GitHub token not found" error, see [Troubleshooting & FAQ](TROUBLESHOOTING_FAQ.md) for setup.

### CHAOSS-Aligned Metrics

All metrics follow [CHAOSS (Community Health Analytics in Open Source Software)](https://chaoss.community) standards. See [CHAOSS Metrics Alignment](CHAOSS_METRICS_ALIGNMENT_VALIDATION.md) for details.

## 📚 Next Steps

- **Analyze your project's dependencies**: [Dependency Analysis](DEPENDENCY_ANALYSIS_GUIDE.md)
- **Analyze entire projects**: [Recursive Scanning](RECURSIVE_SCANNING_GUIDE.md)
- **Track changes over time**: [Time Series Analysis](TREND_ANALYSIS_GUIDE.md)
- **Exclude packages**: [Exclude Configuration](EXCLUDE_PACKAGES_GUIDE.md)
- **Automate in CI/CD**: [GitHub Actions](GITHUB_ACTIONS_GUIDE.md)
- **Find projects to support**: [Gratitude Vending Machine](GRATITUDE_VENDING_MACHINE.md)
- **Need help?**: [Troubleshooting & FAQ](TROUBLESHOOTING_FAQ.md)

| Metric | Description |
|--------|-------------|
| **Contributor Redundancy** | Distribution of contributions (lower = single-maintainer risk) |
| **Recent Activity** | Project's current activity level |
| **Release Rhythm** | Release frequency and consistency |
| **Maintainer Retention** | Stability of maintainers |
| **Issue Responsiveness** | Speed of issue response |

## 🔧 Useful Options

### View Detailed Information

```bash
oss-guard check requests --verbose
```

### Use a Different Scoring Profile

Recalculate scores based on different priorities:

```bash
# Prioritize security
oss-guard check requests --profile security_first

# Prioritize contributor experience
oss-guard check requests --profile contributor_experience

# Prioritize long-term stability
oss-guard check requests --profile long_term_stability
```

### Bypass Cache (Real-time Analysis)

```bash
oss-guard check requests --no-cache
```

## 📌 Next Steps

- **Configure Exclusions**: [Exclude Configuration Guide](EXCLUDE_PACKAGES_GUIDE.md) - Exclude internal packages
- **Scan Entire Project**: [Recursive Scanning Guide](RECURSIVE_SCANNING_GUIDE.md) - Scan monorepos and complex projects
- **Track Changes**: [Time Series Analysis Guide](TREND_ANALYSIS_GUIDE.md) - Monitor dependency health over time
- **CI/CD Integration**: [GitHub Actions Guide](GITHUB_ACTIONS_GUIDE.md) - Integrate with your workflow
- **Discover Projects to Support**: [Gratitude Vending Machine](GRATITUDE_VENDING_MACHINE.md) - Find projects that need support

## ❓ Questions or Issues?

For help, see [Troubleshooting & FAQ](TROUBLESHOOTING_FAQ.md).

## 🌍 Supported Languages

- Python (PyPI)
- JavaScript / TypeScript (npm)
- Rust (Cargo)
- Java (Maven)
- PHP (Packagist)
- Ruby (RubyGems)
- C# / .NET (NuGet)
- Go (Go Modules)
- Kotlin

## 💡 Key Concepts

### When Do I Need a GitHub Token?

For most popular packages, OSS Sustain Guard uses **pre-computed cached data** without needing a token. You'll only need `GITHUB_TOKEN` if analyzing new packages not in the cache or if you hit GitHub API rate limits. See [Troubleshooting & FAQ](TROUBLESHOOTING_FAQ.md) for details.

### CHAOSS Alignment

All metrics are based on [CHAOSS (Community Health Analytics in Open Source Software)](https://chaoss.community) best practices. See [CHAOSS Metrics Alignment](CHAOSS_METRICS_ALIGNMENT_VALIDATION.md) for details.
