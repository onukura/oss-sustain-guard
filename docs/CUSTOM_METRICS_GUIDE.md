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
   - `checker`: `MetricChecker` (preferred) or callable using `VCSRepositoryData`
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

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class MyMetricChecker(MetricChecker):
    """Evaluate my metric using normalized VCS data."""

    def check(
        self, vcs_data: VCSRepositoryData, _context: MetricContext
    ) -> Metric | None:
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
        max_score = 10

        description = (vcs_data.description or "").lower()
        if not description:
            return Metric(
                "My Metric",
                5,
                max_score,
                "Note: No description available.",
                "None",
            )

        if "security" in description:
            score = 10
            risk = "None"
            message = "Excellent: Security focus mentioned."
        elif "monitor" in description:
            score = 7
            risk = "Low"
            message = "Good: Monitoring signals present."
        else:
            score = 4
            risk = "Medium"
            message = "Observe: No security focus mentioned."

        return Metric("My Metric", score, max_score, message, risk)


_CHECKER = MyMetricChecker()


def check_my_metric(repo_data: dict[str, object] | VCSRepositoryData) -> Metric | None:
    if isinstance(repo_data, VCSRepositoryData):
        return _CHECKER.check(repo_data, _LEGACY_CONTEXT)
    return _CHECKER.check_legacy(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "My Metric",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


METRIC = MetricSpec(
    name="My Metric",
    checker=_CHECKER,
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
from oss_sustain_guard.vcs.base import VCSRepositoryData


def _vcs_data(**overrides) -> VCSRepositoryData:
    data = VCSRepositoryData(
        is_archived=False,
        pushed_at=None,
        owner_type="User",
        owner_login="owner",
        owner_name=None,
        star_count=0,
        description=None,
        homepage_url=None,
        topics=[],
        readme_size=None,
        contributing_file_size=None,
        default_branch="main",
        watchers_count=0,
        open_issues_count=0,
        language=None,
        commits=[],
        total_commits=0,
        merged_prs=[],
        closed_prs=[],
        total_merged_prs=0,
        releases=[],
        open_issues=[],
        closed_issues=[],
        total_closed_issues=0,
        vulnerability_alerts=None,
        has_security_policy=False,
        code_of_conduct=None,
        license_info=None,
        has_wiki=False,
        has_issues=True,
        has_discussions=False,
        funding_links=[],
        forks=[],
        total_forks=0,
        ci_status=None,
        sample_counts={},
        raw_data=None,
    )
    return data._replace(**overrides)


def test_check_my_metric_excellent():
    result = check_my_metric(_vcs_data(description="Security automation"))
    assert result.score == 10
    assert result.risk == "None"


def test_check_my_metric_no_data():
    result = check_my_metric(_vcs_data(description=None))
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

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData


class CustomSecurityFocusChecker(MetricChecker):
    """Custom metric logic using normalized VCS data."""

    def check(
        self, vcs_data: VCSRepositoryData, context: MetricContext
    ) -> Metric | None:
        """
        Custom metric logic.

        Args:
            vcs_data: Normalized repository data (GitHub, GitLab, etc.)
            context: Metric context with owner, name, repo_url, etc.

        Returns:
            Metric with score, message, and status level
        """
        _ = context.owner
        _ = context.name

        description = (vcs_data.description or "").lower()

        if "security" in description:
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
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )


# Export MetricSpec
METRIC = MetricSpec(
    name="Custom Security Focus",
    checker=CustomSecurityFocusChecker(),
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

    checker: MetricChecker | Callable[[dict[str, object], MetricContext], Metric | None]
    """MetricChecker (preferred) or callable for legacy data."""

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
    """Repository owner."""

    name: str
    """Repository name."""

    repo_url: str
    """Full repository URL."""

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

    score: int
    """Metric score (0-10)."""

    max_score: int
    """Maximum possible score (always 10)."""

    message: str
    """Human-readable result message."""

    risk: str
    """Status label (internal values: "None", "Low", "Medium", "High", "Critical")."""
```

### Accessing VCS Data

The `vcs_data` parameter contains normalized repository data:

```python
def check_my_metric(
    vcs_data: VCSRepositoryData, context: MetricContext
) -> Metric:
    # Repository metadata
    description = vcs_data.description or ""
    owner_login = vcs_data.owner_login
    owner_type = vcs_data.owner_type  # "Organization", "User", or "Group"

    # Stars, forks, watchers
    stargazers = vcs_data.star_count
    forks = vcs_data.total_forks
    watchers = vcs_data.watchers_count

    # Issues and PRs
    open_issues = vcs_data.open_issues_count
    closed_issues = vcs_data.total_closed_issues

    # Commits, releases, PRs
    commits = vcs_data.commits
    releases = vcs_data.releases
    merged_prs = vcs_data.merged_prs

    # Funding and license info
    funding_links = vcs_data.funding_links
    license_info = vcs_data.license_info

    # Host-specific data (may be None depending on provider)
    raw_data = vcs_data.raw_data or {}

    # ... your metric logic
```

### Error Handling

Two approaches for error handling:

**1. Internal Error Handling:**

```python
def check_my_metric(vcs_data: VCSRepositoryData, context: MetricContext) -> Metric:
    try:
        # Metric logic
        license_id = vcs_data.license_info["spdxId"]
        _ = context.repo_url
    except (KeyError, TypeError):
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
        f"Note: Analysis incomplete - {error}",
        "Medium",
    )

METRIC = MetricSpec(
    name="My Metric",
    checker=check_my_metric,
    on_error=_on_error,
)
```

### Skipping Metrics

If a metric requires optional data (for example, a third-party API key), return `None`
to mark it as skipped. Skipped metrics are shown in the CLI output.

## Best Practices

### Scoring Guidelines

✅ **DO:**

- Use **0-10 scale** for all metrics
- Set `max_score = 10` (consistency)
- Use graduated thresholds (e.g., 10, 8, 5, 2, 0)
- Return meaningful default scores for missing data
- Return `None` only for intentionally skipped metrics (for example, optional API keys)

❌ **DON'T:**

- Use arbitrary max_score values
- Raise exceptions for missing data
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
    result = check_metric(_vcs_data(), MetricContext(...))
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

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData


class CodeCoverageChecker(MetricChecker):
    """Detect coverage signals from repository metadata."""

    def check(
        self, vcs_data: VCSRepositoryData, _context: MetricContext
    ) -> Metric | None:
        """
        Evaluates code coverage percentage.

        Scoring:
        - 90-100%: 10/10 (Excellent)
        - 70-89%: 7/10 (Good)
        - 50-69%: 4/10 (Moderate)
        - <50%: 1/10 (Needs attention)
        """
        description = (vcs_data.description or "").lower()
        topics = [topic.lower() for topic in vcs_data.topics]

        if "coverage" in description or "coverage" in topics:
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
    checker=CodeCoverageChecker(),
)
```

### Example 2: Dependency Update Frequency

```python
"""Dependency update frequency metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData


class DependencyUpdatesChecker(MetricChecker):
    """Detect dependency update activity via bot authors."""

    def check(
        self, vcs_data: VCSRepositoryData, _context: MetricContext
    ) -> Metric | None:
        """
        Evaluates how frequently dependencies are updated.

        Looks for bot-style commit authors (Dependabot, Renovate, etc.).
        """
        commits = vcs_data.commits

        if not commits:
            return Metric(
                "Dependency Updates",
                5,
                10,
                "Note: No commit history available.",
                "None",
            )

        dep_keywords = ["dependabot", "renovate", "github-actions", "ci-"]
        dep_commits = []
        for commit in commits:
            author = commit.get("author", {})
            name = (author.get("name") or "").lower()
            email = (author.get("email") or "").lower()
            user = author.get("user") or {}
            login = (user.get("login") or "").lower()

            if any(
                keyword in name or keyword in email or keyword in login
                for keyword in dep_keywords
            ):
                dep_commits.append(commit)

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
            message = (
                f"Needs attention: Only {percentage:.1f}% of commits are dependency updates."
            )

        return Metric("Dependency Updates", score, 10, message, risk)


METRIC = MetricSpec(
    name="Dependency Updates",
    checker=DependencyUpdatesChecker(),
)
```

### Example 3: CHAOSS-Aligned Metric

```python
"""Technical fork metric aligned with CHAOSS."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData


class TechnicalForkChecker(MetricChecker):
    """Evaluate fork activity via normalized VCS data."""

    def check(
        self, vcs_data: VCSRepositoryData, _context: MetricContext
    ) -> Metric | None:
        """
        Evaluates technical fork activity (downstream projects).

        CHAOSS Aligned: Technical Fork
        https://chaoss.community/kb/metric-technical-fork/

        Measures project reuse and impact via fork count.
        """
        forks = vcs_data.total_forks
        stargazers = vcs_data.star_count

        if stargazers > 0:
            fork_ratio = forks / stargazers
        else:
            fork_ratio = 0

        if fork_ratio >= 0.5:
            score = 10
            risk = "None"
            message = (
                f"Excellent: High fork activity ({forks} forks, {fork_ratio:.1%} ratio)."
            )
        elif fork_ratio >= 0.2:
            score = 7
            risk = "Low"
            message = (
                f"Good: Moderate fork activity ({forks} forks, {fork_ratio:.1%} ratio)."
            )
        elif fork_ratio >= 0.1:
            score = 4
            risk = "Medium"
            message = (
                f"Moderate: Some fork activity ({forks} forks, {fork_ratio:.1%} ratio)."
            )
        else:
            score = 1
            risk = "High"
            message = f"Low: Limited fork activity ({forks} forks, {fork_ratio:.1%} ratio)."

        return Metric("Technical Fork", score, 10, message, risk)


METRIC = MetricSpec(
    name="Technical Fork",
    checker=TechnicalForkChecker(),
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
