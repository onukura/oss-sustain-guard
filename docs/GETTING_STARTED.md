# Getting Started with OSS Sustain Guard

OSS Sustain Guard is a multi-language package sustainability analyzer that helps you understand the health of your dependencies. This guide shows you how to get started in just a few minutes.

## 📦 Installation

### Recommended: Isolated Environment (for non-Python developers)

If you're not a Python developer or want to avoid polluting your global Python environment, use one of these methods:

**Using pipx** (recommended for most users):

```bash
# Install pipx first (if not already installed)
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install oss-sustain-guard in isolated environment
pipx install oss-sustain-guard
```

**Using uv tool** (fastest option):

```bash
# Install uv first (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install oss-sustain-guard in isolated environment
uv tool install oss-sustain-guard
```

**Using Docker** (no Python installation needed):

```bash
# Pull the Docker image
docker pull ghcr.io/onukura/oss-sustain-guard:latest

# Run analysis (pass GitHub token as environment variable)
docker run --rm -e GITHUB_TOKEN=$GITHUB_TOKEN ghcr.io/onukura/oss-sustain-guard:latest check requests
```

**Using GitHub Actions** (for CI/CD):

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

See [GitHub Actions Guide](GITHUB_ACTIONS_GUIDE.md) for more details.

### Standard Installation (for Python developers)

Install directly from PyPI:

```bash
pip install oss-sustain-guard
```

## Quick Demo (No Token Needed)

Run the built-in demo data to see output instantly without network calls:

```bash
os4g check --demo
```

Demo data is a snapshot for illustration and may differ from current repository status.

## 🔐 GitHub and GitLab Token Setup (Required for Real-Time Analysis)

**OSS Sustain Guard requires a GitHub Personal Access Token for most real-time analyses; a GitLab token is only needed when the source is hosted on gitlab.com.**

This is needed because the tool fetches repository data directly from the host API to analyze:

- Contributor activity and redundancy
- Release patterns and commit history
- Issue/PR response times
- Security policies and funding information
- And more sustainability metrics

### GitHub Token Setup (3 steps)

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

### GitLab Token Setup (3 steps)

**1. Create a token:**
Visit [https://gitlab.com/-/user_settings/personal_access_tokens](https://gitlab.com/-/user_settings/personal_access_tokens) and create a token with `read_api` and `read_repository` scopes.

**2. Set the environment variable:**

```bash
# Linux/macOS
export GITLAB_TOKEN='your_token_here'

# Windows PowerShell
$env:GITLAB_TOKEN='your_token_here'

# Or add to .env file in your project
echo "GITLAB_TOKEN=your_token_here" > .env
```

**3. Verify it works:**

```bash
os4g check <package-hosted-on-gitlab>
```

> **Why is this required?**
>
> - Unauthenticated API access has very low rate limits
> - Authenticated requests get higher limits and consistent access
> - Package analysis requires multiple API calls per repository
>
> **Security:** Use minimal scopes (`public_repo`/`security_events` for GitHub, `read_api`/`read_repository` for GitLab). Never commit tokens to version control.

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

### Visualize Your Dependency Network

Create an interactive graph of your project's dependencies and their health scores:

```bash
# Generate an interactive HTML dependency graph
os4g graph package.json

# Export as JSON for integration with other tools
os4g graph Cargo.lock --output deps.json

# Expoer as HTML file
os4g graph uv.lock --output my-dependencies.html
```

See [Dependency Graph Visualization Guide](DEPENDENCY_GRAPH_VISUALIZATION.md) for more options.

### Track Sustainability Trends Over Time

Analyze how a repository's sustainability score changes over multiple time periods:

```bash
# Default: 6 monthly periods, 30-day windows
os4g trend requests

# Custom periods and intervals
os4g trend requests --periods 12 --interval weekly
os4g trend requests --periods 4 --interval quarterly --window-days 90

# Analyze recent history with daily granularity
os4g trend requests --periods 30 --interval daily --window-days 7
```

See [Trend Analysis Guide](TREND_ANALYSIS_GUIDE.md) for details on time-dependent metrics and visualization.

## 🔐 Token Setup (GitHub or GitLab)

**Required:** OSS Sustain Guard needs a token for the host where the repository lives.

### GitHub (github.com)

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

### GitLab (gitlab.com)

1. **Create a token:**

   - Visit: <https://gitlab.com/-/user_settings/personal_access_tokens>
   - Token name: `oss-sustain-guard`
   - Select scopes: ✓ `read_api`, ✓ `read_repository`
   - Click "Create personal access token" and **copy it immediately**

2. **Set the token:**

   **Linux/macOS:**

   ```bash
   export GITLAB_TOKEN='your_token_here'
   ```

   **Windows (PowerShell):**

   ```powershell
   $env:GITLAB_TOKEN='your_token_here'
   ```

   **Persistent (recommended):**

   Add to your `.env` file in your project directory:

   ```shell
   GITLAB_TOKEN=your_token_here
   ```

3. **Verify:**

   ```bash
   os4g check <package-hosted-on-gitlab>
   ```

### Why is a token needed?

The host API requires authentication for repository analysis. The token allows OSS Sustain Guard to:

- Query repository metadata (contributors, releases, issues)
- Access funding information
- Analyze project health metrics

**Rate Limits:** With a token, you get higher rate limits than unauthenticated requests. Local caching minimizes API calls.

**Security:** Your token is only stored locally and never sent anywhere except the host API.

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
- **Visualize Dependencies**: [Dependency Graph Visualization](DEPENDENCY_GRAPH_VISUALIZATION.md) - Interactive dependency health networks
- **Track Sustainability Trends**: [Trend Analysis Guide](TREND_ANALYSIS_GUIDE.md) - Monitor health changes over time
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
