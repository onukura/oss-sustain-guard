# Scoring Profiles Guide

OSS Sustain Guard provides multiple **scoring profiles** to evaluate projects based on different priorities. Each profile adjusts the weight of sustainability categories to match specific use cases.

## Available Profiles

### 1. **Balanced** (Default)

A balanced view across all sustainability dimensions.

**Category Weights:**

- Maintainer Health: 25%
- Development Activity: 20%
- Community Engagement: 25% ⬆️ (increased from 20%)
- Project Maturity: 15%
- Security & Funding: 15% ⬇️ (decreased from 20%)

**Best for:** General-purpose evaluation, understanding overall project health.

---

### 2. **Security First**

Prioritizes security and risk mitigation.

**Category Weights:**

- **Security & Funding: 30%** ⬆️ (adjusted)
- Maintainer Health: 20%
- Development Activity: 15%
- Community Engagement: 20%
- Project Maturity: 15%

**Best for:**

- Enterprise deployments
- Security-critical applications
- Compliance requirements
- Risk assessment for production systems

**Example:** If you're evaluating a cryptography library or authentication service, this profile emphasizes security posture and funding stability.

---

### 3. **Contributor Experience**

Focuses on community engagement and contributor-friendliness.

**Category Weights:**

- **Community Engagement: 45%** ⬆️ (highest priority)
- Project Maturity: 15%
- Maintainer Health: 15%
- Development Activity: 15%
- Security & Funding: 10%

**Best for:**

- First-time contributors looking for welcoming projects
- Evaluating community health
- Open-source mentorship programs
- Projects seeking contributor-friendly dependencies

**Example:** If you're looking for a project to contribute to, this profile highlights responsive maintainers and good PR acceptance rates.

---

### 4. **Long-term Stability**

Emphasizes maintainer health and sustainable development.

**Category Weights:**

- **Maintainer Health: 35%** ⬆️ (highest priority)
- Development Activity: 25%
- Community Engagement: 15%
- Project Maturity: 15%
- Security & Funding: 10%

**Best for:**

- Long-term dependencies in critical infrastructure
- Evaluating bus factor and maintainer retention
- Projects with multi-year roadmaps
- Avoiding maintainer burnout risks

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
  Prioritizes security and risk mitigation

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
| **Security audit** | `security_first` | Highlights vulnerabilities and funding risks |
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

While not directly exposed in the API yet, you can modify `SCORING_PROFILES` in `core.py` to create custom profiles:

```python
# Future enhancement (not yet implemented)
SCORING_PROFILES["custom_enterprise"] = {
    "name": "Enterprise Custom",
    "description": "Custom profile for enterprise evaluation",
    "weights": {
        "Maintainer Health": 0.30,
        "Development Activity": 0.20,
        "Community Engagement": 0.05,
        "Project Maturity": 0.25,
        "Security & Funding": 0.20,
    },
}
```

---

## Integration with CLI

The CLI currently uses the **balanced** profile by default. Future enhancements will support profile selection:

```bash
# Future feature (not yet implemented)
oss-sustain-guard check --profile security_first requests
oss-sustain-guard check --compare-profiles django
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

### Category Breakdown

All profiles use the same **5 categories** with different weights:

1. **Maintainer Health** - Bus factor, retention, diversity
2. **Development Activity** - Releases, CI, recent activity
3. **Community Engagement** - Responsiveness, PR handling, issue resolution
4. **Project Maturity** - Documentation, governance, adoption
5. **Security & Funding** - Security posture, funding signals

### Score Calculation

1. Each category is normalized to 0-100 scale
2. Profile weights are applied to categories
3. Weighted sum produces total score (0-100)

Formula:

```shell
Total Score = Σ (Category_Score_normalized × Profile_Weight)
```

### Validation

All profile weights must sum to 1.0 (validated in tests).

---

## See Also

- [Database Schema](DATABASE_SCHEMA.md) - Stored metric details
- [CHAOSS Metrics Alignment](CHAOSS_METRICS_ALIGNMENT_VALIDATION.md) - Metric definitions
