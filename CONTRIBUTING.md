# Contributing to OSS Sustain Guard

Thank you for your interest in contributing! This guide covers development setup, testing, code style, and architecture.

## 📋 Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Testing Guidelines](#testing-guidelines)
- [Code Style](#code-style)
- [Architecture](#architecture)
- [Pull Request Process](#pull-request-process)
- [Adding New Features](#adding-new-features)

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Git

### Setup Development Environment

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/oss-sustain-guard.git
cd oss-sustain-guard

# 3. Add upstream remote
git remote add upstream https://github.com/onukura/oss-sustain-guard.git

# 4. Install dependencies
uv sync

# 5. Install pre-commit hooks
uv run pre-commit install

# 6. Create a feature branch
git checkout -b feature/your-feature-name
```

## 🔄 Development Workflow

### 1. Keep Your Fork Updated

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

### 2. Make Changes

```bash
# Create a feature branch
git checkout -b feature/add-new-metric

# Make your changes
# ...

# Run tests
uv run pytest tests/ -v

# Check code quality
uv run ruff check oss_sustain_guard tests builder
uv run ruff format oss_sustain_guard tests builder
```

### 3. Commit Changes

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git commit -m "feat: add new sustainability metric for dependency freshness"
git commit -m "fix: resolve cache TTL validation issue"
git commit -m "docs: update README with cache examples"
git commit -m "test: add coverage for JavaScript resolver"
git commit -m "chore: update dependencies"
```

**Commit Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

## 🧪 Testing Guidelines

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_cache.py -v

# Run tests with coverage
uv run pytest tests/ --cov=oss_sustain_guard --cov-report=term --cov-report=html

# Run tests for specific ecosystem
uv run pytest tests/resolvers/test_python.py -v
```

### Writing Tests

1. **Test Location**: Place tests in `tests/` directory mirroring the source structure
2. **Test Naming**: Use `test_` prefix for test functions
3. **Mock External APIs**: Always mock HTTP requests to external services
4. **Coverage Target**: Aim for 80%+ coverage for new code

**Example Test:**

```python
import pytest
from unittest.mock import patch
from oss_sustain_guard.cache import load_cache, save_cache

def test_save_and_load_cache(tmp_path):
    """Test cache save and load functionality."""
    with patch("oss_sustain_guard.config.get_cache_dir", return_value=tmp_path):
        data = {"python:requests": {"total_score": 85}}
        save_cache("python", data)

        loaded = load_cache("python")
        assert "python:requests" in loaded
        assert loaded["python:requests"]["total_score"] == 85
```

### Test Categories

- **Unit Tests**: Test individual functions/methods
- **Integration Tests**: Test component interactions
- **Resolver Tests**: Test package registry resolvers
- **CLI Tests**: Test command-line interface
- **Cache Tests**: Test caching functionality

## 🎨 Code Style

### Python Style Guide

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting.

**Key Guidelines:**

- Follow PEP 8
- Line length: 88 characters (Black style)
- Use type hints for function signatures
- Use `list[T]`, `dict[K, V]` instead of `List`, `Dict` (Python 3.10+ style)
- Docstrings: Google style

**Example:**

```python
def analyze_package(
    package_name: str,
    ecosystem: str,
    use_cache: bool = True,
) -> AnalysisResult | None:
    """
    Analyze a package's sustainability metrics.

    Args:
        package_name: Name of the package to analyze.
        ecosystem: Ecosystem name (python, javascript, rust, etc.).
        use_cache: Whether to use cached data if available.

    Returns:
        AnalysisResult if successful, None otherwise.
    """
    # Implementation
    pass
```

### Running Code Quality Checks

```bash
# Lint check
uv run ruff check oss_sustain_guard tests builder

# Format code
uv run ruff format oss_sustain_guard tests builder

# Check formatting without modifying files
uv run ruff format --check oss_sustain_guard tests builder
```

## 📝 Pull Request Process

### Before Submitting

1. ✅ Run all tests and ensure they pass
2. ✅ Run linter and formatter
3. ✅ Update documentation if needed
4. ✅ Add tests for new functionality
5. ✅ Update CHANGELOG.md (if applicable)

### Submitting Pull Request

1. **Push to your fork:**

   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request on GitHub:**
   - Go to the original repository
   - Click "New Pull Request"
   - Select your fork and branch

3. **PR Template:**

   ```markdown
   ## Description
   Brief description of changes

   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update

   ## Testing
   - [ ] All tests pass
   - [ ] Added new tests
   - [ ] Coverage maintained/improved

   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Self-reviewed code
   - [ ] Commented complex code
   - [ ] Documentation updated
   - [ ] No new warnings
   ```

### PR Review Process

1. Automated checks must pass (tests, linting)
2. Maintainer review
3. Address feedback
4. Approval and merge

## 🆕 Adding New Features

### Adding a New Metric

1. **Define the metric in `core.py`:**

   ```python
   def check_dependency_freshness(repo_data: dict[str, Any]) -> Metric:
       """Check how up-to-date dependencies are."""
       # Implementation
       return Metric(
           name="Dependency Freshness",
           score=score,
           max_score=10,
           message=message,
           risk=risk,
       )
   ```

2. **Add to `analyze_repository()`:**

   ```python
   metrics.append(check_dependency_freshness(repo_data))
   ```

3. **Write tests:**

   ```python
   def test_check_dependency_freshness_up_to_date():
       mock_data = {"dependencies": {"outdated": 0}}
       result = check_dependency_freshness(mock_data)
       assert result.score == 10
   ```

4. **Update documentation:**
   - README.md
   - docs/METRICS.md (if exists)

### Adding a New Language Resolver

1. **Create resolver file:**

   ```bash
   touch oss_sustain_guard/resolvers/kotlin.py
   ```

2. **Implement resolver class:**

   ```python
   from oss_sustain_guard.resolvers.base import BaseResolver

   class KotlinResolver(BaseResolver):
       def resolve(self, package_name: str) -> tuple[str, str] | None:
           # Implementation
           pass
   ```

3. **Register in `resolvers/__init__.py`:**

   ```python
   from .kotlin import KotlinResolver

   ECOSYSTEM_RESOLVERS = {
       # ... existing resolvers ...
       "kotlin": KotlinResolver(),
   }
   ```

4. **Write comprehensive tests:**

   ```bash
   touch tests/resolvers/test_kotlin.py
   ```

5. **Update documentation:**
   - README.md ecosystem table
   - Add examples

## 🏗️ Architecture

### File Structure

```text
oss_sustain_guard/
  __init__.py                    # Package marker
  cli.py                         # Typer CLI & Rich output
  core.py                        # Analysis engine & GitHub GraphQL
  config.py                      # Configuration management
  cache.py                       # Cache management
  resolver.py                    # Backward compatibility layer

  resolvers/                     # Multi-language resolver package
    __init__.py                  # Registry & factory functions
    base.py                      # BaseResolver abstract class
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
  fallback_packages.py           # Fallback package definitions

data/
  latest/                        # Current snapshot (build artifacts, not committed)
    python.json
    javascript.json
    ...

tests/
  resolvers/                     # Resolver unit tests
    test_base.py
    test_python.py
    test_javascript.py
    ...
  test_cli_multi.py              # Multi-language CLI tests
  test_cache.py                  # Cache functionality tests
  test_config.py                 # Configuration tests
  test_core.py                   # Core analysis tests

.github/workflows/
  test.yml                       # Test automation
  update_database.yml            # Database update automation
```

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

### Cache Architecture

OSS Sustain Guard uses a local filesystem cache to store package analysis results:

**Location:** `~/.cache/oss-sustain-guard/` (configurable)

**Structure:**

- Per-ecosystem JSON files: `python.json`, `javascript.json`, etc.
- Each entry includes:
  - `repo_url`: GitHub repository URL
  - `total_score`: Overall sustainability score (0-100)
  - `metrics`: Array of individual metric results
  - `cache_metadata`: Metadata with `fetched_at`, `ttl_seconds`, `source`

**TTL Management:**

- Default TTL: 7 days (604800 seconds)
- Configurable via CLI, environment variables, or TOML config
- Auto-refresh on cache expiration

**Priority:** CLI args > env vars > TOML config > defaults

See `oss_sustain_guard/cache.py` for implementation details.

## 📞 Getting Help

- **Issues**: [GitHub Issues](https://github.com/onukura/oss-sustain-guard/issues)
- **Discussions**: [GitHub Discussions](https://github.com/onukura/oss-sustain-guard/discussions)

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.
