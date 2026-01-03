# Scoring Profiles Guide

OSS Sustain Guard provides multiple **scoring profiles** to evaluate projects based on different priorities. Each profile assigns **integer weights** (≥1) to individual metrics to reflect their relative importance.

## Scoring System Overview

- **All metrics are scored on a 0-10 scale** for consistency and transparency
- **Weights are integers (1+)** that determine relative importance per metric
- **Total score formula**: `Sum(metric_score × weight) / Sum(10 × weight) × 100`
- **Result**: Normalized 0-100 score for easy comparison

**Example Calculation:**

```
Metric A: score=8, weight=3  →  8×3 = 24
Metric B: score=6, weight=2  →  6×2 = 12
Metric C: score=10, weight=1 → 10×1 = 10
────────────────────────────────────────
Total: (24+12+10) / (3×10 + 2×10 + 1×10) × 100
     = 46 / 60 × 100 = 76.7 ≈ 77/100
```

## Available Profiles

### 1. **Balanced** (Default)

A balanced view across all sustainability dimensions.

**Metric Emphasis (Key Weights):**

- Contributor Redundancy: 3 (High priority - bus factor)
- Recent Activity: 3 (Key for active development)
- Security Signals: 2 (Balanced security focus)
- Community Health: 2 (Issue responsiveness)
- Other metrics: 1-2 (Proportional importance)

**Best for:** General-purpose evaluation, understanding overall project health.

---

### 2. **Security First**

Prioritizes security and resilience.

**Metric Emphasis (Key Weights):**

- **Security Signals: 5** ⬆️ (Highest priority - vulnerabilities)
- **Funding Signals: 3** (Sustainability via funding)
- Build Health: 3 (CI/CD reliability)
- Contributor Redundancy: 2 (Maintainer security)
- Other metrics: 1-2 (Balanced coverage)

**Best for:**

- Enterprise deployments
- Security-sensitive applications
- Compliance requirements
- Stability assessment for production systems

**Example:** If you're evaluating a cryptography library or authentication service, this profile emphasizes security posture and funding stability.

---

### 3. **Contributor Experience**

Focuses on community engagement and contributor-friendliness.

**Metric Emphasis (Key Weights):**

- **Community Health: 4** ⬆️ (Community engagement)
- **PR Acceptance Ratio: 4** (Welcoming to contributors)
- **Review Health: 3** (Code review quality)
- **PR Responsiveness: 3** (Fast feedback)
- Documentation Presence: 2 (Onboarding ease)
- Other metrics: 1-2 (Supporting factors)

**Best for:**

- First-time contributors looking for welcoming projects
- Evaluating community health
- Open-source mentorship programs
- Projects seeking contributor-friendly dependencies

**Example:** If you're looking for a project to contribute to, this profile highlights responsive maintainers and good PR acceptance rates.

---

### 4. **Long-term Stability**

Emphasizes maintainer health and sustainable development.

**Metric Emphasis (Key Weights):**

- **Contributor Redundancy: 5** ⬆️ (Bus factor - key signal)
- **Maintainer Retention: 4** (Team stability)
- **Contributor Attraction: 3** (Pipeline health)
- **Organizational Diversity: 3** (Ownership distribution)
- Recent Activity: 3 (Consistent development)
- Other metrics: 1-2 (Holistic view)

**Best for:**

- Long-term dependencies in core infrastructure
- Evaluating contributor redundancy and maintainer retention
- Projects with multi-year roadmaps
- Avoiding maintainer burnout concerns

**Example:** If you're choosing a core framework for a 5-year project, this profile emphasizes contributor diversity and maintainer retention.

---

## Usage Examples

### Python API

```python
from oss_sustain_guard.core import analyze_repository, compute_weighted_total_score

# Analyze a repository
result = analyze_repository("psf", "requests")

# Get score with different profiles
balanced_score = compute_weighted_total_score(result.metrics, "balanced")
security_score = compute_weighted_total_score(result.metrics, "security_first")
contributor_score = compute_weighted_total_score(result.metrics, "contributor_experience")
stability_score = compute_weighted_total_score(result.metrics, "long_term_stability")

print(f"Balanced: {balanced_score}/100")
print(f"Security First: {security_score}/100")
print(f"Contributor Experience: {contributor_score}/100")
print(f"Long-term Stability: {stability_score}/100")
```

### Compare All Profiles

```python
from oss_sustain_guard.core import compare_scoring_profiles, analyze_repository

result = analyze_repository("django", "django")
comparison = compare_scoring_profiles(result.metrics)

for profile_key, data in comparison.items():
    print(f"\n{data['name']} ({profile_key})")
    print(f"  Score: {data['total_score']}/100")
    print(f"  {data['description']}")
```

**Example Output:**

```shell
Balanced (balanced)
  Score: 85/100
  Balanced view across all sustainability dimensions

Security First (security_first)
  Score: 88/100
  Prioritizes security and resilience

Contributor Experience (contributor_experience)
  Score: 90/100
  Focuses on community engagement and contributor-friendliness

Long-term Stability (long_term_stability)
  Score: 83/100
  Emphasizes maintainer health and sustainable development
```

---

## Choosing the Right Profile

| Use Case | Recommended Profile | Why |
|----------|---------------------|-----|
| **General evaluation** | `balanced` | Provides holistic view |
| **Security audit** | `security_first` | Highlights vulnerabilities and funding gaps |
| **Finding projects to contribute to** | `contributor_experience` | Shows responsive, welcoming communities |
| **Choosing core dependencies** | `long_term_stability` | Emphasizes maintainer diversity and retention |
| **Open-source program office** | Compare all | See different perspectives |

---

## Profile Comparison Strategy

When evaluating a project, consider running **multiple profiles** to get different perspectives:

1. **Start with `balanced`** - Get a general understanding
2. **Apply domain-specific profile** - Match your use case
3. **Compare scores** - Understand trade-offs

**Example Scenario:**

You're evaluating a web framework for a new project:

```python
comparison = compare_scoring_profiles(result.metrics)

# Django scores
# balanced: 85/100
# security_first: 88/100
# contributor_experience: 90/100
# long_term_stability: 83/100

# Analysis:
# ✅ Excellent security and community engagement
# ⚠️  Slightly lower long-term stability score
# → Check: maintainer diversity and retention metrics
```

---

## Understanding Score Differences

Different profiles can produce significantly different scores:

| Project Type | Balanced | Security First | Contributor Exp | Long-term Stability |
|--------------|----------|----------------|-----------------|---------------------|
| **Corporate-backed** | 75 | 85 | 65 | 70 |
| **Community-driven** | 80 | 70 | 90 | 85 |
| **Security-focused** | 85 | 95 | 75 | 80 |
| **New project** | 60 | 55 | 70 | 50 |

**Interpretation:**

- **Corporate-backed** projects score higher on security (resources for audits)
- **Community-driven** projects excel in contributor experience (welcoming culture)
- **Security-focused** libraries prioritize security metrics
- **New projects** may lack history for long-term stability assessment

---

## Advanced Usage: Custom Weights

### Method 1: Configuration File (Recommended)

Define custom profiles in `.oss-sustain-guard.toml` or `pyproject.toml`:

```toml
# .oss-sustain-guard.toml
[tool.oss-sustain-guard.profiles.my_custom]
name = "My Custom Profile"
description = "Custom scoring focused on specific needs"

[tool.oss-sustain-guard.profiles.my_custom.weights]
"Contributor Redundancy" = 5
"Security Signals" = 4
"Recent Activity" = 3
"Maintainer Retention" = 3
"Funding Signals" = 2
"Build Health" = 2
"Community Health" = 2
"PR Acceptance Ratio" = 2
"Review Health" = 2
"PR Responsiveness" = 2
"Documentation Presence" = 2
"License Clarity" = 2
"Organizational Diversity" = 2
"Contributor Attraction" = 2
"Release Rhythm" = 1
"Test Coverage" = 1
"Dependency Health" = 1
"Code Quality" = 1
"Security Response" = 1
"Code of Conduct" = 1
"Community Diversity" = 1
"Contributor Growth" = 1
"Project Maturity" = 1
"Release Freshness" = 1
```

**Usage:**

```bash
# Automatically uses profile from .oss-sustain-guard.toml
os4g check --profile my_custom requests

# Or use external profile file
os4g check --profile-file my_profiles.toml --profile my_custom requests
```

**Priority Order:**

1. `--profile-file` (if specified)
2. `.oss-sustain-guard.toml` (local config)
3. `pyproject.toml` (project-level config)

### Method 2: Python Code

You can modify `SCORING_PROFILES` in `core.py` to create custom profiles:

```python
SCORING_PROFILES["custom_enterprise"] = {
    "name": "Enterprise Custom",
    "description": "Custom profile for enterprise evaluation",
    "weights": {
        # Security-focused metrics (high weights)
        "Security Signals": 5,
        "Funding Signals": 4,
        "Build Health": 3,

        # Maintainer health (moderate weights)
        "Contributor Redundancy": 3,
        "Maintainer Retention": 2,
        "Organizational Diversity": 2,

        # Other metrics (standard weights)
        "Recent Activity": 2,
        "Release Rhythm": 2,
        "Documentation Presence": 2,
        "License Clarity": 2,

        # Lower priority for community metrics
        "Community Health": 1,
        "PR Acceptance Ratio": 1,
        # ... (include all 24 core metrics)
    },
}
```

**Important:** All metrics must have a weight ≥1.

---

## Integration with CLI

The CLI supports profile selection via the `--profile` flag:

```bash
# Use specific profile
os4g check --profile security_first requests
os4g check --profile contributor_experience django
os4g check --profile long_term_stability flask

# Compare all profiles (Python API)
python -c "from oss_sustain_guard.core import analyze_repository, compare_scoring_profiles; \
  result = analyze_repository('psf', 'requests'); \
  print(compare_scoring_profiles(result.metrics))"
```

---

## Tuning and Feedback

The current weights are based on CHAOSS metrics and sustainability best practices. We welcome feedback:

1. **Report score discrepancies** - If a profile doesn't match your expectations
2. **Suggest new profiles** - For specific use cases (e.g., "academic research", "startup dependencies")
3. **Contribute weight adjustments** - Based on data analysis

See [Contributing Guide](GETTING_STARTED.md) for how to provide feedback.

---

## Technical Details

### Metric-Level Weighting

All profiles assign **individual weights to each metric** (not categories):

- **24 core metrics** evaluated per repository
- Each metric scored **0-10** (normalized scale)
- Weights are **integers ≥1** per metric
- Different profiles emphasize different metrics

**Example Metrics:**

- Contributor Redundancy, Maintainer Retention, Recent Activity
- Security Signals, Funding Signals, Build Health
- Community Health, PR Acceptance Ratio, Review Health
- Documentation Presence, License Clarity, Code of Conduct
- And more...

### Score Calculation

1. Each metric produces a score (0-10)
2. Profile weights are applied to individual metrics
3. Weighted sum is normalized to 0-100 scale

Formula:

```python
Total Score = Sum(metric_score × metric_weight) / Sum(10 × metric_weight) × 100
```

**Worked Example:**

```
# Balanced profile with 3 metrics:
Contributor Redundancy: 8/10, weight=3  →  8×3 = 24
Security Signals: 10/10, weight=2       → 10×2 = 20
Recent Activity: 6/10, weight=2         →  6×2 = 12
                                           ──────
Total: (24+20+12) / (10×3 + 10×2 + 10×2) × 100
     = 56 / 70 × 100 = 80/100
```

### Validation

All profile weights are positive integers (validated in tests):

```python
for metric_name, weight in profile["weights"].items():
    assert isinstance(weight, int)
    assert weight >= 1
```

---

## See Also

- [CHAOSS Metrics Alignment](CHAOSS_METRICS_ALIGNMENT_VALIDATION.md) - Metric definitions
- [Exclude Packages Guide](EXCLUDE_PACKAGES_GUIDE.md) - Configuration management
