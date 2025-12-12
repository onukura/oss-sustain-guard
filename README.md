# OSS Sustain Guard

[![Test & Coverage](https://github.com/onukura/oss-sustain-guard/actions/workflows/test.yml/badge.svg)](https://github.com/onukura/oss-sustain-guard/actions/workflows/test.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/oss-sustain-guard)](https://pypi.org/project/oss-sustain-guard/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Multi-language package sustainability analyzer** - Evaluate your dependencies' health with 9 key metrics including Bus Factor, Maintainer Activity, and Security Posture.

✨ **No API tokens required** - Fast, cache-based evaluation for Python, JavaScript, Go, Rust, PHP, Java, C#, and Ruby packages.

> 📌 **Important Notes:**
>
> - For **cached packages**: Instant evaluation without API calls
> - For **uncached packages**: GitHub API queries are required (requires `GITHUB_TOKEN` environment variable)
> - **GitHub rate limiting**: GitHub API has rate limits; cached data helps avoid hitting these limits
> - **GitHub unavailable packages**: Cannot be evaluated (non-GitHub repositories or private packages not accessible via GitHub API)
> - **SSL verification**: Use `--insecure` flag to disable SSL verification for development/testing only
> - **Package resolution**: If a package cannot be resolved to a GitHub repository, it will be skipped with a notification

## 💡 Project Philosophy

OSS Sustain Guard is designed to spark thoughtful conversations about open-source sustainability, not to pass judgment on projects. Our mission is to **raise awareness** about the challenges maintainers face and encourage the community to think together about how we can better support the open-source ecosystem.

We believe that:

- 🌱 **Sustainability matters** - Open-source projects need ongoing support to thrive
- 🤝 **Community support is essential** - For community-driven projects, we highlight funding opportunities to help users give back
- 📊 **Transparency helps everyone** - By providing objective metrics, we help maintainers and users make informed decisions
- 🎯 **Respectful evaluation** - We distinguish between corporate-backed and community-driven projects, recognizing their different sustainability models
- 💝 **Supporting maintainers** - When available, we display funding links for community projects to encourage direct support

This tool is meant to be a conversation starter about OSS sustainability, not a judgment. Every project has unique circumstances, and metrics are just one part of the story.

## 🎯 Key Features

- **21 Sustainability Metrics** - Comprehensive evaluation across maintainer health, development activity, community engagement, project maturity, and security
- **Optional Dependents Analysis** - Downstream dependency metrics (informational, not affecting total score)
- **5 CHAOSS-Aligned Models** - Risk, Sustainability, Community Engagement, Project Maturity, and Contributor Experience
- **Category-Weighted Scoring** - Balanced 0-100 scale evaluation across 5 key sustainability dimensions
- **Multi-Language Support** - Python, JavaScript, Go, Rust, PHP, Java, C#, Ruby
- **Community Support Awareness** - Displays funding links for community-driven projects
- **Fast & Cache-Based** - Pre-computed data for instant results
- **CI/CD Integration** - GitHub Actions, Pre-commit hooks
- **Zero Configuration** - Works out of the box

## 🚀 Quick Start

```bash
# Install
pip install oss-sustain-guard

# Check a package
oss-guard check requests

# Check multiple ecosystems
oss-guard check python:django npm:react rust:tokio

# Auto-detect from lock files
oss-guard check --include-lock
```

![Demo](./docs/assets/demo01..png)

## 📖 Usage

### Command Line

```bash
# Single package
oss-guard check flask

# Multiple packages
oss-guard check django requests numpy

# From requirements.txt
oss-guard check requirements.txt

# Verbose output
oss-guard check flask -v

# Clear cache
oss-guard check --clear-cache
```

**Community Funding Support:**

When analyzing community-driven projects, OSS Sustain Guard displays funding links to help you support the maintainers:

```bash
$ oss-guard check go:gorm

OSS Sustain Guard Report
┌──────────────┬────────┬──────────────┬────────────────────────────────────────────┐
│ Package      │ Score  │ Health Status│ Details                                    │
├──────────────┼────────┼──────────────┼────────────────────────────────────────────┤
│ go-gorm/gorm │ 89/100 │ Healthy      │ Analyzed: Healthy: 58 active contributors. │
└──────────────┴────────┴──────────────┴────────────────────────────────────────────┘

💝 go-gorm/gorm is a community-driven project. Consider supporting:
   • GITHUB: https://github.com/jinzhu
   • PATREON: https://patreon.com/jinzhu
   • OPEN_COLLECTIVE: https://opencollective.com/gorm
```

Corporate-backed projects (e.g., maintained by organizations) do not display funding links, as they typically have different sustainability models.

### Multi-Language Support

```bash
# Specify ecosystem with prefix
oss-guard check npm:react              # JavaScript
oss-guard check rust:tokio             # Rust
oss-guard check ruby:rails             # Ruby
oss-guard check go:github.com/gin-gonic/gin  # Go
oss-guard check php:symfony/console    # PHP
oss-guard check java:com.google.guava:guava  # Java
oss-guard check csharp:Newtonsoft.Json # C#

# Mix multiple ecosystems
oss-guard check requests npm:express rust:tokio

# Auto-detect from manifest files in current directory
oss-guard check

# Analyze a specific manifest file
oss-guard check --manifest package.json
oss-guard check --manifest requirements.txt
oss-guard check -m Cargo.toml

# Auto-detect from specific directory
oss-guard check --root-dir /path/to/project

# Auto-detect with lock files
oss-guard check --include-lock

# Recursively scan subdirectories (great for monorepos!)
oss-guard check --recursive

# Limit recursion depth
oss-guard check --recursive --depth 2

# Recursive scan with lock files
oss-guard check --recursive --include-lock --depth 3
```

**Recursive Scanning for Monorepos:**

Perfect for analyzing complex project structures with multiple subprojects:

```bash
# Project structure:
# monorepo/
#   ├── frontend/package.json
#   ├── backend/requirements.txt
#   └── services/rust-service/Cargo.toml

cd monorepo
oss-guard check --recursive        # Scan all subdirectories
oss-guard check --recursive --depth 2  # Limit to 2 levels deep
```

**Note:** Common directories like `node_modules/`, `venv/`, `.git/`, etc. are automatically excluded. You can customize exclusions in `.oss-sustain-guard.toml`:

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = ["custom_cache"]  # Additional patterns
use_defaults = true          # Use built-in exclusions
use_gitignore = true         # Respect .gitignore
```

See [Recursive Scanning Guide](./docs/RECURSIVE_SCANNING_GUIDE.md) for detailed examples.

**Supported Ecosystems:**

| Ecosystem | Format | Example |
|-----------|--------|---------|
| Python | `python:package` or `package` | `requests`, `python:flask` |
| JavaScript | `npm:package`, `js:package` | `npm:react`, `js:vue` |
| Go | `go:path` | `go:github.com/golang/go` |
| Ruby | `ruby:gem`, `gem:gem` | `ruby:rails`, `gem:devise` |
| Rust | `rust:crate` | `rust:tokio` |
| PHP | `php:vendor/package` | `php:symfony/console` |
| Java | `java:groupId:artifactId` | `java:com.google.guava:guava` |
| C# | `csharp:package`, `nuget:package` | `csharp:Serilog` |

### GitHub Actions

Add to your workflow:

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    packages: 'requests django'
    verbose: 'true'
```

Or auto-detect from lock files:

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    include-lock: 'true'
```

**Multi-language example:**

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    packages: 'requests npm:express ruby:rails rust:tokio'
    verbose: 'true'
```

See [GitHub Actions Guide](./docs/GITHUB_ACTIONS_GUIDE.md) for details.

### Pre-Commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/onukura/oss-sustain-guard
    rev: 'main'
    hooks:
      - id: oss-sustain-guard
        args: ['--include-lock']
```

Install and run:

```bash
pip install pre-commit
pre-commit install
pre-commit run oss-sustain-guard --all-files
```

See [Pre-Commit Integration Guide](./docs/PRE_COMMIT_INTEGRATION.md) for details.

## 🎁 Gratitude Vending Machine

**Support the maintainers who keep your dependencies running!**

The Gratitude Vending Machine is a unique feature that helps you discover and support community-driven OSS projects that need your help the most. It analyzes your dependencies and prioritizes projects based on:

- **Impact & dependency load** - How many projects depend on it
- **Maintainer capacity** - Low bus factor, high review backlog
- **Community support** - Whether funding links are available

### How to Use

```bash
# Discover top 3 projects that would appreciate your support
oss-guard gratitude

# See top 5 projects
oss-guard gratitude --top 5
```

**Interactive Experience:**

1. **Discover** - Shows top community-driven projects ranked by support priority
2. **Learn** - Displays health scores, contributor metrics, and impact
3. **Support** - Opens funding links (GitHub Sponsors, Open Collective, Patreon, etc.)
4. **Give back** - Make a direct contribution with one click

**Example Output:**

```text
🎁 Gratitude Vending Machine
Loading community projects that could use your support...

Top 3 projects that would appreciate your support:

1. rich (python)
   Repository: https://github.com/Textualize/rich
   Health Score: 77/100 (Monitor)
   Contributor Redundancy: 10/20
   Maintainer Drain: 15/15
   💝 Support options:
      • GITHUB: https://github.com/willmcgugan

2. pytest (python)
   Repository: https://github.com/pytest-dev/pytest
   Health Score: 78/100 (Monitor)
   Contributor Redundancy: 15/20
   Maintainer Drain: 15/15
   💝 Support options:
      • GITHUB: https://github.com/pytest-dev
      • TIDELIFT: https://tidelift.com/funding/github/pypi/pytest
      • OPEN_COLLECTIVE: https://opencollective.com/pytest

Would you like to open a funding link?
Enter project number (1-3) to open funding link, or 'q' to quit:
```

**What makes this special:**

- 🎯 **Smart prioritization** - Not just popular projects, but ones that truly need support
- 🤝 **Community focus** - Only shows community-driven projects (excludes corporate-backed)
- 💝 **One-click support** - Opens funding links directly in your browser
- 🌱 **Awareness** - Helps you understand the sustainability challenges maintainers face
- 📊 **Transparency** - Shows health metrics so you can make informed decisions

**Philosophy:**

The Gratitude Vending Machine embodies our belief that open-source sustainability requires both awareness and action. By making it easy to discover and support the maintainers who keep your dependencies running, we hope to create a more sustainable OSS ecosystem—one small contribution at a time.

## 💾 Cache Management

Caches analysis data locally (default: `~/.cache/oss-sustain-guard`, 7-day TTL).

```bash
# Custom cache directory
oss-guard check requests --cache-dir /path/to/cache

# Custom TTL (seconds)
oss-guard check requests --cache-ttl 86400

# Disable cache
oss-guard check requests --no-cache

# Clear cache
oss-guard check --clear-cache

# View cache statistics
oss-guard cache-stats
```

Configure in `.oss-sustain-guard.toml`:

```toml
[tool.oss-sustain-guard.cache]
directory = "~/.cache/oss-sustain-guard"
ttl_seconds = 604800  # 7 days
enabled = true
```

## 📊 Score Explanation

Scores are evaluated in the range of 0-100 using a **category-weighted approach** across 5 sustainability dimensions:

- **80-100**: 🟢 **Excellent** - Healthy project
- **50-79**: 🟡 **Monitor** - Areas to consider supporting
- **0-49**: 🔴 **Needs Attention** - Needs support and improvement

### Scoring Profiles

OSS Sustain Guard supports **multiple scoring profiles** to evaluate projects based on different priorities:

- **🔵 Balanced** (default) - Balanced view across all dimensions
- **🔒 Security First** - Prioritizes security and risk mitigation (40% security weight)
- **🤝 Contributor Experience** - Focuses on community engagement (40% community weight)
- **🌱 Long-term Stability** - Emphasizes maintainer health (35% maintainer weight)

See [Scoring Profiles Guide](./docs/SCORING_PROFILES_GUIDE.md) for detailed comparison and usage examples.

### Scoring Categories (Balanced Profile)

| Category | Weight | Focus Areas |
|----------|--------|-------------|
| **Maintainer Health** | 25% | Contributor diversity, retention, organizational diversity |
| **Development Activity** | 20% | Release rhythm, recent activity, build health, PR resolution |
| **Community Engagement** | 20% | Issue responsiveness, PR acceptance, review quality |
| **Project Maturity** | 15% | Documentation, governance, popularity, adoption |
| **Security & Funding** | 20% | Security posture, financial sustainability |

### All 21 Sustainability Metrics

#### Maintainer Health (25%)

- **Contributor Redundancy** (20pt) - Single maintainer dependency risk
- **Maintainer Retention** (10pt) - Active maintainer continuity
- **Contributor Attraction** (10pt) - New contributor onboarding (last 6 months)
- **Contributor Retention** (10pt) - Repeat contributor engagement
- **Organizational Diversity** (10pt) - Multi-organization contribution

#### Development Activity (20%)

- **Recent Activity** (20pt) - Repository activity recency
- **Release Rhythm** (10pt) - Release frequency and consistency
- **Build Health** (5pt) - CI/CD test status
- **Change Request Resolution** (10pt) - Average PR merge time

#### Community Engagement (20%)

- **Issue Responsiveness** (5pt) - Issue response time
- **PR Acceptance Ratio** (10pt) - Pull request acceptance rate
- **PR Responsiveness** (5pt) - Time to first PR response
- **Review Health** (10pt) - PR review quality and speed
- **Issue Resolution Duration** (10pt) - Average time to close issues

#### Project Maturity (15%)

- **Documentation Presence** (10pt) - README, CONTRIBUTING, Wiki, docs
- **Code of Conduct** (5pt) - Community guidelines presence
- **License Clarity** (5pt) - OSI-approved license status
- **Project Popularity** (10pt) - Stars, watchers, community interest
- **Fork Activity** (5pt) - Fork count and recent activity

#### Optional Informational Metrics

These metrics provide additional insights but do not affect the total score (0-100):

- **Downstream Dependents** - Shows how many packages depend on this package (requires Libraries.io API key + `--enable-dependents` flag)

#### Security & Funding (20%)

- **Security Signals** (15pt) - Security policy, vulnerability alerts
- **Funding Signals** (10pt) - Sponsorship/funding availability

**Note on Funding Metric:** Scored differently by project type:

- **Community-driven projects** (max 10pt): Funding is critical for sustainability
- **Corporate-backed projects** (max 5pt): Corporate backing provides sustainability

### CHAOSS-Aligned Metric Models

Aggregated views for holistic assessment:

1. **Risk Model** - Project stability and security risks
2. **Sustainability Model** - Long-term viability indicators
3. **Community Engagement Model** - Community health and responsiveness
4. **Project Maturity Model** - Documentation, governance, adoption
5. **Contributor Experience Model** - PR handling and contributor satisfaction

## ⚙️ Configuration

### Exclude Packages

Create `.oss-sustain-guard.toml`:

```toml
[tool.oss-sustain-guard]
exclude = ["internal-package", "legacy-dependency"]
```

See [Exclude Packages Guide](./docs/EXCLUDE_PACKAGES_GUIDE.md) for details.

### GitHub Token (Required for Uncached Packages)

When analyzing packages not in the cache, the tool requires GitHub API access. Set your GitHub token:

```bash
# Using Personal Access Token
export GITHUB_TOKEN=ghp_your_personal_access_token

# Then run the analysis
oss-guard check requests django
```

**When is GITHUB_TOKEN needed?**

- ✅ **Not needed**: Packages already in cache (pre-computed data)
- ❌ **Required**: First-time analysis of packages not in the cache

**Getting a GitHub Token:**

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Create a token with `public_repo` scope (read-only access to public repositories)
3. Set environment variable: `export GITHUB_TOKEN=your_token`

**Example with uncached package:**

```bash
# This package might not be in cache and will require GITHUB_TOKEN
$ export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
$ oss-guard check my-private-package
```

### Libraries.io API (Optional - Enhanced Dependents Analysis)

For enhanced dependency analysis, you can optionally configure a free Libraries.io API key to get **downstream dependents count** - showing how many other packages depend on the packages you're analyzing.

**⚠️ Important:** Due to API rate limits (10,000 requests/month), this feature is **opt-in** and requires the `--enable-dependents` flag.

```bash
# 1. Get free API key from https://libraries.io/api
export LIBRARIESIO_API_KEY=your_api_key

# 2. Enable dependents analysis with the flag
oss-guard check requests --enable-dependents

# Short form
oss-guard check requests -D
```

**What is Dependents Analysis?**

- Shows how many other packages depend on this package (downstream dependencies)
- Indicates ecosystem importance and adoption
- Helps identify critical infrastructure packages
- **Informational only** - does not affect total score (0-100) to ensure consistency
- **Opt-in only** - must use `--enable-dependents` flag to avoid rate limits

**Getting a Libraries.io API Key:**

1. Sign up at [libraries.io](https://libraries.io)
2. Go to [Account Settings → API Key](https://libraries.io/account)
3. Copy your free API key
4. Set environment variable: `export LIBRARIESIO_API_KEY=your_api_key`

**Benefits:**

- ✅ Free API (10,000 requests/month)
- ✅ Multi-language support (Python, JavaScript, Rust, Go, PHP, Java, C#, Ruby)
- ✅ Shows adoption trends and ecosystem importance
- ✅ Helps identify critical infrastructure packages

**Example with dependents analysis:**

```bash
$ export LIBRARIESIO_API_KEY=your_key
$ oss-guard check requests --enable-dependents

# Output will include "Downstream Dependents" metric (informational):
# 📦 500,000+ packages depend on this (150,000 repos)
# Critical infrastructure: Essential to ecosystem
#
# Note: This metric is displayed for information only and does not affect
# the total score (0-100), ensuring consistent scoring whether or not
# the --enable-dependents flag is used.
```

**Why is it informational only?**

To ensure fair and consistent scoring:

- ✅ **Same score for same project** - Total score (0-100) remains identical whether or not `--enable-dependents` is used
- ✅ **No API dependency** - Users without Libraries.io API key get complete, accurate scores
- ✅ **Bonus insight** - When enabled, provides valuable ecosystem importance information without penalizing projects that don't enable it

**Without the flag:**

- The tool works normally with all other 20+ metrics
- Only the "Downstream Dependents" metric is skipped
- No error messages - seamlessly handles missing API key

### SSL Verification

For development/testing, you can disable SSL verification:

```bash
oss-guard check requests --insecure
```

> ⚠️ **Warning**: Only use `--insecure` in development environments. Never disable SSL verification in production.

## 🤝 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup, testing, code style, and architecture documentation.

## 📝 Documentation

- [Scoring Profiles Guide](./docs/SCORING_PROFILES_GUIDE.md) - Different evaluation perspectives
- [Database Schema](./docs/DATABASE_SCHEMA.md) - JSON database format
- [Pre-Commit Integration](./docs/PRE_COMMIT_INTEGRATION.md) - Hook configuration
- [GitHub Actions Guide](./docs/GITHUB_ACTIONS_GUIDE.md) - CI/CD setup
- [Exclude Packages Guide](./docs/EXCLUDE_PACKAGES_GUIDE.md) - Package filtering

## 📄 License

MIT License
