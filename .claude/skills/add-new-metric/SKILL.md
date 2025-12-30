---
name: add-new-metric
description: Guide for adding new sustainability metrics to OSS Sustain Guard. Use this when the user wants to implement a new metric function that evaluates a specific aspect of open-source project health (e.g., issue responsiveness, test coverage, security response time, etc.).
---

# Add New Metric

This skill provides a systematic workflow for adding new sustainability metrics to the OSS Sustain Guard project.

## When to Use

- User wants to add a new metric to evaluate project health
- Implementing metrics from NEW_METRICS_IDEA.md
- Extending analysis capabilities with additional measurements

## Critical Principles

1. **No Duplication**: Always check existing metrics to avoid measuring the same thing
2. **100-Point Budget**: Total max scores must sum to ≤100 across all metrics
3. **Project Philosophy**: Use "observation" language, not "risk" or "critical"
4. **CHAOSS Alignment**: Reference CHAOSS metrics when applicable

## Implementation Workflow

### 1. Verify No Duplication

```bash
# Search for similar metrics
grep -n "def check_" oss_sustain_guard/core.py
grep -n "return Metric(" oss_sustain_guard/core.py | grep "MetricName"
```

**Check**: Does any existing metric measure the same aspect?

### 2. Design Metric Function

**Template**:
```python
def check_my_metric(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates [metric purpose].

    [Description of what this measures and why it matters.]

    Scoring:
    - [Condition]: X/Y ([Label])
    - [Condition]: X/Y ([Label])

    CHAOSS Aligned: [CHAOSS metric name] (if applicable)
    """
    from datetime import datetime

    max_score = 5  # Adjust based on importance

    # Extract data from repo_data
    data = repo_data.get("fieldName", {})

    if not data:
        return Metric(
            "My Metric Name",
            score_on_no_data,
            max_score,
            "Note: [Reason for default score].",
            "None",
        )

    # Calculate metric
    # ...

    # Score logic with graduated thresholds
    if condition_excellent:
        score = max_score
        risk = "None"
        message = f"Excellent: [Details]."
    elif condition_good:
        score = max_score * 0.8
        risk = "Low"
        message = f"Good: [Details]."
    elif condition_moderate:
        score = max_score * 0.4
        risk = "Medium"
        message = f"Moderate: [Details]."
    else:
        score = max_score * 0.2
        risk = "High"
        message = f"Observe: [Details]. Consider improving."

    return Metric("My Metric Name", score, max_score, message, risk)
```

**Key Decisions**:
- `max_score`: Typically 5, 10, or 20 based on importance
- Risk levels: "None", "Low", "Medium", "High", "Critical"
- Use supportive language: "Observe", "Consider", "Monitor" not "Failed", "Error"

### 3. Integrate into Analysis Pipeline

Add to `_analyze_repository_data()` in `core.py`:

```python
try:
    metrics.append(check_my_metric(repo_info))
except Exception as e:
    # Silently capture error in metric message
    metrics.append(
        Metric(
            "My Metric Name",
            0,
            max_score,
            f"Note: Analysis incomplete - {e}",
            "Medium",
        )
    )
```

**Location**: After `check_ci_status()`, before dependents analysis

### 4. Verify Total Score Budget

```python
# Calculate total possible score
total_max = 20 + 10 + 20 + 10 + 10 + 10 + 5 + 5 + ...
# Must be ≤ 100
```

**Adjust if needed**: Reduce max_score proportionally across metrics

### 5. Test Implementation

```bash
# Syntax check
python -m py_compile oss_sustain_guard/core.py

# Run analysis on test project
uv run os4g check fastapi --insecure --no-cache -o detail

# Verify metric appears in output
# Check score is reasonable

# Run unit tests
uv run pytest tests/test_core.py -x --tb=short

# Lint check
uv run ruff check oss_sustain_guard/core.py
```

### 6. Update Documentation (if needed)

Consider updating:
- `docs/local/NEW_METRICS_IDEA.md` - Mark as implemented
- Metric count in README.md

## Common Metric Patterns

### Time-Based Metrics

```python
from datetime import datetime

created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
completed_at = datetime.fromisoformat(completed_str.replace("Z", "+00:00"))
duration_days = (completed_at - created_at).total_seconds() / 86400
```

### Ratio/Percentage Metrics

```python
ratio = (count_a / total) * 100
# Use graduated scoring
if ratio < 15:
    score = max_score  # Excellent
elif ratio < 30:
    score = max_score * 0.6  # Acceptable
```

### Median Calculations

```python
values.sort()
median = (
    values[len(values) // 2]
    if len(values) % 2 == 1
    else (values[len(values) // 2 - 1] + values[len(values) // 2]) / 2
)
```

### GraphQL Data Access

```python
# Common paths in repo_data
issues = repo_data.get("issues", {}).get("edges", [])
prs = repo_data.get("pullRequests", {}).get("edges", [])
commits = repo_data.get("defaultBranchRef", {}).get("target", {}).get("history", {})
funding = repo_data.get("fundingLinks", [])
```

## Score Budget Guidelines

| Importance | Max Score | Use Case |
|-----------|-----------|----------|
| Critical | 20 | Core sustainability (Bus Factor, Activity) |
| High | 10 | Important health signals (Funding, Retention) |
| Medium | 5 | Supporting metrics (CI, Community Health) |
| Low | 3-5 | Supplementary observations |

**Total Budget**: 100 points across ~20-25 metrics

## Validation Checklist

- [ ] No duplicate measurement with existing metrics
- [ ] Total max_score budget ≤ 100
- [ ] Uses supportive "observation" language
- [ ] Has graduated scoring (not binary)
- [ ] Handles missing data gracefully
- [ ] Error handling in integration
- [ ] Syntax check passes
- [ ] Real-world test shows metric in output
- [ ] Unit tests pass
- [ ] Lint checks pass

## Example: Stale Issue Ratio

```python
def check_stale_issue_ratio(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates Stale Issue Ratio - percentage of issues not updated in 90+ days.

    Measures how well the project manages its issue backlog.
    High stale issue ratio indicates potential burnout or backlog accumulation.

    Scoring:
    - <15% stale: 5/5 (Healthy backlog management)
    - 15-30% stale: 3/5 (Acceptable)
    - 30-50% stale: 2/5 (Needs attention)
    - >50% stale: 1/5 (Significant backlog challenge)

    CHAOSS Aligned: Issue aging and backlog management
    """
    from datetime import datetime, timedelta

    max_score = 5

    closed_issues = repo_data.get("closedIssues", {}).get("edges", [])

    if not closed_issues:
        return Metric(
            "Stale Issue Ratio",
            max_score // 2,
            max_score,
            "Note: No closed issues in recent history.",
            "None",
        )

    stale_count = 0
    current_time = datetime.now(datetime.now().astimezone().tzinfo)
    stale_threshold = current_time - timedelta(days=90)

    for edge in closed_issues:
        node = edge.get("node", {})
        updated_at_str = node.get("updatedAt") or node.get("closedAt")

        if not updated_at_str:
            continue

        try:
            updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            if updated_at < stale_threshold:
                stale_count += 1
        except (ValueError, AttributeError):
            pass

    total_issues = len(closed_issues)
    if total_issues == 0:
        return Metric(
            "Stale Issue Ratio",
            5,
            max_score,
            "Note: Unable to calculate stale issue ratio.",
            "None",
        )

    stale_ratio = (stale_count / total_issues) * 100

    # Scoring logic
    if stale_ratio < 15:
        score = max_score
        risk = "None"
        message = f"Healthy: {stale_ratio:.1f}% of issues are stale (90+ days inactive)."
    elif stale_ratio < 30:
        score = 3
        risk = "Low"
        message = f"Acceptable: {stale_ratio:.1f}% of issues are stale."
    elif stale_ratio < 50:
        score = 2
        risk = "Medium"
        message = f"Observe: {stale_ratio:.1f}% of issues are stale. Consider review."
    else:
        score = 1
        risk = "High"
        message = f"Significant: {stale_ratio:.1f}% of issues are stale. Backlog accumulation evident."

    return Metric("Stale Issue Ratio", score, max_score, message, risk)
```

## Troubleshooting

**Score exceeds 100**: Reduce max_score values proportionally
**Metric not appearing**: Check integration in `_analyze_repository_data()`
**Tests fail**: Update expected metric names in test files
**Data not available**: Add proper null checks and default handling
