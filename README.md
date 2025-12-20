# OSS Sustain Guard

[![Test & Coverage](https://github.com/onukura/oss-sustain-guard/actions/workflows/test.yml/badge.svg)](https://github.com/onukura/oss-sustain-guard/actions/workflows/test.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/oss-sustain-guard)](https://pypi.org/project/oss-sustain-guard/)
[![PyPI - Version](https://img.shields.io/pypi/v/oss-sustain-guard)](https://pypi.org/project/oss-sustain-guard/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

![demo](./docs/assets/demo01.png)

**Multi-language package sustainability analyzer** - Evaluate your dependencies' health with 21 metrics including Contributor Redundancy, Maintainer Retention, and Security Signals.

✨ **Globally Distributed Cache** - Instant results via Cloudflare KV with local fallback caching.

> 📌 **Quick Notes:**
>
> - **Instant results** - Popular packages served from global Cloudflare KV cache (no API calls needed)
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

- **21 Sustainability Metrics** - Comprehensive evaluation across maintainer health, development activity, community engagement, project maturity, and security
- **Optional Dependents Analysis** - Downstream dependency metrics (informational, not affecting total score)
- **5 CHAOSS-Aligned Models** - Risk, Sustainability, Community Engagement, Project Maturity, and Contributor Experience
- **Category-Weighted Scoring** - Balanced 0-100 scale evaluation across 5 key sustainability dimensions
- **Multi-Language Support** - Python, JavaScript, Go, Rust, PHP, Java, Kotlin, C#, Ruby
- **Time Series Analysis** - Track package health trends over time, compare snapshots, generate reports
- **Community Support Awareness** - Displays funding links for community-driven projects
- **Globally Distributed Cache** - Cloudflare KV-based data delivery with local user cache fallback
- **CI/CD Integration** - GitHub Actions, Pre-commit hooks
- **Zero Configuration** - Works out of the box

## 🚀 Quick Start

```bash
# Install
pip install oss-sustain-guard

# Check a single package
oss-guard check requests

# Check multiple packages (auto-detect language)
oss-guard check django flask numpy

# Multi-language support
oss-guard check python:requests npm:react rust:tokio

# Auto-detect from manifest files
oss-guard check --include-lock

# Scan recursively (great for monorepos)
oss-guard check --recursive
```

## 📚 Documentation

For detailed usage, configuration, and features, see our documentation site:

- **[Getting Started](https://onukura.github.io/oss-sustain-guard/GETTING_STARTED/)** - Installation and basic usage
- **[Scoring Profiles](https://onukura.github.io/oss-sustain-guard/SCORING_PROFILES_GUIDE/)** - Different evaluation perspectives
- **[Trend Analysis](https://onukura.github.io/oss-sustain-guard/TREND_ANALYSIS_GUIDE/)** - Track package health over time
- **[GitHub Actions Integration](https://onukura.github.io/oss-sustain-guard/GITHUB_ACTIONS_GUIDE/)** - CI/CD setup
- **[Pre-Commit Hooks](https://onukura.github.io/oss-sustain-guard/PRE_COMMIT_INTEGRATION/)** - Automated checks
- **[Exclude Packages](https://onukura.github.io/oss-sustain-guard/EXCLUDE_PACKAGES_GUIDE/)** - Configuration
- **[FAQ](https://onukura.github.io/oss-sustain-guard/TROUBLESHOOTING_FAQ/)** - Common questions

### Supported Ecosystems

Python, JavaScript, Go, Rust, PHP, Java, Kotlin, C#, Ruby

See [Getting Started](https://onukura.github.io/oss-sustain-guard/GETTING_STARTED/) for ecosystem-specific syntax.

### 21 Sustainability Metrics

Evaluated across 5 categories:

- **Maintainer Health** (25%) - Contributor diversity and retention
- **Development Activity** (20%) - Release rhythm and recent activity
- **Community Engagement** (20%) - Issue/PR responsiveness
- **Project Maturity** (15%) - Documentation and governance
- **Security & Funding** (20%) - Security posture and sustainability

**Score interpretation:** 80-100 (Healthy) | 50-79 (Monitor) | 0-49 (Needs Attention)

See [Database Schema](https://onukura.github.io/oss-sustain-guard/DATABASE_SCHEMA/) for complete metric details.

### Special Features

- **🎁 Gratitude Vending Machine** - Discover community projects that need support
  ```bash
  oss-guard gratitude --top 5
  ```

- **📊 Trend Analysis** - Track package health evolution
  ```bash
  oss-guard trend requests
  oss-guard compare requests 2025-12-11 2025-12-12
  ```

- **💝 Community Funding Links** - Auto-displays funding options for community-driven projects

See [Trend Analysis Guide](https://onukura.github.io/oss-sustain-guard/TREND_ANALYSIS_GUIDE/) for details.

## 🤝 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup, testing, code style, and architecture documentation.

## 📝 Documentation

- [Scoring Profiles Guide](./docs/SCORING_PROFILES_GUIDE.md) - Different evaluation perspectives
- [Trend Analysis Guide](./docs/TREND_ANALYSIS_GUIDE.md) - Time series analysis and historical comparison
- [Database Schema](./docs/DATABASE_SCHEMA.md) - JSON database format
- [Pre-Commit Integration](./docs/PRE_COMMIT_INTEGRATION.md) - Hook configuration
- [GitHub Actions Guide](./docs/GITHUB_ACTIONS_GUIDE.md) - CI/CD setup
- [Exclude Packages Guide](./docs/EXCLUDE_PACKAGES_GUIDE.md) - Package filtering

## 📄 License

MIT License
