# OSS Sustain Guard

[![Test & Coverage](https://github.com/onukura/oss-sustain-guard/actions/workflows/test.yml/badge.svg)](https://github.com/onukura/oss-sustain-guard/actions/workflows/test.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/oss-sustain-guard)](https://pypi.org/project/oss-sustain-guard/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Multi-language package sustainability analyzer** - Evaluate your dependencies' health with 9 key metrics including Bus Factor, Maintainer Activity, and Security Posture.

✨ **No API tokens required** - Fast, cache-based evaluation for Python, JavaScript, Go, Rust, PHP, Java, C#, and Ruby packages.

## 🎯 Key Features

- **9 Sustainability Metrics** - Bus Factor, Maintainer Drain, Release Cadence, Security, and more
- **Multi-Language Support** - Python, JavaScript, Go, Rust, PHP, Java, C#, Ruby
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

# Auto-detect from lock files
oss-guard check --include-lock
```

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

Scores are evaluated in the range of 0-100:

- **80-100**: 🟢 **Excellent** - Healthy project
- **50-79**: 🟡 **Caution** - Areas needing improvement
- **0-49**: 🔴 **Critical** - Severe risks

### Metrics Details

| Metric | Max Score | Description |
|--------|----------|------|
| Bus Factor | 20 | Single maintainer dependency |
| Maintainer Drain | 10 | Long-inactive maintainers |
| Zombie Check | 20 | Inactive repository detection |
| Merge Velocity | 10 | Merge processing speed |
| CI Status | 5 | Automated test coverage |
| Funding | 10 | Sponsorship status |
| Release Cadence | 10 | Release frequency |
| Security Posture | 15 | Security configuration and alerts |
| Community Health | 5 | Issue response time |

## ⚙️ Configuration

**Exclude packages** - Create `.oss-sustain-guard.toml`:

```toml
[tool.oss-sustain-guard]
exclude = ["internal-package", "legacy-dependency"]
```

**GitHub token** - For non-cached packages (optional):

```bash
export GITHUB_TOKEN=your_github_token
```

See [Exclude Packages Guide](./docs/EXCLUDE_PACKAGES_GUIDE.md) for details.

## 🤝 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup, testing, code style, and architecture documentation.

## 📝 Documentation

- [Database Schema](./docs/DATABASE_SCHEMA.md) - JSON database format
- [Pre-Commit Integration](./docs/PRE_COMMIT_INTEGRATION.md) - Hook configuration
- [GitHub Actions Guide](./docs/GITHUB_ACTIONS_GUIDE.md) - CI/CD setup
- [Exclude Packages Guide](./docs/EXCLUDE_PACKAGES_GUIDE.md) - Package filtering

## 📄 License

MIT License
