# Getting Started with OSS Sustain Guard

OSS Sustain Guard is a multi-language package sustainability analyzer that helps you understand the health of your dependencies. This guide shows you how to get started in just a few minutes.

## 📦 Installation

Install easily from PyPI:

```bash
pip install oss-sustain-guard
```

## Quick Demo (No Token Needed)

Run the built-in demo data to see output instantly without network calls:

```bash
os4g check --demo
```

Demo data is a snapshot for illustration and may differ from current repository status.

## 🔐 GitHub Token Setup (Required for Real-Time Analysis)

**OSS Sustain Guard requires a GitHub Personal Access Token for real-time package analysis.**

This is needed because the tool fetches repository data directly from GitHub's API to analyze:

- Contributor activity and redundancy
- Release patterns and commit history
- Issue/PR response times
- Security policies and funding information
- And more sustainability metrics

### Quick Setup (3 steps)

**1. Create a token:**
Visit [https://github.com/settings/tokens/new](https://github.com/settings/tokens/new) and create a classic token with `public_repo` and `security_events` scopes.

**2. Set the environment variable:**

```bash
# Linux/macOS
export GITHUB_TOKEN='your_token_here'

# Windows PowerShell
$env:GITHUB_TOKEN='your_token_here'

# Or add to .env file in your project
echo "GITHUB_TOKEN=your_token_here" > .env
```

**3. Verify it works:**

```bash
os4g check requests
```

> **Why is this required?**
>
> - GitHub's unauthenticated API has very low rate limits (60 requests/hour)
> - Authenticated requests get 5,000 requests/hour
> - Package analysis requires multiple API calls per repository
>
> **Security:** The token only needs `public_repo` and `security_events` scopes for public repositories. Never commit tokens to version control.

## 🚀 First Steps

### 1. Analyze Your Project's Dependencies (Most Common)

```bash
os4g check --include-lock
```

Automatically scans `requirements.txt`, `package.json`, `Cargo.toml`, and other manifest files to analyze all your project's dependencies.

Displays health scores of all packages with:

- **Health Score** (0-100): Overall sustainability rating
- **Health Status**: Healthy ✓, Monitor, or Needs support
- **Key Observations**: Important signals about each project

### 2. Check a Single Package

```bash
os4g check requests
```

Analyze a specific package in detail.

### 3. Check Multiple Packages

```bash
os4g check python:django npm:react rust:tokio
```

Mix any languages you use in one command.

### 4. Scan Entire Projects (Monorepos)

```bash
os4g check --recursive
```

Recursively finds and analyzes all dependencies in subdirectories.

See [Dependency Analysis Guide](DEPENDENCY_ANALYSIS_GUIDE.md) for details (experimental).

## 📊 Understanding Scores

Your results show:

- **🟢 80+**: Healthy - Good state, continue monitoring
- **🟡 50-79**: Monitor - Review regularly for changes
- **🔴 <50**: Needs support - Consider support or migration

## 🎯 Common Scenarios

### Evaluate a New Library

```bash
os4g check library-name --output-style detail
```

The `--output-style detail` (or `-o detail`) shows all metrics in a detailed table format.

For verbose logging (cache operations, metric reconstruction):

```bash
os4g check library-name -v
```

### Check Your Project's Dependencies

```bash
cd /path/to/project
os4g check --include-lock
```

### Use Different Scoring Profiles

Recalculate scores based on your priorities:

```bash
# Security-focused evaluation
os4g check requests --profile security_first

# Contributor-experience focused
os4g check requests --profile contributor_experience

# Long-term stability focused
os4g check requests --profile long_term_stability
```

### Bypass Cache (Real-time Analysis)

```bash
os4g check requests --no-cache
```

## 🔐 GitHub Token Setup

**Required:** OSS Sustain Guard requires a GitHub Personal Access Token to analyze repositories.

### Quick Setup (5 minutes)

1. **Create a token:**

   - Visit: <https://github.com/settings/tokens/new>
   - Token name: `oss-sustain-guard`
   - Select scopes: ✓ `public_repo`, ✓ `security_events`
   - Click "Generate token" and **copy it immediately**

2. **Set the token:**

   **Linux/macOS:**

   ```bash
   export GITHUB_TOKEN='your_token_here'
   ```

   **Windows (PowerShell):**

   ```powershell
   $env:GITHUB_TOKEN='your_token_here'
   ```

   **Persistent (recommended):**

   Add to your `.env` file in your project directory:

   ```shell
   GITHUB_TOKEN=your_token_here
   ```

3. **Verify:**

   ```bash
   os4g check requests
   ```

### Why is a token needed?

GitHub's API requires authentication for repository analysis. The token allows OSS Sustain Guard to:

- Query repository metadata (contributors, releases, issues)
- Access funding information
- Analyze project health metrics

**Rate Limits:** With a token, you get 5,000 requests/hour (vs 60 without). Local caching minimizes API calls.

**Security:** Your token is only stored locally and never sent anywhere except GitHub's API.

## 📚 Next Steps

- **Analyze your project's dependencies**: [Dependency Analysis](DEPENDENCY_ANALYSIS_GUIDE.md)
- **Analyze entire projects**: [Recursive Scanning](RECURSIVE_SCANNING_GUIDE.md)
- **Exclude packages**: [Exclude Configuration](EXCLUDE_PACKAGES_GUIDE.md)
- **Automate in CI/CD**: [GitHub Actions](GITHUB_ACTIONS_GUIDE.md)
- **Find projects to support**: [Gratitude Vending Machine](GRATITUDE_VENDING_MACHINE.md)
- **Need help?**: [Troubleshooting & FAQ](TROUBLESHOOTING_FAQ.md)

| Metric | Description |
| -------- | -------- |
| **Contributor Redundancy** | Distribution of contributions (lower = single-maintainer concentration) |
| **Recent Activity** | Project's current activity level |
| **Release Rhythm** | Release frequency and consistency |
| **Maintainer Retention** | Stability of maintainers |
| **Community Health** | Issue response time and responsiveness |

## 🔧 Useful Options

### Output Formats

Control how results are displayed:

```bash
# Compact output (one line per package, ideal for CI/CD)
os4g check requests -o compact

# Normal output (default, table with key observations)
os4g check requests -o normal

# Detail output (full metrics table with all signals)
os4g check requests -o detail
```

### Verbose Logging

Enable detailed logging for debugging and cache operations:

```bash
# Show cache operations and metric reconstruction
os4g check requests -v

# Combine with any output style
os4g check requests -v -o compact
os4g check requests -v -o detail
```

### Use a Different Scoring Profile

Recalculate scores based on different priorities:

```bash
# Prioritize security
os4g check requests --profile security_first

# Prioritize contributor experience
os4g check requests --profile contributor_experience

# Prioritize long-term stability
os4g check requests --profile long_term_stability
```

### Bypass Cache (Real-time Analysis)

```bash
os4g check requests --no-cache
```

## 📌 Next Steps

- **Configure Exclusions**: [Exclude Configuration Guide](EXCLUDE_PACKAGES_GUIDE.md) - Exclude internal packages
- **Scan Entire Project**: [Recursive Scanning Guide](RECURSIVE_SCANNING_GUIDE.md) - Scan monorepos and complex projects
- **Track Changes**: Monitor dependency health over time
- **CI/CD Integration**: [GitHub Actions Guide](GITHUB_ACTIONS_GUIDE.md) - Integrate with your workflow
- **Discover Projects to Support**: [Gratitude Vending Machine](GRATITUDE_VENDING_MACHINE.md) - Find projects that need support

## ❓ Questions or Issues?

For help, see [Troubleshooting & FAQ](TROUBLESHOOTING_FAQ.md).

## 🌍 Supported Languages

- Python (PyPI)
- JavaScript / TypeScript (npm)
- Rust (Cargo)
- Dart (pub.dev)
- Elixir (Hex.pm)
- Haskell (Hackage)
- Perl (CPAN)
- R (CRAN/renv)
- Swift (Swift Package Manager)
- Java (Maven)
- PHP (Packagist)
- Ruby (RubyGems)
- C# / .NET (NuGet)
- Go (Go Modules)
- Kotlin
