# OSS Sustain Guard Documentation

OSS Sustain Guard is a multi-language package sustainability analyzer that helps you understand the health of your dependencies across ecosystems. The tool provides constructive insights about maintainer activity, community engagement, security posture, and funding signals so teams can make informed decisions about the projects they rely on.

![CLI demo showing an analyzed package](assets/demo01.png)

## Why OSS Sustain Guard?

Every time a high-profile OSS incident makes the news, I find myself wondering about the packages I rely on right now. I could visit GitHub and skim issues, pull requests, and activity to get a rough sense, but it is not easy. When you depend on tens or hundreds of packages, plus their dependencies, it becomes nearly impossible, and you usually do not notice until something goes wrong.

The libraries that support my work might be under heavy strain, and their own dependencies might be too. OSS Sustain Guard was built to answer those questions and to create moments where users can see the state of maintainers and communities. The first step is simple awareness.

## 💡 Project Philosophy

OSS Sustain Guard uses empathetic language and contextual metrics to help teams support the projects they rely on. We avoid judgment and recognize that sustainability looks different across communities and organizations.

We believe that:

- 🌱 **Sustainability matters** - Open-source projects need ongoing support to thrive
- 🤝 **Community support is essential** - For community-driven projects, we highlight funding opportunities to help users give back
- 📊 **Transparency helps everyone** - By providing objective metrics, we help maintainers and users make informed decisions
- 🎯 **Respectful evaluation** - We distinguish between corporate-backed and community-driven projects, recognizing their different sustainability models
- 💝 **Supporting maintainers** - When available, we display funding links for community projects to encourage direct support

Metrics are one lens among many; they work best alongside project context and real-world knowledge.

- **Local caching:** Analysis results are cached locally to minimize API calls. GitHub token required for real-time analysis of uncached packages.
- **Multi-ecosystem support:** Analyze packages from Python, JavaScript, Go, Rust, PHP, Java, Kotlin, C#, and Ruby in one command.
- **Actionable insights:** Metrics use empathetic language that encourages collaboration with maintainers rather than blame.
- **Time-travel friendly:** Historical snapshots enable trend analysis and comparisons between releases.
- **Sustainable by design:** Respects open-source sustainability models with funding awareness for community-driven projects.

## Key Features

### 🔍 Comprehensive Analysis

- **24 Sustainability Metrics** - Comprehensive evaluation across maintainer health, development activity, community engagement, project maturity, and security (all metrics scored 0-10)
- **CHAOSS-aligned metrics** measuring contributor health, development activity, community engagement, and project maturity
- **5 CHAOSS-Aligned Models** - Risk, Sustainability, Community Engagement, Project Maturity, and Contributor Experience
- **Scoring profiles** optimized for different priorities (balanced, security-first, contributor-experience, long-term-stability)
- **Transparent scoring** with detailed breakdowns of each metric

### 🔧 Developer-Friendly Workflow

- **Manifest auto-detection** from `requirements.txt`, `package.json`, `Cargo.toml`, and other formats
- **Recursive scanning** for monorepos and multi-service projects
- **Exclude configuration** for internal or legacy dependencies
- **Integration-ready** for GitHub Actions, pre-commit hooks, and CI/CD pipelines

### 📝 Extensibility & Configuration

- **Pluggable Metrics System** - Easily extend analysis by adding your own sustainability metrics as plugins
- **Custom Scoring Profiles** - Define your own scoring profiles to tailor evaluation priorities for your organization or use case
- **Metric-Weighted Scoring** - Configurable scoring profiles with integer weights per metric, normalized to 0-100 scale
- **Zero Configuration** - Works out of the box

### 🌍 Multi-Language Support

- **Python, JavaScript, Go, Rust, PHP, Java, Kotlin, C#, Ruby** and more
- **Multi-ecosystem support** - Analyze packages from all supported languages in one command

### 💝 Sustainability Focus

- **Community Support Awareness** - Displays funding links for community-driven projects
- **Local Caching** - Efficient local cache for faster repeated checks
- **Gratitude Vending Machine** - Discover projects that need your support most

## Quick Navigation

### Just Getting Started?

👉 **[Getting Started Guide](GETTING_STARTED.md)** - Installation, first steps, and basic usage in 5 minutes

### Common Tasks

**Usage:**

- [Recursive Scanning](RECURSIVE_SCANNING_GUIDE.md) - Analyze entire projects and monorepos
- [Gratitude Vending Machine](GRATITUDE_VENDING_MACHINE.md) - Find projects to support

**Configuration:**

- [Exclude Configuration](EXCLUDE_PACKAGES_GUIDE.md) - Skip internal or legacy packages

**Scoring & Metrics:**

- [Scoring Profiles](SCORING_PROFILES_GUIDE.md) - Choose the right scoring model for your needs
- [CHAOSS Metrics Alignment](CHAOSS_METRICS_ALIGNMENT_VALIDATION.md) - Understanding our metrics
- [Custom Metrics](CUSTOM_METRICS_GUIDE.md) - Create your own sustainability metrics

**Integrations:**

- [GitHub Actions](GITHUB_ACTIONS_GUIDE.md) - Automate checks in CI/CD
- [Pre-commit Integration](PRE_COMMIT_INTEGRATION.md) - Run checks before commits

**Support:**

- [Troubleshooting & FAQ](TROUBLESHOOTING_FAQ.md) - Common issues and solutions

## Installation

```bash
pip install oss-sustain-guard
```

## Supported Ecosystems

- **Python** - PyPI
- **JavaScript/TypeScript** - npm
- **Rust** - Cargo
- **Dart** - pub.dev
- **Elixir** - Hex.pm
- **Haskell** - Hackage
- **Perl** - CPAN
- **R** - CRAN/renv
- **Swift** - Swift Package Manager
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
