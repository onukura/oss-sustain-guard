# OSS Sustain Guard

[![Test & Coverage](https://github.com/onukura/oss-sustain-guard/actions/workflows/test.yml/badge.svg)](https://github.com/onukura/oss-sustain-guard/actions/workflows/test.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/oss-sustain-guard)](https://pypi.org/project/oss-sustain-guard/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Evaluates the sustainability of Python packages using metrics such as Bus Factor, Maintainer Drain, Release Frequency, and Security Status.

With the **Token-less Experience** + **Static Snapshot API** model, users can perform fast evaluations without API tokens.

## 🎯 Key Features

- **9 Sustainability Metrics**
  - Bus Factor
  - Maintainer Drain
  - Zombie Check
  - Merge Velocity
  - CI Status
  - Funding
  - Release Cadence
  - Security Posture
  - Community Health

- **Cache-based Fast Evaluation**
  - Pre-computed top 10 packages in `data/database.json`
  - Returns results immediately on cache hit

- **Pre-Commit Hook Support**
  - Automatically checks dependency packages in `requirements.txt`
  - Detects sustainability risks at commit time

- **GitHub Actions Automation**
  - Automatically updates database daily at UTC 00:00
  - 4-layer commit safety mechanism to prevent unnecessary file changes

## 🚀 Installation

```bash
pip install oss-sustain-guard
```

Or setup for development:

```bash
uv sync
```

## 📖 Usage

### Direct CLI Execution - Python Packages

```bash
# Check a single package
oss-guard check flask

# Check multiple packages
oss-guard check django requests numpy

# Load from requirements.txt
oss-guard check requirements.txt

# Display detailed information
oss-guard check flask -v
```

### 🌍 Multi-Language Package Analysis

OSS Sustain Guard supports multiple languages: **Python, JavaScript, Go, Rust, PHP, Java, and C#**.

#### Usage

```bash
# Single language checks
oss-guard check npm:react             # JavaScript (npm)
oss-guard check rust:tokio            # Rust (crates.io)
oss-guard check ruby:rails            # Ruby (RubyGems)
oss-guard check go:github.com/golang/go  # Go (GitHub URL)
oss-guard check php:symfony/console   # PHP (Composer)
oss-guard check java:com.google.guava:guava  # Java (Maven)
oss-guard check csharp:Newtonsoft.Json      # C# (NuGet)

# Multi-language simultaneous analysis
oss-guard check \
  requests \
  npm:react \
  npm:vue \
  ruby:rails \
  rust:tokio \
  php:laravel/framework \
  java:org.springframework:spring-core \
  csharp:Serilog

# Auto-detect from directory
oss-guard check --include-lock
```

#### Ecosystem Specification Format

Use `ecosystem:` prefix with package names:

| Ecosystem | Aliases | Format Example | Description |
|-----------|---------|-------------|------|
| **Python** | `python`, `py` | `requests` or `python:requests` | PyPI packages |
| **JavaScript** | `javascript`, `js`, `npm` | `npm:react`, `js:vue` | npm registry |
| **Go** | `go` | `go:github.com/golang/go` | GitHub path format |
| **Ruby** | `ruby`, `gem` | `ruby:rails`, `gem:devise` | RubyGems |
| **Rust** | `rust` | `rust:tokio` | crates.io |
| **PHP** | `php`, `composer` | `php:symfony/console`, `composer:laravel/framework` | Composer/Packagist |
| **Java** | `java`, `kotlin`, `scala`, `maven` | `java:com.google.guava:guava` | Maven Central (groupId:artifactId) |
| **C#** | `csharp`, `dotnet`, `nuget` | `csharp:Newtonsoft.Json`, `nuget:Serilog` | NuGet |

#### Supported Lock File Formats

```bash
# Auto-detect with --include-lock option
oss-guard check --include-lock
```

| Ecosystem | Lock Files |
|-----------|-----------|
| Python | `poetry.lock`, `uv.lock`, `Pipfile.lock` |
| JavaScript | `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml` |
| Go | `go.sum` |
| Ruby | `Gemfile.lock` |
| Rust | `Cargo.lock` |
| PHP | `composer.lock` |
| Java | `gradle.lockfile`, `build.sbt.lock` |
| C# | `packages.lock.json` |

#### CLI Options

```bash
oss-guard check [PACKAGES]... [OPTIONS]

Options:
  --ecosystem, -e TEXT      Default ecosystem (python, javascript, go, ruby, rust, php, java, kotlin, scala, csharp, dotnet)
                           Default: auto (auto-detect)
  --include-lock, -l       Auto-detect from all lock files in directory
  --verbose, -v            Display detailed metrics
  --help                   Show help
```

### GitHub Actions (Recommended for CI/CD)

OSS Sustain Guard integrates directly into GitHub Actions CI/CD pipelines. This project itself uses the action in two workflows:

- **`check-dependencies.yml`** - Checks specific project dependencies
- **`auto-detect-deps.yml`** - Auto-detects dependencies from lock files

#### Quick Start - Docker Action (Recommended ⭐)

The fastest and most reliable way to use OSS Sustain Guard. Uses pre-built Docker image with all dependencies:

```yaml
name: Check Dependencies

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Check package sustainability
        uses: onukura/oss-sustain-guard@main
        with:
          packages: 'requests django flask'
          verbose: 'true'
```

**Advantages:**

- ⚡ **Fast** - No dependency installation required
- 🔒 **Reliable** - Pre-built and tested image
- 🌍 **Multi-language** - All ecosystems pre-configured
- 📦 **Lightweight** - Based on Python slim image

#### Alternative - Reusable Workflow

Call the reusable workflow for more control:

```yaml
name: Sustainability Check

on: [push, pull_request]

jobs:
  check-packages:
    uses: onukura/oss-sustain-guard/.github/workflows/check-packages.yml@main
    with:
      packages: 'flask requests numpy'
      include-lock: false
      verbose: false
```

#### Action Inputs

| Input | Required | Description | Example |
|-------|----------|-------------|---------|
| `packages` | No | Space-separated package names to analyze | `"requests"` or `"npm:react rust:tokio"` or empty for auto-detect |
| `ecosystem` | No | Default ecosystem for unqualified packages | `"python"`, `"javascript"`, `"go"`, `"rust"`, `"php"`, `"java"`, `"csharp"` or `"auto"` (default) |
| `include-lock` | No | Auto-detect from lock files | `true` (default: `false`) |
| `verbose` | No | Show detailed metrics | `true` (default: `false`) |
| `insecure` | No | Disable SSL certificate verification | `true` (default: `false`) |
| `github-token` | No | GitHub token for API calls | Uses `secrets.GITHUB_TOKEN` by default |

#### Real-World Examples

**Python & JavaScript multi-package check:**

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    packages: 'requests django flask npm:react npm:vue npm:axios'
```

**Auto-detect from lock files:**

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    packages: ''  # Or omit entirely
    include-lock: 'true'
```

**Verbose output with multiple ecosystems:**

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    packages: 'requests npm:express ruby:rails rust:tokio'
    verbose: 'true'
```

**Fail workflow on critical findings:**

```yaml
- name: Check critical dependencies
  uses: onukura/oss-sustain-guard@main
  with:
    packages: 'critical-package'
    verbose: 'true'
```

**Using ecosystem option to override package type:**

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    packages: 'react express vue'
    ecosystem: 'javascript'
    verbose: 'true'
```

**Insecure mode for environments with SSL issues:**

```yaml
- uses: onukura/oss-sustain-guard@main
  with:
    packages: 'requests django'
    insecure: 'true'
```

### Pre-Commit Hooks (Recommended)

#### Setup

```bash
# 1. Install Pre-Commit
pip install pre-commit

# 2. Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/onukura/oss-sustain-guard
    rev: v0.1.0
    hooks:
      - id: oss-sustain-guard
EOF

# 3. Install hooks
pre-commit install
```

#### Execution

```bash
# Automatically run on commit
git add requirements.txt
git commit -m "Update dependencies"

# Manual execution
pre-commit run oss-sustain-guard --all-files

# Skip hooks (emergency only)
git commit -m "Emergency fix" --no-verify
```

See [PRE_COMMIT_INTEGRATION.md](./docs/PRE_COMMIT_INTEGRATION.md) for details.

## 💾 Cache Management

OSS Sustain Guard caches package analysis data locally to improve performance and reduce network requests.

### Cache Configuration

Configure cache behavior via:

1. **Command-line options**
2. **Environment variables**
3. **Configuration file** (`.oss-sustain-guard.toml`)

#### Command-line Options

```bash
# Specify custom cache directory
oss-guard check requests --cache-dir /path/to/cache

# Set custom TTL (in seconds, default: 604800 = 7 days)
oss-guard check requests --cache-ttl 86400  # 1 day

# Disable cache (always fetch fresh data)
oss-guard check requests --no-cache

# Clear cache
oss-guard check --clear-cache
```

#### Environment Variables

```bash
# Set cache directory
export OSS_SUSTAIN_GUARD_CACHE_DIR="$HOME/.cache/oss-sustain-guard"

# Set cache TTL (in seconds)
export OSS_SUSTAIN_GUARD_CACHE_TTL=604800

# Run check
oss-guard check requests
```

#### Configuration File

Create `.oss-sustain-guard.toml` in your project root:

```toml
[tool.oss-sustain-guard.cache]
# Cache directory (default: ~/.cache/oss-sustain-guard)
directory = "~/.cache/oss-sustain-guard"

# Cache TTL in seconds (default: 604800 = 7 days)
ttl_seconds = 604800

# Enable/disable cache (default: true)
enabled = true
```

### Cache Statistics

View cache statistics:

```bash
# All ecosystems
oss-guard cache-stats

# Specific ecosystem
oss-guard cache-stats python
```

Example output:

```text
Cache Statistics
  Directory: /home/user/.cache/oss-sustain-guard
  Total entries: 604
  Valid entries: 598
  Expired entries: 6

Per-Ecosystem Breakdown:
┏━━━━━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━━━┓
┃ Ecosystem ┃ Total ┃ Valid ┃ Expired ┃
┡━━━━━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━━━┩
│ python    │   188 │   185 │       3 │
│ rust      │   198 │   198 │       0 │
│ ruby      │   197 │   195 │       2 │
└───────────┴───────┴───────┴─────────┘
```

### Cache Behavior

- **Default Location**: `~/.cache/oss-sustain-guard/`
- **Default TTL**: 7 days (604800 seconds)
- **Auto-refresh**: Expired entries are automatically refetched
- **Per-ecosystem files**: Each language has its own cache file (e.g., `python.json`, `javascript.json`)

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

## ⚙️ Exclude Packages Configuration

You can exclude specific packages from sustainability checks.

### Configuration File

Add the following to `.oss-sustain-guard.toml` or `pyproject.toml`:

```toml
[tool.oss-sustain-guard]
exclude = [
    "internal-package",
    "legacy-dependency",
]
```

See [EXCLUDE_PACKAGES_GUIDE.md](./EXCLUDE_PACKAGES_GUIDE.md) for details.

## ⚙️ Configuration

### Environment Variables

```bash
export GITHUB_TOKEN=your_github_token
```

**Note**: Non-cached packages use GitHub GraphQL API for real-time analysis. If no token is provided, data is fetched from cache only.

### Database Generation

```bash
# Regenerate database by running builder/build_db.py
python builder/build_db.py
```

## 🔧 Development

### Running Tests

```bash
uv run pytest -v
```

### Code Formatting & Linting

```bash
# Format code
uv run ruff format oss_sustain_guard tests

# Check for lint issues
uv run ruff check oss_sustain_guard tests
```

## 📁 File Structure

```text
oss_sustain_guard/
  __init__.py                    # Package marker
  cli.py                         # Typer CLI & Rich output
  core.py                        # Analysis engine & GitHub GraphQL
  config.py                      # Configuration management
  resolver.py                    # Backward compatibility layer

  resolvers/                     # Multi-language resolver package
    __init__.py                  # Registry & factory functions
    base.py                      # LanguageResolver ABC
    python.py                    # Python (PyPI) resolver
    javascript.py                # JavaScript (npm) resolver
    go.py                        # Go resolver
    rust.py                      # Rust (crates.io) resolver
    ruby.py                      # Ruby (RubyGems) resolver
    php.py                       # PHP (Composer/Packagist) resolver
    java.py                      # Java/Kotlin/Scala (Maven Central) resolver
    csharp.py                    # C# (.NET/NuGet) resolver

builder/
  build_db.py                    # Multi-language DB generation script

scripts/
  migrate_db_v1_to_v2.py        # v1.0 → v2.0 schema migration script

data/
  database.json                  # Cached database (v2.0 format)
  database.json.backup           # Backup

tests/
  resolvers/                     # Resolver unit tests
    test_base.py
    test_python.py
    test_javascript.py
    test_go.py
    test_rust.py
    test_ruby.py
    test_php.py
    test_java.py
    test_csharp.py
    test_registry.py
  test_cli_multi.py              # Multi-language CLI tests
  test_*.py                      # Other tests

.github/workflows/
  update_database.yml            # GitHub Actions automation

.pre-commit-hooks.yaml           # Pre-Commit hook definitions
```

## 🏗️ Architecture

### Multi-Language Data Flow

```text
Package Input
    ↓
  parse_package_spec()
    ├─ ecosystem: "python"    → python:requests
    ├─ ecosystem: "javascript" → npm:react
    ├─ ecosystem: "go"         → go:gin
    ├─ ecosystem: "rust"       → rust:tokio
    ├─ ecosystem: "php"        → php:symfony/console
    ├─ ecosystem: "java"       → java:com.google.guava:guava
    └─ ecosystem: "csharp"     → csharp:Newtonsoft.Json
    ↓
  get_resolver(ecosystem)
    ├─ PythonResolver (PyPI API)
    ├─ JavaScriptResolver (npm API)
    ├─ GoResolver (GitHub paths)
    ├─ RustResolver (crates.io API)
    ├─ RubyResolver (RubyGems API)
    ├─ PhpResolver (Packagist V2 API)
    ├─ JavaResolver (Maven Central API)
    └─ CSharpResolver (NuGet V3 API)
    ↓
  resolve_github_url(package_name)
    ↓
  GitHub GraphQL API
    ↓
  analyze_repository(owner, repo)
    ├─ Calculate 9 metrics
    └─ AnalysisResult (0-100 score)
    ↓
  Check cache or perform new analysis
    ↓
  display_results() → Rich table
```

### Ecosystem Support Matrix

| Ecosystem | API | Lock Files | Authentication |
|-----------|-----|-----------|------|
| Python | PyPI API | poetry.lock, uv.lock, Pipfile.lock | Not required |
| JavaScript | npm API | package-lock.json, yarn.lock, pnpm-lock.yaml | Not required |
| Go | pkg.go.dev | go.sum | Not required |
| Ruby | RubyGems API | Gemfile.lock | Not required |
| Rust | crates.io API | Cargo.lock | Not required |
| PHP | Packagist V2 API | composer.lock | Not required |
| Java | Maven Central API | gradle.lockfile, build.sbt.lock | Not required |
| C# | NuGet V3 API | packages.lock.json | Not required |

## 📝 Documentation

- [DATABASE_SCHEMA.md](./docs/DATABASE_SCHEMA.md) - v2.0 schema specification (multi-language support)
- [PRE_COMMIT_INTEGRATION.md](./PRE_COMMIT_INTEGRATION.md) - Pre-Commit hook details
- [EXCLUDE_PACKAGES_GUIDE.md](./EXCLUDE_PACKAGES_GUIDE.md) - Package exclusion configuration

## 🔄 Migration

### v1.0 (Python Only) → v2.0 (Multi-Language)

To upgrade an existing project:

```bash
# 1. Migrate database schema
uv run python scripts/migrate_db_v1_to_v2.py

# 2. Run all tests
uv run pytest -v

# 3. Verify multi-language support in CLI
uv run oss-guard check python:flask npm:react rust:tokio
```

See [DATABASE_SCHEMA.md](./docs/DATABASE_SCHEMA.md) for details.

## 📄 License

MIT License

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss the proposed changes.

## 🧪 Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/onukura/oss-sustain-guard.git
cd oss-sustain-guard

# Install dependencies with uv
uv sync

# Install pre-commit hooks
uv run pre-commit install
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ --cov=oss_sustain_guard --cov-report=term --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Code Quality

```bash
# Run linter
uv run ruff check oss_sustain_guard tests builder

# Run formatter
uv run ruff format oss_sustain_guard tests builder

# Run type checker (if mypy is added)
uv run mypy oss_sustain_guard
```

### Testing CI Locally

```bash
# Test pre-commit hooks
uv run pre-commit run --all-files

# Test specific ecosystem resolver
uv run pytest tests/resolvers/test_python.py -v

# Test cache functionality
uv run pytest tests/test_cache.py -v
```

### Coverage Goals

Current coverage: **55%**

Priority areas for improvement:

- `cli.py` (17%) - CLI integration tests
- `core.py` (42%) - GitHub API mocking tests
- Resolver error paths - Edge case handling

Target: **80%+ coverage**

## 🐛 Bug Reports

If you find an issue, please report it on [GitHub Issues](https://github.com/onukura/oss-sustain-guard/issues).
