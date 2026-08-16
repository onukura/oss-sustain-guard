# Built-in Metrics Guide

This guide provides a comprehensive reference for all built-in metrics included in OSS Sustain Guard. Each metric evaluates a specific aspect of open-source project sustainability.

## 📋 Table of Contents

- [Overview](#overview)
- [Metrics by Category](#metrics-by-category)
- [Core Sustainability Metrics](#core-sustainability-metrics)
- [Community Engagement Metrics](#community-engagement-metrics)
- [Quality & Maintenance Metrics](#quality-maintenance-metrics)
- [Visibility & Adoption Metrics](#visibility-adoption-metrics)
- [Scoring System](#scoring-system)
- [Status Levels](#status-levels)

## Overview

OSS Sustain Guard evaluates projects across **24+ built-in metrics** organized into four categories:

| Category | Focus | Purpose |
| ---------- | ------- | --------- |
| **Sustainability** | Financial, Maintainers, Releases | Long-term viability |
| **Community** | Contributors, Responsiveness | Ecosystem health |
| **Quality** | Build, Security, Code | Project excellence |
| **Visibility** | Popularity, Dependencies | Adoption & impact |

All metrics use a **0-10 scale** with supportive messaging. Metrics are combined into "Metrics Models" for holistic assessment.

## Metrics by Category

### Core Sustainability Metrics

Essential metrics for project viability:

- [Contributor Redundancy](#contributor-redundancy)
- [Commit Author Continuity](#commit-author-continuity)
- [Release Rhythm](#release-rhythm)
- [Funding Signals](#funding-signals)

### Community Engagement Metrics

Evaluate community health and contributor health:

- [Contributor Attraction](#contributor-attraction)
- [Contributor Retention](#contributor-retention)
- [Community Health](#community-health)
- [Change Request Resolution](#change-request-resolution)
- [Review Health](#review-health)

### Quality & Maintenance Metrics

Assess code quality and maintenance practices:

- [Build Health](#build-health)
- [Security Signals](#security-signals)
- [Code of Conduct](#code-of-conduct)
- [License Clarity](#license-clarity)
- [Documentation Presence](#documentation-presence)
- [Stale Issue Ratio](#stale-issue-ratio)

### Visibility & Adoption Metrics

Measure project impact and ecosystem integration:

- [Project Popularity](#project-popularity)
- [Fork Activity](#fork-activity)
- [PR Acceptance Ratio](#pr-acceptance-ratio)
- [PR Merge Speed](#pr-merge-speed)
- [PR Responsiveness](#pr-responsiveness)
- [Organizational Diversity](#organizational-diversity)
- [Single Maintainer Load](#single-maintainer-load)

---

## Core Sustainability Metrics

### Contributor Redundancy

**Alternative Name:** Bus Factor (Estimated)

**Purpose:** Evaluates whether the project depends on a single contributor or has a healthy distribution.

**⚠️ Important Limitations:**

This metric is **estimated from public commit history only** and has significant limitations:

- **Cannot see internal Git mirrors** - Many organizations use internal Git systems that sync to public repos, making contribution patterns appear more concentrated than reality
- **Code-only view** - Ignores non-code contributions like documentation, issue triage, community management, and project governance
- **No organizational context** - Cannot detect succession planning, knowledge transfer practices, or full-time maintainer status
- **Snapshot, not trajectory** - Recent patterns may not reflect long-term team structure or onboarding efforts

**Use this metric as a signal to investigate further, not as a definitive assessment.** Projects with a single dominant contributor may have:

- Strong corporate backing with internal teams
- Active mentorship and onboarding processes
- Clear governance and succession plans
- Other forms of redundancy not visible in commit history

**Data Source:** Commit history (recent commits analyzed)

**Calculation:**

- Identifies top contributor percentage from recent commits
- Adjusts scoring based on project maturity (total commits)
- Analyzes contributor diversity trend

**Scoring:**

- <50% by single contributor: 10/10 (Excellent - healthy diversity)
- 50-69% concentration: 5/10 (Moderate - acceptable)
- 70-89% concentration: 3/10 (Needs attention - concentrated contributions)
- 90%+ concentration: 1/10 (Needs support - single point of failure)

**Status Levels:**

- **None:** <50% - Well-distributed contributions
- **Low:** 50-69% - Acceptable concentration
- **Medium:** 70-89% - Elevated concentration
- **High:** 90%+ - Significant dependency concentration

**CHAOSS Alignment:** ✅ [Elephant Factor](https://chaoss.community/kb/metric-elephant-factor/), [Contributor Absence Factor](https://chaoss.community/kb/metric-contributor-absence-factor/)

**Use Case:** Organizations should prioritize projects with high redundancy to avoid single-maintainer concentration.

---

### Commit Author Continuity

**Former Name:** Maintainer Retention (a.k.a. Maintainer Drain) — renamed in v0.26.0, see [#11](https://github.com/onukura/oss-sustain-guard/issues/11)

**Purpose:** Tracks whether the people who were carrying the project are still carrying it.

**Data Source:** Commit authorship and PR merges over two 180-day windows, excluding automated accounts (bots)

**Calculation:**

- Splits history into a recent window (last 180 days) and a previous window (180-360 days ago)
- Filters out bot contributions (Dependabot, GitHub Actions, etc.)
- Merges email-only commit identities into the matching platform login
- Identifies the *principal committers* of the previous window: the fewest top authors holding a majority of its commits
- Counts a principal committer as retained if they authored a commit **or merged a PR** in the recent window (merge rights imply write access)

**Scoring:**

- 80%+ of principal committers retained: 10/10
- 50-79% retained: 7/10
- Under 50% retained: 4/10
- None retained, but commit volume held up (handover): 5/10
- None retained and commit volume collapsed: 0/10
- No human commit or merge in the recent window: 3/10 (0/10 after a full year)

**Status Levels:**

- **None:** Principal committers still active
- **Low:** Majority retained, worth watching
- **Medium:** Minority retained, or an unverified handover
- **High:** No maintainer activity in the last 180 days
- **Critical:** Core team gone, or no maintainer activity for over a year

**Insufficient data:** Projects whose commit sample does not reach back into the previous window — very busy repositories, or new ones — score 10/10 with a message stating that continuity could not be assessed. Unobservable is not the same as unhealthy.

**Limitations:** Commit authorship is a proxy for maintainer activity, not a role check. Maintainers who only triage issues or review code without merging are invisible here, and the commit sample is capped, so long-lived projects are only partially observed.

**CHAOSS Alignment:** ✅ [Inactive Contributors](https://chaoss.community/kb/metric-inactive-contributors/)

**Use Case:** Indicates project sustainability and the likelihood of maintenance burden shifts.

**Note:** This metric is excluded from `oss-guard trend`, because it needs about 12 months of history to compare its two windows and a single trend window does not provide that.

---

### Release Rhythm

**Alternative Name:** Release Cadence

**Purpose:** Measures consistency and frequency of project releases.

**Data Source:** GitHub Releases API

**Calculation:**

- Examines time since last release
- Evaluates release frequency pattern
- Distinguishes between "active development" and "stable maintenance"

**Scoring:**

- Last release <3 months ago: 10/10 (Active development)
- 3-6 months: 7/10 (Moderate pace)
- 6-12 months: 4/10 (Slow maintenance)
- >12 months: 0/10 (Possible abandonment)

**Special Cases:**

- Archived repositories: 10/10 (No releases expected)
- No releases: 0/10 (Project may not be user-ready)

**Status Levels:**

- **None:** Regular release cycles
- **Low:** Periodic releases
- **Medium:** Infrequent releases
- **High:** Abandoned release schedule

**CHAOSS Alignment:** ✅ [Release Frequency](https://chaoss.community/kb/metric-release-frequency/)

**Use Case:** Assess how quickly bug fixes and features reach users.

---

### Funding Signals

**Purpose:** Identifies financial sustainability indicators for community-driven projects and corporate backing for organization-backed projects.

**Data Source:** GitHub Sponsors, Open Collective, funding links; Organization ownership

**Calculation:**

- Detects explicit funding links (GitHub Sponsors, Open Collective, etc.)
- Identifies organization ownership (corporate backing)
- Applies different scoring for community vs. corporate projects

**Scoring - Community-Driven Projects:**

- Has funding links + organization backing: 10/10 (Well-supported)
- Has funding links only: 8/10 (Community-supported)
- No funding links: 0/10 (No visible sustainability model)

**Scoring - Corporate-Backed Projects:**

- Owned by organization: 10/10 (Corporate sustainability model)
- Funding links (optional): 10/10 (Regardless of explicit funding)

**Status Levels:**

- **None:** Clear sustainability model
- **Low:** Corporate backing present
- **Medium:** Some community funding
- **High/Needs support:** No sustainability signals

**CHAOSS Alignment:** ⚠️ Partial alignment with [Sponsorship](https://chaoss.community/kb/metric-sponsorship/) (focus on project sustainability vs. event sponsorship)

**Philosophy:** Recognizes that corporate-backed projects have different sustainability models than community-driven ones.

**Use Case:** Understand how projects sustain themselves and contribute to ecosystems.

---

## Community Engagement Metrics

### Contributor Attraction

**Purpose:** Measures the project's ability to attract new contributors.

**Data Source:** GitHub contributor data with creation date

**Calculation:**

- Counts new contributors joining in recent periods
- Normalizes by project age and history
- Detects if project is attracting fresh talent

**Scoring:**

- Growing contributor base: 10/10 (Healthy growth)
- Stable contributor acquisition: 7/10 (Good)
- Declining new contributors: 3/10 (Concerning trend)
- No new contributors: 0/10 (Not attracting talent)

**Status Levels:**

- **None:** Strong attraction of new contributors
- **Low:** Steady contributor growth
- **Medium:** Declining attraction
- **High:** Unable to attract contributors

**CHAOSS Alignment:** ✅ [New Contributors](https://chaoss.community/kb/metric-new-contributors/)

**Use Case:** Indicates project vitality and ability to grow its community.

---

### Contributor Retention

**Purpose:** Evaluates whether contributors continue engagement over time.

**Data Source:** Historical contributor activity and commit patterns

**Calculation:**

- Tracks contributors across multiple time periods
- Measures return rate (percentage returning after initial contribution)
- Identifies long-term vs. one-time contributors

**Scoring:**

- High retention rate (60%+): 10/10 (Strong community)
- Moderate retention (40-60%): 7/10 (Good)
- Low retention (20-40%): 3/10 (High churn)
- Minimal retention (<20%): 0/10 (One-time contributors only)

**Status Levels:**

- **None:** Strong contributor retention
- **Low:** Moderate churn
- **Medium:** Significant churn
- **High:** Severe contributor loss

**CHAOSS Alignment:** ✅ Inverse of [Inactive Contributors](https://chaoss.community/kb/metric-inactive-contributors/)

**Use Case:** Assess community stickiness and contributor satisfaction.

---

### Community Health

**Purpose:** Measures how quickly maintainers respond to issues.

**Data Source:** GitHub Issues API (creation date, first response date)

**Calculation:**

- Measures time from issue creation to first response
- Focuses on recent open issues with comments
- Treats low-issue volume as a healthy or early-stage signal

**Scoring:**

- Response within 48 hours: 10/10 (Excellent)
- <7 days: 6/10 (Good)
- 7-30 days: 2/10 (Needs attention)
- >30 days: 0/10 (Needs attention)

**Special Cases:**

- No open issues: 10/10 (Well-maintained or low activity)
- No recent responses: 6/10 (Limited response data)

**Status Levels:**

- **None:** Quick response times or low issue volume
- **Low:** Timely responses
- **Medium:** Delayed responses
- **High:** Responses take longer than typical

**CHAOSS Alignment:** ✅ [Issue Response Time](https://chaoss.community/kb/metric-issue-response-time/), [Time to First Response](https://chaoss.community/kb/metric-time-to-first-response/)

**Use Case:** Evaluate maintainer engagement and project support quality.

---

### Change Request Resolution

**Purpose:** Measures the speed at which pull requests are merged.

**Data Source:** GitHub Pull Requests API (creation date, merge date)

**Calculation:**

- Analyzes time from PR creation to merge
- Measures across recent PRs
- Accounts for review cycles and feedback iterations

**Scoring:**

- Merge within 3 days: 10/10 (Excellent)
- 3-10 days: 7/10 (Good)
- 10-30 days: 4/10 (Moderate)
- >30 days: 0/10 (Slow)

**Special Cases:**

- Closed without merge (rejected PRs): Scored separately
- Stale PRs without activity: 0/10 (Abandoned)

**Status Levels:**

- **None:** Fast merging
- **Low:** Reasonable turnaround
- **Medium:** Slow review cycle
- **High:** Stalled PRs

**CHAOSS Alignment:** ✅ [Change Request Review Duration](https://chaoss.community/kb/metric-change-request-review-duration/)

**Use Case:** Assess developer experience and maintainer capacity.

---

### Review Health

**Purpose:** Evaluates the quality and thoroughness of code reviews.

**Data Source:** GitHub PR reviews (review comments, approval workflow)

**Calculation:**

- Counts review comments per PR
- Measures review count before merge
- Identifies patterns of thorough vs. rubber-stamp reviews

**Scoring:**

- Regular, constructive reviews (3+ comments per PR): 10/10 (Thorough)
- Adequate reviews (1-3 comments): 7/10 (Good)
- Minimal reviews (<1 comment avg): 3/10 (Light review)
- Auto-merge or no reviews: 0/10 (No quality gate)

**Status Levels:**

- **None:** Thorough review process
- **Low:** Adequate review
- **Medium:** Light review
- **High:** Insufficient review

**CHAOSS Alignment:** ✅ [Change Request Reviews](https://chaoss.community/kb/metric-change-request-reviews/), [Review Cycle Duration](https://chaoss.community/kb/metric-review-cycle-duration-within-a-change-request/)

**Use Case:** Indicates code quality standards and maintainer involvement.

---

## Quality & Maintenance Metrics

### Build Health

**Purpose:** Indicates whether automated tests and CI/CD are passing.

**Data Source:** GitHub commit status checks, Actions CI logs

**Calculation:**

- Checks latest commit CI status
- Analyzes test pass rate
- Identifies build failures

**Scoring:**

- All recent builds passing: 10/10 (Healthy)
- Most pass (>80%): 7/10 (Good)
- Some failures (50-80%): 3/10 (Concerning)
- Most fail (<50%): 0/10 (Broken)

**Status Levels:**

- **None:** CI/CD working well
- **Low:** Mostly passing builds
- **Medium:** Frequent failures
- **High:** Broken build pipeline

**CHAOSS Alignment:** ⚠️ Partial - Related to [Test Coverage](https://chaoss.community/kb/metric-test-coverage/)

**Use Case:** Assess code quality and regression prevention.

---

### Security Signals

**Purpose:** Checks for security best practices and vulnerability disclosure.

**Data Source:** GitHub Security tab (dependabot alerts, security policies)

**Calculation:**

- Detects SECURITY.md policy
- Counts open security alerts
- Checks for known vulnerabilities

**Scoring:**

- Security policy + no alerts: 10/10 (Excellent)
- Security policy present: 8/10 (Good)
- Few alerts, no policy: 4/10 (Moderate)
- Multiple unresolved alerts: 0/10 (Poor)

**Status Levels:**

- **None:** Proactive security
- **Low:** Managed vulnerabilities
- **Medium:** Some concerns
- **High:** Unaddressed vulnerabilities

**CHAOSS Alignment:** ⚠️ Partial - Related to [OpenSSF Best Practices Badge](https://chaoss.community/kb/metric-open-source-security-foundation-openssf-best-practices-badge/)

**Use Case:** Evaluate supply chain security concerns.

---

### Code of Conduct

**Purpose:** Checks whether the project has adopted a community code of conduct.

**Data Source:** GitHub repository (CODE_OF_CONDUCT.md or similar)

**Calculation:**

- Detects presence of CODE_OF_CONDUCT.md
- Validates common CoC types (Contributor Covenant, etc.)

**Scoring:**

- Has code of conduct: 10/10 (Excellent)
- No code of conduct: 2/10 (Needs attention)

**Status Levels:**

- **None:** Code of conduct present
- **Low:** Basic guidelines
- **Medium:** No formal policy
- **High/Needs support:** No conduct standards

**Use Case:** Evaluate community inclusivity and conflict resolution.

---

### License Clarity

**Purpose:** Determines if the project has a clear, recognized license.

**Data Source:** GitHub License Detection API

**Calculation:**

- Identifies recognized SPDX license
- Validates LICENSE file presence
- Checks for license clarity

**Scoring:**

- Clear, standard license (MIT, Apache-2.0, GPL, etc.): 10/10
- Non-standard but present: 5/10 (Requires review)
- No license detected: 0/10 (Ambiguous legal status)

**Status Levels:**

- **None:** Clear licensing
- **Low:** Non-standard license
- **Medium:** Unclear licensing
- **High/Needs support:** No license

**Use Case:** Assess legal compliance and reuse rights.

---

### Documentation Presence

**Purpose:** Evaluates quality and completeness of project documentation.

**Data Source:** GitHub repository files (README.md, docs/, wiki)

**Calculation:**

- Detects README.md presence and length
- Checks for additional documentation
- Evaluates documentation structure

**Scoring:**

- Comprehensive docs (README + docs/): 10/10
- Good README: 8/10
- Basic README: 5/10
- No documentation: 0/10

**Status Levels:**

- **None:** Well-documented
- **Low:** Adequate documentation
- **Medium:** Sparse documentation
- **High:** Minimal documentation

**Use Case:** Assess ease of adoption and onboarding.

---

### Stale Issue Ratio

**Purpose:** Identifies proportion of old, unanswered issues.

**Data Source:** GitHub Issues API (creation date, last activity)

**Calculation:**

- Counts issues open >90 days without response
- Calculates stale issue ratio
- Measures issue triage health

**Scoring:**

- <10% stale issues: 10/10 (Excellent triage)
- 10-25% stale: 7/10 (Good)
- 25-50% stale: 3/10 (Moderate)
- >50% stale: 0/10 (Poor triage)

**Status Levels:**

- **None:** Healthy issue management
- **Low:** Minor staleness
- **Medium:** Significant backlog
- **High:** Overwhelming stale issues

**Use Case:** Evaluate project responsiveness and issue management.

---

## Visibility & Adoption Metrics

### Project Popularity

**Purpose:** Measures adoption and visibility through GitHub stars and watchers.

**Data Source:** GitHub repository statistics (stars, watchers, forks)

**Calculation:**

- Analyzes stargazer count
- Considers watchers and forks
- Normalizes by project age

**Scoring:**

- High stars relative to age: 10/10
- Moderate popularity: 7/10
- Low visibility: 3/10
- No adoption: 0/10

**Status Levels:**

- **None:** Highly visible project
- **Low:** Good visibility
- **Medium:** Limited visibility
- **High:** Low adoption

**Use Case:** Assess community interest and potential ecosystem impact.

---

### Fork Activity

**Purpose:** Measures project reuse through downstream forks (derivatives).

**Data Source:** GitHub fork count

**Calculation:**

- Analyzes fork count relative to stars
- Identifies technical reuse
- Measures ecosystem impact

**Scoring:**

- High fork ratio (forks/stars >0.5): 10/10 (Active reuse)
- Moderate ratio (0.2-0.5): 7/10 (Good)
- Low ratio (0.1-0.2): 4/10 (Some reuse)
- Minimal ratio (<0.1): 1/10 (Little reuse)

**CHAOSS Alignment:** ✅ [Technical Fork](https://chaoss.community/kb/metric-technical-fork/)

**Use Case:** Evaluate ecosystem impact and project influence.

---

### PR Acceptance Ratio

**Purpose:** Measures proportion of merged vs. closed pull requests.

**Data Source:** GitHub Pull Requests API (merged, closed)

**Calculation:**

- Counts merged PRs
- Counts rejected/closed PRs
- Calculates acceptance ratio

**Scoring:**

- High acceptance (>70%): 10/10 (Collaborative)
- Moderate (50-70%): 7/10 (Good)
- Selective (30-50%): 4/10 (Strict)
- Low (<30%): 1/10 (Unwelcoming)

**Status Levels:**

- **None:** Highly collaborative
- **Low:** Welcoming to PRs
- **Medium:** Selective acceptance
- **High:** Difficulty in contribution

**CHAOSS Alignment:** ✅ [Change Request Acceptance Ratio](https://chaoss.community/kb/metric-change-request-acceptance-ratio/)

**Use Case:** Assess contributor-friendliness and collaboration.

---

### PR Merge Speed

**Purpose:** Measures how quickly pull requests move from creation to merge.

**Data Source:** GitHub Pull Requests API (time metrics)

**Calculation:**

- Analyzes merge time from PR creation
- Measures recent PR velocity
- Accounts for review cycles

**Scoring:**

- Quick merge (median <5 days): 10/10
- Good pace (5-15 days): 7/10
- Moderate (15-30 days): 4/10
- Slow (>30 days): 1/10

**Status Levels:**

- **None:** Fast-moving merges
- **Low:** Reasonable timeline
- **Medium:** Slower review
- **High:** Stalled PRs

**Use Case:** Assess developer experience and maintainer capacity.

---

### PR Responsiveness

**Purpose:** Measures maintainer engagement with pull requests.

**Data Source:** GitHub Pull Requests API (comment activity)

**Calculation:**

- Counts comments per PR
- Measures feedback frequency
- Identifies engagement pattern

**Scoring:**

- Active feedback (multiple comments): 10/10
- Moderate feedback (1-2 comments): 7/10
- Minimal feedback: 3/10
- No feedback/auto-merge: 0/10

**Status Levels:**

- **None:** Highly engaged reviewers
- **Low:** Good feedback
- **Medium:** Light feedback
- **High:** Unresponsive to PRs

**Use Case:** Evaluate code review engagement and quality.

---

### Organizational Diversity

**Purpose:** Measures contribution diversity across organizations.

**Data Source:** GitHub contributor email domains or affiliated organizations

**Calculation:**

- Analyzes top contributors' organizations
- Measures organizational concentration
- Identifies corporate vs. individual contributions

**Scoring:**

- Diverse orgs (top org <40% contrib): 10/10
- Moderate diversity (40-60%): 7/10
- Single-org dominated (60-80%): 4/10
- Single-org (>80%): 1/10

**CHAOSS Alignment:** ✅ [Organizational Diversity](https://chaoss.community/kb/metric-organizational-diversity/)

**Use Case:** Assess ecosystem independence and sustainability.

---

### Single Maintainer Load

**Purpose:** Identifies projects with excessive burden on single maintainer.

**Data Source:** Commit history and contributor distribution

**Calculation:**

- Calculates percentage of work by top maintainer
- Analyzes load distribution
- Identifies burnout concerns

**Scoring:**

- Well-distributed (<40% top): 10/10 (Healthy)
- Moderate load (40-60%): 7/10 (Acceptable)
- High load (60-80%): 3/10 (Needs attention)
- Concentrated (>80%): 0/10 (Burnout concern)

**Status Levels:**

- **None:** Well-distributed load
- **Low:** Reasonable distribution
- **Medium:** Elevated concentration
- **High:** Burnout concern

**Use Case:** Identify projects showing maintainer burnout signals.

---

## Scoring System

### Scale

All metrics use a **0-10 point scale** for consistency:

| Score | Meaning | Color |
| ------ | ------ | ------ |
| **9-10** | Excellent | 🟢 Green |
| **7-8** | Good | 🟢 Green |
| **4-6** | Moderate | 🟡 Yellow |
| **1-3** | Needs attention | 🟡 Yellow |
| **0** | Needs support | 🔴 Red |

### Total Score Calculation

Overall Score uses metric weights from the selected scoring profile:

**Overall Score = (Sum(metric_score x weight) / Sum(10 x weight)) x 100**

Example:

- 3 metrics analyzed
- Scores: 8, 6, 10 with weights 2, 1, 1
- Weighted score: (8x2 + 6x1 + 10x1) = 32
- Weighted max: (10x2 + 10x1 + 10x1) = 40
- Overall score: (32/40) x 100 = 80

### Metrics Models

Metrics are grouped into focused assessments:

#### 🎯 Stability Model (Stability Focus)

Evaluates maintainability and single-point-of-failure concerns:

- Contributor Redundancy (40%)
- Change Request Resolution (33%)
- Community Health (13%)
- Security Signals (13%)

**Use:** Assess project stability for core infrastructure

#### 💰 Sustainability Model (Viability Focus)

Evaluates long-term project viability:

- Funding Signals (33%)
- Commit Author Continuity (33%)
- Release Rhythm (33%)

**Use:** Assess long-term sustainability concerns

#### 👥 Community Engagement Model (Growth Focus)

Evaluates community health and contributor experience:

- Contributor Attraction (30%)
- Contributor Retention (30%)
- Review Health (25%)
- Community Health (15%)

**Use:** Assess community health and onboarding

---

## Status Levels

### Status Level Definitions

Each metric assigns a **status level** reflecting areas of concern:

| Status Level | Meaning | Score Range | Action |
| -------- | -------- | -------- | -------- |
| **None** | Excellent health | 9-10 | ✅ No action needed |
| **Low** | Good status | 7-8 | ✅ Monitor occasionally |
| **Medium** | Monitor | 4-6 | 📋 Monitor and plan improvements |
| **High** | Needs attention | 1-3 | 🔴 Address in next quarter |
| **Needs support** | Support needed | 0 | 🚨 Immediate support recommended |

### Interpreting Status Levels

**For Individual Contributors:**

- **High/Needs support:** Consider if project is suitable for production use
- **Medium:** Monitor before major dependency
- **Low/None:** Generally safe to depend on

**For Maintainers:**

- **High/Needs support:** Target for improvement efforts
- **Medium:** Include in roadmap improvements
- **Low/None:** Maintain current practices

---

## Using These Metrics

### Best Practices

1. **Context Matters:** Metrics provide signals, not absolute judgments
2. **Project Stage:** New projects have different patterns than mature ones
3. **Community vs. Corporate:** Different sustainability models apply
4. **Multiple Metrics:** Always review several metrics before making decisions

### Example: Evaluating a Dependency

```bash
# Check comprehensive metrics for a package
oss-guard check numpy --show-models

# Result: Score 82/100
# - Stability Model: 85/100 (Stable, diverse contributors)
# - Sustainability: 75/100 (Active releases, corporate backing)
# - Community: 88/100 (Quick responses, active PRs)
```

**Interpretation:**

- ✅ Good choice for core dependency
- 📋 Note: Sustainability score indicates maintain awareness of releases
- 👥 Strong community support

---

## Resources

- [Custom Metrics Guide](CUSTOM_METRICS_GUIDE.md) - Create your own metrics
- [CHAOSS Metrics Alignment](CHAOSS_METRICS_ALIGNMENT_VALIDATION.md) - Industry standards
- [Scoring Profiles Guide](SCORING_PROFILES_GUIDE.md) - Custom scoring weights
- [GitHub API Reference](https://docs.github.com/en/graphql) - Data sources

## Feedback

Questions or suggestions about these metrics?

- **Issues:** [GitHub Issues](https://github.com/onukura/oss-sustain-guard/issues)
- **Discussions:** [GitHub Discussions](https://github.com/onukura/oss-sustain-guard/discussions)
- **Contributing:** See [CONTRIBUTING.md](https://github.com/onukura/oss-sustain-guard/blob/main/CONTRIBUTING.md)
