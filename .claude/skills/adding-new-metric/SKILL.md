---
name: adding-new-metric
description: Guides systematic implementation of new sustainability metrics in OSS Sustain Guard. Use when adding metric functions to evaluate project health aspects like issue responsiveness, test coverage, or security response time.
---

# Add New Metric

This skill provides a systematic workflow for adding new sustainability metrics to the OSS Sustain Guard project.

## When to Use

- User wants to add a new metric to evaluate project health
- Implementing metrics from NEW_METRICS_IDEA.md
- Extending analysis capabilities with additional measurements

## Critical Principles

1. **No Duplication**: Always check existing metrics to avoid measuring the same thing
2. **10-Point Scale**: ALL metrics use max_score=10 for consistency and transparency
3. **Integer Weights**: Metric importance is controlled via profile weights (integers ≥1)
4. **Project Philosophy**: Use "observation" language, not "risk" or "critical"
5. **CHAOSS Alignment**: Reference CHAOSS metrics when applicable

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

    max_score = 10  # ALWAYS use 10 for all metrics

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

    # Score logic with graduated thresholds (0-10 scale)
    if condition_excellent:
        score = 10  # Excellent
        risk = "None"
        message = f"Excellent: [Details]."
    elif condition_good:
        score = 8  # Good (80%)
        risk = "Low"
        message = f"Good: [Details]."
    elif condition_moderate:
        score = 5  # Moderate (50%)
        risk = "Medium"
        message = f"Moderate: [Details]."
    elif condition_needs_attention:
        score = 2  # Needs attention (20%)
        risk = "High"
        message = f"Observe: [Details]. Consider improving."
    else:
        score = 0  # Critical issue
        risk = "Critical"
        message = f"Note: [Details]. Immediate attention recommended."

    return Metric("My Metric Name", score, max_score, message, risk)
```

**Key Decisions**:
- `max_score`: **ALWAYS 10** for all metrics (consistency)
- Score range: **0-10** (use integers or decimals)
- Importance: Controlled by **profile weights** (integers ≥1)
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

### 4. Add Metric to Scoring Profiles

Update `SCORING_PROFILES` in `core.py` to include your new metric:

```python
SCORING_PROFILES = {
    "balanced": {
        "name": "Balanced",
        "description": "...",
        "weights": {
            # Existing metrics...
            "Contributor Redundancy": 3,
            "Security Signals": 2,
            # Add your new metric
            "My Metric Name": 2,  # Assign appropriate weight (1+)
            # ...
        },
    },
    # Update all 4 profiles...
}
```

**Weight Guidelines**:
- **Critical metrics**: 3-5 (bus factor, security)
- **Important metrics**: 2-3 (activity, responsiveness)
- **Supporting metrics**: 1-2 (documentation, governance)

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

For a complete, production-ready implementation example, see [examples/stale-issue-ratio.md](examples/stale-issue-ratio.md).

**Quick overview:**
- **Measures**: Percentage of issues not updated in 90+ days
- **Max Score**: 5 points
- **Scoring**: <15% stale (5pts), 15-30% (3pts), 30-50% (2pts), >50% (1pt)
- **Key patterns**: Time-based calculation, graduated scoring, graceful error handling
- **Real results**: fastapi (8.2% stale, 5/5), requests (23.4%, 3/5)

## Score Validation with Real Projects

After implementing a new metric, validate scoring behavior with diverse real-world projects.

### Validation Script

Create `scripts/validate_scoring.py`:

```python
#!/usr/bin/env python3
"""
Score validation script for testing new metrics against diverse projects.

Usage:
    uv run python scripts/validate_scoring.py
"""

import subprocess
import json
from typing import Any

VALIDATION_PROJECTS = {
    "Famous/Mature": {
        "requests": "psf/requests",
        "react": "facebook/react",
        "kubernetes": "kubernetes/kubernetes",
        "django": "django/django",
        "fastapi": "fastapi/fastapi",
    },
    "Popular/Active": {
        "angular": "angular/angular",
        "numpy": "numpy/numpy",
        "pandas": "pandas-dev/pandas",
    },
    "Emerging/Small": {
        # Add smaller projects you want to test
    },
}

def analyze_project(owner: str, repo: str) -> dict[str, Any]:
    """Run analysis on a project and return results."""
    cmd = [
        "uv", "run", "os4g", "check",
        f"{owner}/{repo}",
        "--insecure", "--no-cache", "-o", "json"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return {"error": result.stderr}

    # Parse JSON output
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON output"}

def main():
    print("=" * 80)
    print("OSS Sustain Guard - Score Validation Report")
    print("=" * 80)
    print()

    for category, projects in VALIDATION_PROJECTS.items():
        print(f"\n## {category}\n")
        print(f"{'Project':<25} {'Score':<10} {'Status':<15} {'Key Observations'}")
        print("-" * 80)

        for name, repo_path in projects.items():
            result = analyze_project(*repo_path.split("/"))

            if "error" in result:
                print(f"{name:<25} {'ERROR':<10} {result['error'][:40]}")
                continue

            score = result.get("total_score", 0)
            status = "✓ Healthy" if score >= 80 else "⚠ Monitor" if score >= 60 else "⚡ Needs attention"
            observations = result.get("key_observations", "N/A")[:40]

            print(f"{name:<25} {score:<10} {status:<15} {observations}")

    print("\n" + "=" * 80)
    print("\nValidation complete. Review scores for:")
    print("  - Famous projects should score 70-95")
    print("  - New metrics should show reasonable distribution")
    print("  - No project should score >100")

if __name__ == "__main__":
    main()
```

### Quick Validation Command

```bash
# Test specific famous projects
uv run os4g check requests react fastapi kubernetes --insecure --no-cache

# Compare before/after metric changes
uv run os4g check requests --insecure --no-cache -o detail > before.txt
# ... make changes ...
uv run os4g check requests --insecure --no-cache -o detail > after.txt
diff before.txt after.txt
```

### Expected Score Ranges

| Category | Expected Score | Examples |
|----------|----------------|----------|
| Famous/Mature | 75-95 | requests, kubernetes, react |
| Popular/Active | 65-85 | angular, numpy, pandas |
| Emerging/Small | 45-70 | New projects with activity |
| Problematic | 20-50 | Abandoned or struggling projects |

### Validation Checklist

After implementing a new metric:

- [ ] Test on 3-5 famous projects (requests, react, kubernetes, etc.)
- [ ] Verify scores remain within 0-100
- [ ] Check that famous projects score reasonably high (70+)
- [ ] Ensure new metric contributes meaningfully to total score
- [ ] Review that metric differentiates well between projects
- [ ] Confirm no single metric dominates the total score

## Troubleshooting

**Score calculation issues**: Verify all metrics have max_score=10 and check profile weights
**Metric not appearing**: Check integration in `_analyze_repository_data()`
**Tests fail**: Update expected metric names in test files
**Data not available**: Add proper null checks and default handling
**Scores too similar across projects**: Adjust scoring thresholds for better differentiation
**Famous project scores low**: Review metric logic and thresholds
