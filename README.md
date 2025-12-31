# OSS Sustain Guard

[![Test & Coverage](https://github.com/onukura/oss-sustain-guard/actions/workflows/test.yml/badge.svg)](https://github.com/onukura/oss-sustain-guard/actions/workflows/test.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/oss-sustain-guard)](https://pypi.org/project/oss-sustain-guard/)
[![PyPI - Version](https://img.shields.io/pypi/v/oss-sustain-guard)](https://pypi.org/project/oss-sustain-guard/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

![demo](./docs/assets/demo01.png)

**Multi-language package sustainability analyzer** - Evaluate your dependencies' health with 24 metrics including Contributor Redundancy, Maintainer Retention, and Security Signals.

> 📌 **Quick Notes:**
>
> - **Local caching** - Popular packages served from efficient local cache for faster results
> - **SSL verification** - Use `--insecure` flag to disable SSL verification for development/testing only
> - **Package resolution** - If a package cannot be resolved to a GitHub repository, it will be skipped with a notification
> - **Full documentation** - https://onukura.github.io/oss-sustain-guard/

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

- **24 Sustainability Metrics** - Comprehensive evaluation across maintainer health, development activity, community engagement, project maturity, and security (all metrics scored 0-10)
- **Optional Dependents Analysis** - Downstream dependency metrics (informational, not affecting total score)
- **5 CHAOSS-Aligned Models** - Risk, Sustainability, Community Engagement, Project Maturity, and Contributor Experience
- **Metric-Weighted Scoring** - Configurable scoring profiles with integer weights per metric, normalized to 0-100 scale
- **Multi-Language Support** - Python, JavaScript, Go, Rust, PHP, Java, Kotlin, C#, Ruby
- **Community Support Awareness** - Displays funding links for community-driven projects
- **Local Caching** - Efficient local cache for faster repeated checks
- **CI/CD Integration** - GitHub Actions, Pre-commit hooks
- **Zero Configuration** - Works out of the box

## 🚀 Quick Start

```bash
# Install
pip install oss-sustain-guard

# Set GitHub token (required for all package analysis)
export GITHUB_TOKEN='your_token_here'  # Get from: https://github.com/settings/tokens/new

# Check a single package
os4g check requests

# Check multiple packages (auto-detect language)
os4g check django flask numpy

# Multi-language support
os4g check python:requests npm:react rust:tokio r:ggplot2 haskell:text swift:apple/swift-nio

# Auto-detect from manifest files
os4g check --include-lock

# Scan recursively (great for monorepos)
os4g check --recursive
```

## 📚 Documentation

For detailed usage, configuration, and features, see our documentation site:

- **[Getting Started](https://onukura.github.io/oss-sustain-guard/GETTING_STARTED/)** - Installation and basic usage
- **[Scoring Profiles](https://onukura.github.io/oss-sustain-guard/SCORING_PROFILES_GUIDE/)** - Different evaluation perspectives
- **[GitHub Actions Integration](https://onukura.github.io/oss-sustain-guard/GITHUB_ACTIONS_GUIDE/)** - CI/CD setup
- **[Pre-Commit Hooks](https://onukura.github.io/oss-sustain-guard/PRE_COMMIT_INTEGRATION/)** - Automated checks
- **[Exclude Packages](https://onukura.github.io/oss-sustain-guard/EXCLUDE_PACKAGES_GUIDE/)** - Configuration
- **[FAQ](https://onukura.github.io/oss-sustain-guard/TROUBLESHOOTING_FAQ/)** - Common questions

### Supported Ecosystems

Python, JavaScript, Go, Rust, PHP, Java, Kotlin, C#, Ruby, R, Haskell, Swift, Dart, Elixir, Perl

See [Getting Started](https://onukura.github.io/oss-sustain-guard/GETTING_STARTED/) for ecosystem-specific syntax.

### 24 Sustainability Metrics

Evaluated across 5 categories:

- **Maintainer Health** (25%) - Contributor diversity and retention
- **Development Activity** (20%) - Release rhythm and recent activity
- **Community Engagement** (20%) - Issue/PR responsiveness
- **Project Maturity** (15%) - Documentation and governance
- **Security & Funding** (20%) - Security posture and sustainability

**Score interpretation:** 80-100 (Healthy) | 50-79 (Monitor) | 0-49 (Needs Attention)

### Custom Scoring Profiles

You can override scoring profiles via `.oss-sustain-guard.toml`, `pyproject.toml`, or a dedicated TOML file with `--profile-file`.

Profile weights must include every metric and use integer values ≥ 1.

**Method 1: Configuration File (Recommended)**

```toml
# .oss-sustain-guard.toml
[tool.oss-sustain-guard.profiles.custom_security]
name = "Custom Security"
description = "Security-focused profile with higher signal weight."

[tool.oss-sustain-guard.profiles.custom_security.weights]
"Contributor Redundancy" = 2
"Maintainer Retention" = 2
"Contributor Attraction" = 1
"Contributor Retention" = 1
"Organizational Diversity" = 2
"Maintainer Load Distribution" = 1
"Recent Activity" = 2
"Release Rhythm" = 2
"Build Health" = 3
"Change Request Resolution" = 1
"Issue Responsiveness" = 2
"PR Acceptance Ratio" = 1
"Review Health" = 2
"Issue Resolution Duration" = 1
"Stale Issue Ratio" = 1
"PR Merge Speed" = 2
"Documentation Presence" = 2
"Code of Conduct" = 1
"License Clarity" = 2
"Project Popularity" = 1
"Fork Activity" = 1
"Security Signals" = 4
"Funding Signals" = 3
"PR Responsiveness" = 1
```

```bash
# Automatically uses profile from .oss-sustain-guard.toml
os4g check requests --profile custom_security
```

**Method 2: External Profile File**

```toml
# profiles.toml
[profiles.custom_security]
name = "Custom Security"
description = "Security-focused profile with higher signal weight."

[profiles.custom_security.weights]
"Contributor Redundancy" = 2
"Maintainer Retention" = 2
"Contributor Attraction" = 1
"Contributor Retention" = 1
"Organizational Diversity" = 2
"Maintainer Load Distribution" = 1
"Recent Activity" = 2
"Release Rhythm" = 2
"Build Health" = 3
"Change Request Resolution" = 1
"Issue Responsiveness" = 2
"PR Acceptance Ratio" = 1
"Review Health" = 2
"Issue Resolution Duration" = 1
"Stale Issue Ratio" = 1
"PR Merge Speed" = 2
"Documentation Presence" = 2
"Code of Conduct" = 1
"License Clarity" = 2
"Project Popularity" = 1
"Fork Activity" = 1
"Security Signals" = 4
"Funding Signals" = 3
"PR Responsiveness" = 1
```

```bash
os4g check requests --profile custom_security --profile-file profiles.toml
```

**Priority Order:**
1. `--profile-file` (if specified)
2. `.oss-sustain-guard.toml` (local config)
3. `pyproject.toml` (project-level config)

### Special Features

- **🎁 Gratitude Vending Machine** - Discover community projects that need support
  ```bash
  os4g gratitude --top 5
  ```

- **� Community Funding Links** - Auto-displays funding options for community-driven projects

## 🤝 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup, testing, code style, and architecture documentation.


## �📝 Documentation

- [Scoring Profiles Guide](./docs/SCORING_PROFILES_GUIDE.md) - Different evaluation perspectives

- [Pre-Commit Integration](./docs/PRE_COMMIT_INTEGRATION.md) - Hook configuration
- [GitHub Actions Guide](./docs/GITHUB_ACTIONS_GUIDE.md) - CI/CD setup
- [Exclude Packages Guide](./docs/EXCLUDE_PACKAGES_GUIDE.md) - Package filtering

## 📄 License

MIT License
