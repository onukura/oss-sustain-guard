# OSS Sustain Guard Documentation

OSS Sustain Guard is a multi-language package sustainability analyzer that helps you understand the health of your dependencies across ecosystems. The tool provides constructive insights about maintainer activity, community engagement, security posture, and funding signals so teams can make informed decisions about the projects they rely on.

![CLI demo showing an analyzed package](assets/demo01.png)

## 💡 Project Philosophy

OSS Sustain Guard is designed to spark thoughtful conversations about open-source sustainability, not to pass judgment on projects. Our mission is to **raise awareness** about the challenges maintainers face and encourage the community to think together about how we can better support the open-source ecosystem.

We believe that:

- 🌱 **Sustainability matters** - Open-source projects need ongoing support to thrive
- 🤝 **Community support is essential** - For community-driven projects, we highlight funding opportunities to help users give back
- 📊 **Transparency helps everyone** - By providing objective metrics, we help maintainers and users make informed decisions
- 🎯 **Respectful evaluation** - We distinguish between corporate-backed and community-driven projects, recognizing their different sustainability models
- 💝 **Supporting maintainers** - When available, we display funding links for community projects to encourage direct support

This tool is meant to be a conversation starter about OSS sustainability, not a judgment. Every project has unique circumstances, and metrics are just one part of the story.

## Why OSS Sustain Guard?

- **Globally distributed cache:** Data stored in Cloudflare KV provides instant results worldwide. GitHub token only needed for uncached packages.
- **Multi-ecosystem support:** Analyze packages from Python, JavaScript, Go, Rust, PHP, Java, Kotlin, C#, and Ruby in one command.
- **Actionable insights:** Metrics use empathetic language that encourages collaboration with maintainers rather than blame.
- **Time-travel friendly:** Historical snapshots enable trend analysis and comparisons between releases.
- **Sustainable by design:** Respects open-source sustainability models with funding awareness for community-driven projects.

## Key Features

### 🔍 Comprehensive Analysis

- **CHAOSS-aligned metrics** measuring contributor health, development activity, community engagement, and project maturity
- **Scoring profiles** optimized for different priorities (balanced, security-first, contributor-experience, long-term-stability)
- **Transparent scoring** with detailed breakdowns of each metric

### 📊 Time-Series & Trend Analysis

- **Track changes** in package health over time
- **Compare snapshots** between dates to identify improvement or degradation patterns
- **Historical data** from pre-computed archives for popular packages

### 🚀 Developer-Friendly Workflow

- **Manifest auto-detection** from `requirements.txt`, `package.json`, `Cargo.toml`, and other formats
- **Recursive scanning** for monorepos and multi-service projects
- **Exclude configuration** for internal or legacy dependencies
- **Integration-ready** for GitHub Actions, pre-commit hooks, and CI/CD pipelines

### 💝 Gratitude Vending Machine

- **Discover projects** that need your support most
- **See funding links** for community-driven projects
- **Make informed decisions** about where to contribute back

## Quick Navigation

### Just Getting Started?

👉 **[Getting Started Guide](GETTING_STARTED.md)** - Installation, first steps, and basic usage in 5 minutes

### Common Tasks

**Usage:**

- [Recursive Scanning](RECURSIVE_SCANNING_GUIDE.md) - Analyze entire projects and monorepos
- [Time Series Analysis](TREND_ANALYSIS_GUIDE.md) - Track health evolution and compare snapshots
- [Gratitude Vending Machine](GRATITUDE_VENDING_MACHINE.md) - Find projects to support

**Configuration:**

- [Exclude Configuration](EXCLUDE_PACKAGES_GUIDE.md) - Skip internal or legacy packages

**Scoring & Metrics:**

- [Scoring Profiles](SCORING_PROFILES_GUIDE.md) - Choose the right scoring model for your needs
- [CHAOSS Metrics Alignment](CHAOSS_METRICS_ALIGNMENT_VALIDATION.md) - Understanding our metrics

**Integrations:**

- [GitHub Actions](GITHUB_ACTIONS_GUIDE.md) - Automate checks in CI/CD
- [Pre-commit Integration](PRE_COMMIT_INTEGRATION.md) - Run checks before commits

**Support:**

- [Troubleshooting & FAQ](TROUBLESHOOTING_FAQ.md) - Common issues and solutions

**Reference:**

- [Database Schema](DATABASE_SCHEMA.md) - Understanding cached data format
- [Schema Version Management](SCHEMA_VERSION_MANAGEMENT.md) - Schema evolution and migrations

## Installation

```bash
pip install oss-sustain-guard
```

## Supported Ecosystems

- **Python** - PyPI
- **JavaScript/TypeScript** - npm
- **Rust** - Cargo
- **Java** - Maven
- **PHP** - Packagist
- **Ruby** - RubyGems
- **C# / .NET** - NuGet
- **Go** - Go Modules
- **Kotlin** - Maven

## Community Standards

OSS Sustain Guard uses encouraging, respectful language across all surfaces. Our observations help teams collaborate with maintainers and improve sustainability together—not to judge or blame projects.

## License

OSS Sustain Guard is open source and available under the MIT License.
