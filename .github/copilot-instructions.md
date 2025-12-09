# Copilot Instructions for OSS Sustain Guard

## Project Overview

**OSS Sustain Guard** is a multi-language package sustainability analyzer that evaluates repository health metrics (bus factor, maintainer drain, funding, etc.) rather than just CVEs. It supports PyPI (Python), npm (JavaScript), Cargo (Rust), Maven (Java), Packagist (PHP), RubyGems, NuGet (C#), Go modules, and provides holistic risk assessment via GitHub repository data.

**Key Philosophy:** "Token-less Experience" + "Static Snapshot API" model - precomputed JSON database (`data/latest/*.json` and `data/archive/`) eliminates need for user API tokens. Multi-language support with language-specific registry resolvers.

## 💡 Project Philosophy & Core Principles

**Mission:** OSS Sustain Guard is designed to spark thoughtful conversations about open-source sustainability, not to pass judgment on projects. We aim to **raise awareness** about the challenges maintainers face and encourage the community to think together about how we can better support the open-source ecosystem.

### Core Beliefs

1. 🌱 **Sustainability matters** - Open-source projects need ongoing support to thrive
2. 🤝 **Community support is essential** - For community-driven projects, we highlight funding opportunities to help users give back
3. 📊 **Transparency helps everyone** - By providing objective metrics, we help maintainers and users make informed decisions
4. 🎯 **Respectful evaluation** - We distinguish between corporate-backed and community-driven projects, recognizing their different sustainability models
5. 💝 **Supporting maintainers** - When available, we display funding links for community projects to encourage direct support

### Design Principles for All Changes

When implementing new features or making improvements, always follow these principles:

1. **Information, not judgment** - Use supportive language instead of critical terms
   - ❌ "Risk", "Error", "Failed", "Critical"
   - ✅ "Health Status", "Observation", "Note", "Needs attention"

2. **Empathy and respect** - Consider both maintainers and users
   - Show understanding of the challenges open-source maintainers face
   - Provide actionable insights, not just warnings
   - Recognize that every project has unique circumstances

3. **Supportive messaging** - Frame observations constructively
   - Instead of "High Risk", say "Needs attention" or "Consider improving"
   - Instead of "Failed to load", say "Unable to load" or "Note: Using fallback"
   - Instead of "No funding", say "Funding information not available"

4. **Funding awareness** - Promote sustainability
   - Display funding links for community-driven projects
   - Do not show funding links for corporate-backed projects (they have different models)
   - Use encouraging language: "Consider supporting" not "Please donate"

5. **Color psychology** - Use colors thoughtfully
   - 🟢 Green: Healthy, good status
   - 🟡 Yellow: Information, needs attention, monitor
   - 🔴 Red: Needs support (not "critical failure")
   - ⚪ Gray/Dim: Informational, less important notes

6. **Metrics presentation** - Focus on observations
   - Column names: "Health Status" not "Risk", "Observation" not "Message"
   - Status labels: "Healthy", "Monitor", "Needs attention", "Needs support"
   - Avoid absolute judgments; context matters

### Examples of Philosophy in Practice

**UI Text:**
```python
# ❌ Avoid
"Error: Package failed analysis"
"Critical Risk Detected"
"Skipping excluded packages"

# ✅ Prefer
"ℹ️  Unable to complete analysis for package"
"🔍 This project needs attention in some areas"
"📋 Package excluded by configuration"
```

**Table Headers:**
```python
# ❌ Avoid
"Risk Level" | "Critical Issues" | "Failures"

# ✅ Prefer
"Health Status" | "Key Observations" | "Areas to Monitor"
```

**Status Messages:**
```python
# ❌ Avoid
"High Risk" | "Critical" | "Failed"

# ✅ Prefer
"Needs attention" | "Monitor" | "Consider improving"
```

This philosophy applies to:
- CLI output and error messages
- Documentation and README
- Code comments (internal understanding)
- User-facing text and help messages
- Metric names and descriptions

**Remember:** This tool is a conversation starter about OSS sustainability, not a judgment. Every project has unique circumstances, and metrics are just one part of the story.

## Architecture & Data Flow

### Core Modules

1. **`resolvers/`** - Multi-language package registry mappers
   - Base class: `resolvers/base.py` - `BaseResolver` with `resolve()` method
   - Language resolvers: `python.py`, `javascript.py`, `rust.py`, `java.py`, `php.py`, `ruby.py`, `csharp.py`, `go.py`
   - Each resolver maps package name → GitHub repository URL
   - Returns `tuple[str, str] | None` for (owner, repo)

2. **`config.py`** - Configuration management
   - Loads excluded packages from `.oss-sustain-guard.toml` or `pyproject.toml`
   - Priority: local `.oss-sustain-guard.toml` > `pyproject.toml`
   - Global `VERIFY_SSL` flag for SSL verification (default: True, can override with --insecure)

3. **`core.py`** - Analysis Engine & GitHub GraphQL integration
   - Main function: `analyze_repository(owner: str, repo: str) -> AnalysisResult`
   - Uses GitHub GraphQL API with `GITHUB_TOKEN` environment variable
   - Data structures: `NamedTuple` types - `Metric` (name, score, max_score, message, risk) and `AnalysisResult` (repo_url, total_score, metrics)
   - Metric functions: `check_bus_factor()`, `check_maintainer_drain()`, `check_funding_status()`, etc.
   - Total score is sum of individual metric scores

4. **`cli.py`** - User Interface (Typer + Rich)
   - Commands: `check` (packages/requirements.txt), `--insecure` flag for SSL override
   - Loads cached data from language-specific files: `data/latest/{language}.json`
   - Displays results in Rich-formatted tables with color-coded risk levels (green/yellow/red)

### Data Flow

```
Package Name (any language) → Language-specific resolver → GitHub (owner/repo)
                                                                 ↓
                                                        core.py (GraphQL query)
                                                                 ↓
                                                        AnalysisResult
                                                                 ↓
                                                 cli.py → Rich table
```

## Development Conventions

### Language Rules

- **Code & Documentation:** Write all code comments, docstrings, and documentation in **English**
- **Chat Response:** Respond to users in user's language
- This applies to:
  - Python docstrings and inline comments
  - Markdown documentation files
  - TOML configuration comments
  - Error messages and user-facing text

### Type Annotations & Imports

- **Use built-in types:** `list[T]`, `dict[K, V]`, `tuple[T, ...]`
- **Never** use `List`, `Dict`, `Optional` from `typing` module
- Use `SomeType | None` for optional values (PEP 604)
- `NamedTuple` for immutable data structures (preferred over dataclass for simplicity)

**Example:**
```python
def get_github_url_from_pypi(package_name: str) -> tuple[str, str] | None:
    """Returns (owner, repo) or None."""
```

### Testing & Code Quality

- **Test Framework:** `pytest` with `asyncio_mode = "auto"`
- **Linter/Formatter:** `ruff` (Python 3.10+, line-length=88, indent=4)
- **Package Manager:** `uv` (check `pyproject.toml` for dependencies)
- **Python Support:** 3.10 - 3.13

**Test Location:** `tests/test_*.py` and `tests/resolvers/test_*.py` - use mocking for external APIs (GitHub, package registries)

**Run Commands:**
```bash
uv run pytest                                    # Run all tests
uv run ruff format oss_sustain_guard tests      # Format code
uv run ruff check oss_sustain_guard tests       # Lint check
uv run python oss_sustain_guard/cli.py check <package>  # Test CLI
```

### Environment & Secrets

- Load environment variables with `load_dotenv()` (already done in `core.py`)
- `GITHUB_TOKEN` required for GitHub GraphQL queries - raise `ValueError` if missing
- `VERIFY_SSL` global flag in `config.py` controls SSL verification (default: True, can be overridden with --insecure CLI flag)

## Critical Patterns

### Language Resolver Implementation

Create new resolver in `resolvers/{language}.py` inheriting from `BaseResolver`:

```python
from resolvers.base import BaseResolver

class MyResolver(BaseResolver):
    """Resolver for MyRegistry packages to GitHub URLs."""

    def resolve(self, package_name: str) -> tuple[str, str] | None:
        """Resolve package name to (owner, repo) tuple."""
        # Fetch from registry API
        # Parse GitHub URL
        # Return (owner, repo) or None on failure
```

Each resolver must:
- Inherit from `BaseResolver`
- Implement `resolve(package_name: str) -> tuple[str, str] | None` method
- Handle network errors gracefully (catch `httpx.RequestError`, return `None` on 404)
- Set `timeout=10` on HTTP requests
- Return `None` if package not found or GitHub URL cannot be extracted

### Error Handling in External APIs

Both language resolvers and `core.py` make HTTP requests. Patterns:

- **Registry API calls:** Catch `httpx.RequestError` for network failures, return `None` on 404
- **GitHub GraphQL:** Check response for `"errors"` key and raise `HTTPStatusError`
- **HTTP Timeouts:** Set `timeout=10` on all client requests

### Database Schema

Cached data in `data/latest/{language}.json` and `data/archive/{date}/{language}.json`:
```json
{
  "package_name": {
    "repo_url": "https://github.com/owner/repo",
    "total_score": 75,
    "metrics": [{"name": "Bus Factor", "score": 5, ...}]
  }
}
```

### Risk Levels

Metric risk values: `"Critical"`, `"High"`, `"Medium"`, `"Low"`, `"None"`

CLI color mapping:
- Score < 50 → Red (critical)
- Score 50-79 → Yellow (warning)
- Score ≥ 80 → Green (safe)

## File Organization

```
oss_sustain_guard/
  __init__.py         # Package marker
  cli.py              # Typer commands & Rich output
  core.py             # Analysis engine, GitHub GraphQL
  config.py           # Configuration management (excluded packages, SSL verification)
  resolvers/          # Multi-language registry resolvers
    __init__.py
    base.py           # BaseResolver abstract class
    python.py         # PyPI resolver
    javascript.py     # npm resolver
    rust.py           # Cargo resolver
    java.py           # Maven resolver
    php.py            # Packagist resolver
    ruby.py           # RubyGems resolver
    csharp.py         # NuGet resolver
    go.py             # Go modules resolver
tests/
  test_cli_multi.py   # Multi-language CLI tests
  test_config.py      # Configuration tests
  test_core.py        # Mock GitHub GraphQL tests
  test_resolver.py    # Legacy PyPI resolver tests
  resolvers/          # Resolver-specific tests
    test_base.py      # BaseResolver tests
    test_python.py    # PyPI tests
    test_javascript.py # npm tests
    test_rust.py      # Cargo tests
    test_java.py      # Maven tests
    test_php.py       # Packagist tests
    test_ruby.py      # RubyGems tests
    test_csharp.py    # NuGet tests
    test_go.py        # Go modules tests
data/
  latest/             # Current snapshot (JSON files per language)
    python.json
    javascript.json
    rust.json
    java.json
    php.json
    ruby.json
    csharp.json
  archive/            # Historical snapshots (dated directories)
    {YYYY-MM-DD}/
      python.json
      javascript.json
      ...
builder/
  build_db.py      # GitHub Actions job to generate database.json files
```

## Key Dependencies

- `typer` - CLI framework with type hints
- `rich` - Terminal formatting (tables, colors)
- `httpx` - HTTP client (async-capable)
- `python-dotenv` - Environment variable loading

## Common Tasks

**Adding a New Metric:**
1. Create `check_my_metric(repo_data: dict[str, Any]) -> Metric` in `core.py`
2. Call it in `analyze_repository()` and append to metrics list
3. Update total_score calculation
4. Add test in `test_core.py` with mocked GraphQL

**Adding a New Language Resolver:**
1. Create `resolvers/{language}.py` inheriting from `BaseResolver`
2. Implement `resolve(package_name: str) -> tuple[str, str] | None` method
3. Create corresponding test file in `tests/resolvers/test_{language}.py` with mocked HTTP responses
4. Update `cli.py` to register the new resolver in language detection logic
5. Create `data/latest/{language}.json` for initial database

**Testing a New API Integration:**
- Use `@patch("httpx.Client.get")` or `@patch("httpx.Client.post")`
- Mock response with `mock_response.json.return_value = {...}`
- See resolver test files for registry mocking examples
- See `test_core.py` for GraphQL mocking examples

**Displaying CLI Results:**
- Use `rich.Table` - see `display_results()` for structure
- Add column with `table.add_column(title, style=color)`
- Color codes: `"cyan"`, `"magenta"`, `"red"`, `"yellow"`, `"green"`
