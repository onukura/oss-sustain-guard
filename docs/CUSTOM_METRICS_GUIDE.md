# Custom Metrics Guide

OSS Sustain Guard supports **custom metrics through a plugin system**. You can add your own sustainability metrics either as built-in metrics (contributing to the core project) or as external plugins (separate packages).

## 📋 Table of Contents

- [Overview](#overview)
- [Built-in Metrics](#built-in-metrics)
- [External Plugin Metrics](#external-plugin-metrics)
- [Metric Development Guide](#metric-development-guide)
- [Best Practices](#best-practices)
- [Examples](#examples)

## Overview

### Plugin Architecture

OSS Sustain Guard uses a **plugin-based metric system** with automatic discovery:

1. **Entry Points**: Metrics are discovered via `[project.entry-points."oss_sustain_guard.metrics"]`
2. **MetricSpec**: Each metric exports a `MetricSpec` object containing:
   - `name`: Display name
   - `checker`: Main evaluation function
   - `on_error`: Error handler (optional)
   - `error_log`: Error log format (optional)
3. **Automatic Loading**: Metrics are loaded automatically by `load_metric_specs()`

### Metric Types

| Type | Use Case | Distribution |
|------|----------|--------------|
| **Built-in** | Core sustainability metrics | Part of `oss-sustain-guard` package |
| **External Plugin** | Custom/specialized metrics | Separate Python packages |

## Built-in Metrics

Built-in metrics are part of the OSS Sustain Guard core package.

### Creating a Built-in Metric

#### 1. Create Metric Module

Create `oss_sustain_guard/metrics/my_metric.py`:

```python
"""My metric description."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_my_metric(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates [metric purpose].

    Scoring:
    - Excellent: 10/10
    - Good: 7-9/10
    - Moderate: 4-6/10
    - Needs attention: 1-3/10
    - Needs support: 0/10

    CHAOSS Aligned: [CHAOSS metric name] (if applicable)
    """
    max_score = 10  # Always use 10 for consistency

    # Extract data
    data = repo_data.get("fieldName", {})

    if not data:
        return Metric(
            "My Metric",
            5,  # Default score
            max_score,
            "Note: No data available.",
            "None",
        )

    # Calculate score based on data
    value = data.get("value", 0)

    if value >= 90:
        score = 10
        risk = "None"
        message = f"Excellent: {value}%."
    elif value >= 70:
        score = 7
        risk = "Low"
        message = f"Good: {value}%."
    else:
        score = 2
        risk = "High"
        message = f"Needs attention: {value}%."

    return Metric("My Metric", score, max_score, message, risk)


def _check(repo_data: dict[str, Any], context: MetricContext) -> Metric:
    """Wrapper for metric spec."""
    return check_my_metric(repo_data)


def _on_error(error: Exception) -> Metric:
    """Error handler for metric spec."""
    return Metric(
        "My Metric",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


# Export MetricSpec for automatic discovery
METRIC = MetricSpec(
    name="My Metric",
    checker=_check,
    on_error=_on_error,
)
```

#### 2. Register Entry Point

Add to `pyproject.toml`:

```toml
[project.entry-points."oss_sustain_guard.metrics"]
my_metric = "oss_sustain_guard.metrics.my_metric:METRIC"
```

#### 3. Add to Built-in Registry

Update `oss_sustain_guard/metrics/__init__.py`:

```python
_BUILTIN_MODULES = [
    # ... existing modules ...
    "oss_sustain_guard.metrics.my_metric",
]
```

#### 4. Update Scoring Profiles

Add to `SCORING_PROFILES` in `core.py`:

```python
SCORING_PROFILES = {
    "balanced": {
        "weights": {
            # ... existing metrics ...
            "My Metric": 2,  # Assign weight 1-5
        },
    },
    # Update all 4 profiles
}
```

#### 5. Write Tests

Create `tests/metrics/test_my_metric.py`:

```python
from oss_sustain_guard.metrics.my_metric import check_my_metric


def test_check_my_metric_excellent():
    mock_data = {"fieldName": {"value": 95}}
    result = check_my_metric(mock_data)
    assert result.score == 10
    assert result.risk == "None"


def test_check_my_metric_no_data():
    mock_data = {}
    result = check_my_metric(mock_data)
    assert result.score == 5
    assert "Note:" in result.message
```

#### 6. Test & Submit

```bash
# Run tests
uv run pytest tests/metrics/test_my_metric.py -v

# Check formatting
uv run ruff check oss_sustain_guard/metrics/my_metric.py
uv run ruff format oss_sustain_guard/metrics/my_metric.py

# Test with real data
uv run os4g check fastapi --no-cache -o detail

# Submit PR
git checkout -b feature/add-my-metric
git add .
git commit -m "feat: add My Metric for sustainability analysis"
git push origin feature/add-my-metric
```

## External Plugin Metrics

External plugins allow you to create custom metrics without modifying OSS Sustain Guard core.

### Creating an External Plugin

#### 1. Project Structure

```
my-custom-metric/
├── pyproject.toml
├── README.md
├── my_custom_metric/
│   ├── __init__.py
│   └── metrics.py
└── tests/
    └── test_metrics.py
```

#### 2. Implementation

**`pyproject.toml`:**

```toml
[project]
name = "my-custom-metric"
version = "0.1.0"
description = "Custom metric for OSS Sustain Guard"
requires-python = ">=3.10"
dependencies = [
    "oss-sustain-guard>=0.13.0",
]

[project.entry-points."oss_sustain_guard.metrics"]
custom_metric = "my_custom_metric:METRIC"
```

**`my_custom_metric/__init__.py`:**

```python
"""Custom metric for OSS Sustain Guard."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_custom_metric(repo_data: dict[str, Any], context: MetricContext) -> Metric:
    """
    Custom metric logic.

    Args:
        repo_data: Repository data from GitHub GraphQL API
        context: Metric context with owner, name, repo_url, etc.

    Returns:
        Metric with score, message, and status level
    """
    # Your custom logic here
    owner = context.owner
    repo_name = context.name

    # Example: check if repo has certain keywords
    description = repo_data.get("description", "")

    if "security" in description.lower():
        score = 10
        risk = "None"
        message = "Excellent: Security-focused project."
    else:
        score = 5
        risk = "Low"
        message = "Moderate: No security focus detected."

    return Metric("Custom Security Focus", score, 10, message, risk)


def _on_error(error: Exception) -> Metric:
    """Error handler."""
    return Metric(
        "Custom Security Focus",
        0,
        10,
        f"Error: {error}",
        "Medium",
    )


# Export MetricSpec
METRIC = MetricSpec(
    name="Custom Security Focus",
    checker=check_custom_metric,
    on_error=_on_error,
)
```

#### 3. Installation & Usage

```bash
# Install your plugin
pip install my-custom-metric

# Or install in development mode
cd my-custom-metric
pip install -e .

# Use OSS Sustain Guard (plugin auto-loaded)
oss-guard check numpy
# Your custom metric will appear in the output!
```

#### 4. Distribution

Publish to PyPI:

```bash
# Build
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

Users can install via:

```bash
pip install oss-sustain-guard my-custom-metric
```

## Metric Development Guide

### MetricSpec Structure

```python
class MetricSpec(NamedTuple):
    """Specification for a metric check."""

    name: str
    """Display name of the metric."""

    checker: Callable[[dict[str, Any], MetricContext], Metric | None]
    """Main evaluation function."""

    on_error: Callable[[Exception], Metric] | None = None
    """Error handler (optional)."""

    error_log: str | None = None
    """Error log format string (optional)."""
```

### MetricContext

Context provided to metric checkers:

```python
class MetricContext(NamedTuple):
    """Context provided to metric checks."""

    owner: str
    """GitHub repository owner."""

    name: str
    """Repository name."""

    repo_url: str
    """Full GitHub repository URL."""

    platform: str | None = None
    """Package platform (e.g., 'pypi', 'npm')."""

    package_name: str | None = None
    """Original package name."""
```

### Metric Return Type

```python
class Metric(NamedTuple):
    """A single sustainability metric result."""

    name: str
    """Metric display name."""

    score: int | float
    """Metric score (0-10)."""

    max_score: int
    """Maximum possible score (always 10)."""

    message: str
    """Human-readable result message."""

    risk: str
    """Status label (internal values: "None", "Low", "Medium", "High", "Critical")."""
```

### Accessing GitHub Data

The `repo_data` parameter contains GitHub GraphQL API response:

```python
def check_my_metric(repo_data: dict[str, Any], context: MetricContext) -> Metric:
    # Repository metadata
    name = repo_data.get("name")
    description = repo_data.get("description")
    created_at = repo_data.get("createdAt")

    # Owner information
    owner = repo_data.get("owner", {})
    owner_type = owner.get("__typename")  # "Organization" or "User"

    # Stars, forks, watchers
    stargazers = repo_data.get("stargazerCount", 0)
    forks = repo_data.get("forkCount", 0)

    # Issues and PRs
    open_issues = repo_data.get("openIssues", {}).get("totalCount", 0)
    closed_issues = repo_data.get("closedIssues", {}).get("totalCount", 0)

    # Commit history
    default_branch = repo_data.get("defaultBranchRef", {})
    commits = default_branch.get("target", {}).get("history", {}).get("edges", [])

    # Funding
    funding_links = repo_data.get("fundingLinks", [])

    # License
    license_info = repo_data.get("licenseInfo", {})

    # ... your metric logic
```

### Error Handling

Two approaches for error handling:

**1. Internal Error Handling:**

```python
def check_my_metric(repo_data: dict[str, Any], context: MetricContext) -> Metric:
    try:
        # Metric logic
        value = repo_data["requiredField"]
    except KeyError:
        return Metric(
            "My Metric",
            0,
            10,
            "Note: Required data not available.",
            "Medium",
        )
```

**2. MetricSpec Error Handler:**

```python
def _on_error(error: Exception) -> Metric:
    return Metric(
        "My Metric",
        0,
        10,
        f"Error: {error}",
        "Medium",
    )

METRIC = MetricSpec(
    name="My Metric",
    checker=check_my_metric,
    on_error=_on_error,
)
```

## Best Practices

### Scoring Guidelines

✅ **DO:**

- Use **0-10 scale** for all metrics
- Set `max_score = 10` (consistency)
- Use graduated thresholds (e.g., 10, 8, 5, 2, 0)
- Return meaningful default scores for missing data

❌ **DON'T:**

- Use arbitrary max_score values
- Return None or raise exceptions for missing data
- Use binary scoring (0 or 10 only)

### Message Guidelines

✅ **DO:**

- Use supportive language: "Consider", "Monitor", "Observe"
- Provide context: numbers, reasons, recommendations
- Start with status: "Excellent", "Good", "Moderate", "Needs attention"

❌ **DON'T:**

- Use negative language: "Failed", "Error", "Alarmist failure language"
- Provide vague messages: "Bad", "Poor"
- Use all caps or excessive punctuation

### Status Levels (internal values)

| Internal value | Score Range | Usage |
|------|-------------|-------|
| `"None"` | 9-10 | Excellent health |
| `"Low"` | 7-8 | Good, minor improvements |
| `"Medium"` | 4-6 | Moderate, needs attention |
| `"High"` | 1-3 | Significant concerns |
| `"Critical"` | 0 | Needs support; immediate attention recommended |

### Performance Considerations

- **Cache expensive operations** (API calls, calculations)
- **Fail gracefully** with default scores
- **Avoid blocking operations** in metric checks
- **Return quickly** for missing data

### Testing

Always write comprehensive tests:

```python
def test_metric_excellent():
    """Test best-case scenario."""
    assert result.score == 10
    assert result.risk == "None"

def test_metric_poor():
    """Test worst-case scenario."""
    assert result.score == 0
    assert result.risk == "Critical"

def test_metric_no_data():
    """Test missing data handling."""
    result = check_metric({}, MetricContext(...))
    assert result.max_score == 10
    assert "Note:" in result.message

def test_metric_error_handling():
    """Test error handling."""
    result = check_metric({"bad": "data"}, MetricContext(...))
    assert result is not None
```

## Examples

### Example 1: Code Coverage Metric

```python
"""Code coverage metric."""

from typing import Any
from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_code_coverage(repo_data: dict[str, Any], context: MetricContext) -> Metric:
    """
    Evaluates code coverage percentage.

    Scoring:
    - 90-100%: 10/10 (Excellent)
    - 70-89%: 7/10 (Good)
    - 50-69%: 4/10 (Moderate)
    - <50%: 1/10 (Needs attention)
    """
    # Note: This is a simplified example
    # Real implementation would fetch coverage from CI badges or APIs

    description = repo_data.get("description", "").lower()

    # Simplified logic: check for coverage badge
    if "coverage" in description:
        score = 8
        risk = "Low"
        message = "Good: Coverage tracking detected."
    else:
        score = 3
        risk = "High"
        message = "Needs attention: No coverage tracking detected."

    return Metric("Code Coverage", score, 10, message, risk)


METRIC = MetricSpec(
    name="Code Coverage",
    checker=check_code_coverage,
)
```

### Example 2: Dependency Update Frequency

```python
"""Dependency update frequency metric."""

from datetime import datetime, timedelta
from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_dependency_updates(repo_data: dict[str, Any], context: MetricContext) -> Metric:
    """
    Evaluates how frequently dependencies are updated.

    Looks for dependency update commits (Dependabot, Renovate, etc.).
    """
    commits = (
        repo_data.get("defaultBranchRef", {})
        .get("target", {})
        .get("history", {})
        .get("edges", [])
    )

    if not commits:
        return Metric(
            "Dependency Updates",
            5,
            10,
            "Note: No commit history available.",
            "None",
        )

    # Count dependency update commits
    dep_keywords = ["bump", "update", "dependabot", "renovate", "dependencies"]
    dep_commits = [
        c for c in commits
        if any(kw in c.get("node", {}).get("message", "").lower() for kw in dep_keywords)
    ]

    total = len(commits)
    dep_count = len(dep_commits)
    percentage = (dep_count / total * 100) if total > 0 else 0

    if percentage >= 20:
        score = 10
        risk = "None"
        message = f"Excellent: {percentage:.1f}% of commits are dependency updates."
    elif percentage >= 10:
        score = 7
        risk = "Low"
        message = f"Good: {percentage:.1f}% of commits are dependency updates."
    elif percentage >= 5:
        score = 4
        risk = "Medium"
        message = f"Moderate: {percentage:.1f}% of commits are dependency updates."
    else:
        score = 1
        risk = "High"
        message = f"Needs attention: Only {percentage:.1f}% of commits are dependency updates."

    return Metric("Dependency Updates", score, 10, message, risk)


METRIC = MetricSpec(
    name="Dependency Updates",
    checker=check_dependency_updates,
)
```

### Example 3: CHAOSS-Aligned Metric

```python
"""Technical fork metric aligned with CHAOSS."""

from typing import Any
from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_technical_fork(repo_data: dict[str, Any], context: MetricContext) -> Metric:
    """
    Evaluates technical fork activity (downstream projects).

    CHAOSS Aligned: Technical Fork
    https://chaoss.community/kb/metric-technical-fork/

    Measures project reuse and impact via fork count.
    """
    forks = repo_data.get("forkCount", 0)
    stargazers = repo_data.get("stargazerCount", 0)

    # Calculate fork ratio (forks relative to stars)
    if stargazers > 0:
        fork_ratio = forks / stargazers
    else:
        fork_ratio = 0

    # High fork ratio indicates active reuse
    if fork_ratio >= 0.5:
        score = 10
        risk = "None"
        message = f"Excellent: High fork activity ({forks} forks, {fork_ratio:.1%} ratio)."
    elif fork_ratio >= 0.2:
        score = 7
        risk = "Low"
        message = f"Good: Moderate fork activity ({forks} forks, {fork_ratio:.1%} ratio)."
    elif fork_ratio >= 0.1:
        score = 4
        risk = "Medium"
        message = f"Moderate: Some fork activity ({forks} forks, {fork_ratio:.1%} ratio)."
    else:
        score = 1
        risk = "High"
        message = f"Low: Limited fork activity ({forks} forks, {fork_ratio:.1%} ratio)."

    return Metric("Technical Fork", score, 10, message, risk)


METRIC = MetricSpec(
    name="Technical Fork",
    checker=check_technical_fork,
)
```

## Resources

- [CHAOSS Metrics](https://chaoss.community/metrics/) - Industry-standard OSS metrics
- [OSS Sustain Guard Architecture](https://github.com/onukura/oss-sustain-guard/blob/main/CONTRIBUTING.md#architecture)
- [Adding New Metric Skill](https://github.com/onukura/oss-sustain-guard/blob/main/.claude/skills/adding-new-metric/SKILL.md)
- [Scoring Profiles Guide](SCORING_PROFILES_GUIDE.md)

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/onukura/oss-sustain-guard/issues)
- **Discussions**: [GitHub Discussions](https://github.com/onukura/oss-sustain-guard/discussions)
- **Contributing**: See [CONTRIBUTING.md](https://github.com/onukura/oss-sustain-guard/blob/main/CONTRIBUTING.md)
