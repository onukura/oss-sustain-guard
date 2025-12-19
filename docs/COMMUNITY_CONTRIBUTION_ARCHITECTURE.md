# Community Contribution Architecture

## Overview

OSS Sustain Guard now supports **community-driven data contributions**, allowing users to share their analysis results with the broader community. This architecture enables a decentralized, secure model for expanding coverage while maintaining data quality.

## 🎯 Goals

1. **Enable Community Contributions** - Allow users who analyze packages locally to share results
2. **Maintain Data Quality** - Validate all contributions for security and correctness
3. **Secure & Trustworthy** - Implement validation and sanitization to prevent malicious data
4. **Token-less for Contributors** - Users don't need GitHub API tokens to export their results
5. **Transparent Process** - Clear contribution workflow with visibility into what's being shared

## 🏗️ Architecture

### Three-Layer Model

```
┌─────────────────────────────────────────────────────────────┐
│                    1. User Analysis Phase                    │
│  ┌────────────┐         ┌─────────────┐                     │
│  │ User runs  │────────▶│ Analysis    │                     │
│  │ oss-guard  │         │ (with token)│                     │
│  └────────────┘         └─────────────┘                     │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                  2. Export & Contribution Phase              │
│  ┌────────────┐         ┌─────────────┐                     │
│  │ oss-guard  │────────▶│ Sanitized   │────┐                │
│  │ export     │         │ JSON Export │    │                │
│  └────────────┘         └─────────────┘    │                │
│                                             │                │
│                         ┌─────────────┐    │                │
│                         │ GitHub PR   │◀───┘                │
│                         │ (Manual)    │                      │
│                         └─────────────┘                      │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   3. Validation & Merge Phase                │
│  ┌────────────┐         ┌─────────────┐                     │
│  │ Automated  │────────▶│ Schema &    │                     │
│  │ CI Check   │         │ Security    │                     │
│  └────────────┘         │ Validation  │                     │
│                         └─────────────┘                     │
│                                │                             │
│                         ┌─────────────┐                     │
│                         │ Maintainer  │                     │
│                         │ Review      │                     │
│                         └─────────────┘                     │
│                                │                             │
│                         ┌─────────────┐                     │
│                         │ Merge to    │                     │
│                         │ main branch │                     │
│                         └─────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User Analysis**
   - User analyzes packages locally with their own `GITHUB_TOKEN`
   - Results stored in local cache (`~/.cache/oss-sustain-guard/`)
   - User decides which results to share

2. **Export**
   - User runs `oss-guard export <ecosystem>` to create contribution file
   - System sanitizes data (removes personal info, validates schema)
   - Generates `contribution-<ecosystem>-<timestamp>.json`

3. **Contribution Submission**
   - User creates PR to `onukura/oss-sustain-guard` repository
   - Includes exported contribution file in `data/contributions/` directory
   - Fills out contribution template with context

4. **Validation**
   - Automated CI runs validation checks:
     - Schema compliance
     - Data sanitization verification
     - No malicious content
     - Package/repository existence verification
   - Human maintainer review for final approval

5. **Merge & Integration**
   - Maintainer merges approved contributions
   - Weekly job integrates contributions into main database
   - Updated database published for all users

## 🔒 Security Model

### Data Sanitization

All exported data is automatically sanitized to remove:

- Personal identification information
- API tokens or credentials
- Local file paths
- System-specific information

### Validation Layers

1. **Export-time Validation** (User's machine)
   - Schema compliance
   - Required fields present
   - Data type correctness

2. **CI Validation** (Automated)
   - Schema version compatibility
   - Package name format validation
   - GitHub repository URL verification
   - No XSS/injection vectors in text fields
   - Reasonable value ranges for scores and metrics

3. **Maintainer Review** (Human)
   - Spot-check metrics for reasonableness
   - Review contribution volume and source
   - Flag suspicious patterns

### Trust Model

- **Open Contributions**: Anyone can submit (GitHub account required for PR)
- **Validation Required**: All contributions must pass automated checks
- **Maintainer Approval**: Final human review before merge
- **Attribution**: Contributions include contributor metadata (GitHub username, timestamp)
- **Reversibility**: Bad data can be rolled back via Git history

## 📦 Contribution File Format

### Structure

```json
{
  "_contribution_metadata": {
    "schema_version": "2.0",
    "contributor": "github_username",
    "contribution_date": "2025-12-19T21:00:00Z",
    "tool_version": "0.7.0",
    "ecosystem": "python",
    "package_count": 5,
    "analysis_method": "github_graphql"
  },
  "packages": {
    "python:requests": {
      "ecosystem": "python",
      "package_name": "requests",
      "github_url": "https://github.com/psf/requests",
      "metrics": [...],
      "models": [...],
      "signals": {...},
      "cache_metadata": {
        "fetched_at": "2025-12-19T20:00:00Z",
        "ttl_seconds": 604800,
        "source": "user_analysis"
      }
    }
  }
}
```

### Key Fields

- `_contribution_metadata`: Contribution tracking information
  - `contributor`: GitHub username (automatically added)
  - `contribution_date`: ISO 8601 timestamp
  - `tool_version`: Version of oss-sustain-guard used
  - `ecosystem`: Target ecosystem for this contribution
  - `package_count`: Number of packages included
  - `analysis_method`: How the analysis was performed

- `packages`: Dictionary of package analysis results
  - Key format: `{ecosystem}:{package_name}`
  - Each entry contains full analysis result (metrics, models, signals)
  - `cache_metadata.source` set to "user_analysis" to distinguish from official builds

## 🔄 Integration Workflow

### Weekly Integration Job

1. **Collect Contributions**
   - Scan `data/contributions/` directory
   - Group by ecosystem

2. **Validate & Merge**
   - Re-validate all contribution files
   - Merge into existing ecosystem databases
   - Prefer official data over user contributions (official data has priority)
   - Update package entries if user contribution is newer

3. **Generate Updated Database**
   - Save to `data/latest/{ecosystem}.json.gz`
   - Archive previous version to `data/archive/{date}/`
   - Commit and push changes

4. **Cleanup**
   - Move processed contributions to `data/contributions/processed/`
   - Keep for historical reference

## 🚀 User Workflow

### Step 1: Analyze Packages Locally

```bash
# User has GITHUB_TOKEN set in environment
export GITHUB_TOKEN=ghp_your_token_here

# Analyze packages they care about
oss-guard check my-favorite-package another-package
```

### Step 2: Export Results

```bash
# Export all Python packages from local cache
oss-guard export python

# Export specific ecosystem with custom output
oss-guard export javascript --output my-contributions.json

# Export with automatic contributor info
oss-guard export rust --contributor myGitHubUsername
```

### Step 3: Submit Contribution

```bash
# 1. Fork the repository on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/oss-sustain-guard.git
cd oss-sustain-guard

# 3. Create a branch
git checkout -b contrib/my-packages

# 4. Copy your contribution file
cp ~/contribution-python-*.json data/contributions/

# 5. Commit and push
git add data/contributions/
git commit -m "contrib: add analysis for Python packages"
git push origin contrib/my-packages

# 6. Create Pull Request on GitHub
```

## 📊 Benefits

### For Contributors

- **Share Knowledge**: Help the community by sharing analysis results
- **Privacy Protected**: Automatic sanitization of personal data
- **Recognition**: GitHub attribution for contributions
- **Low Barrier**: No complex setup or API keys needed for export

### For Users

- **Broader Coverage**: Access to more package analyses
- **Faster Updates**: Community can analyze new packages before official builds
- **Diverse Data**: Multiple perspectives on package health
- **Transparency**: See who contributed and when

### For Maintainers

- **Reduced Load**: Community helps expand database coverage
- **Quality Control**: Validation ensures data integrity
- **Audit Trail**: Git history tracks all contributions
- **Scalable**: Handles growth without infrastructure costs

## ⚠️ Limitations & Considerations

### Current Limitations

1. **Manual Process**: Contributions require GitHub PR (not automated submission)
2. **Review Latency**: Human review needed before merge (not instant)
3. **Duplicate Analysis**: Multiple users might analyze same packages
4. **Priority System**: Official builds take precedence over user contributions

### Future Enhancements

1. **Automated API Submission**: Direct contribution submission via API
2. **Contribution Ranking**: Trust score based on contributor history
3. **Real-time Sync**: Faster integration of high-quality contributions
4. **Community Badges**: Recognition for top contributors

## 🔐 Privacy & Ethics

### What We Collect

- GitHub username (from PR)
- Timestamp of contribution
- Tool version used
- Package analysis data (sanitized)

### What We DON'T Collect

- Personal information
- API tokens or credentials
- Local file paths
- IP addresses or system info

### User Control

- Users choose what to export
- Can exclude specific packages
- Can review export file before submitting
- Can delete contributions at any time

## 📚 Related Documentation

- [COMMUNITY_CONTRIBUTION_GUIDE.md](./COMMUNITY_CONTRIBUTION_GUIDE.md) - User guide for contributing
- [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - Database format specification
- [CONTRIBUTING.md](../CONTRIBUTING.md) - General contribution guidelines

## 🤝 Community First

This architecture embodies OSS Sustain Guard's philosophy:

- 🌱 **Sustainability matters** - Community contributions help sustain the project
- 🤝 **Community support is essential** - Everyone can contribute
- 📊 **Transparency helps everyone** - Open process, visible contributions
- 🎯 **Respectful evaluation** - Validation ensures quality, not judgment
- 💝 **Supporting maintainers** - Reduces maintenance burden

---

**Version**: 1.0  
**Last Updated**: 2025-12-19  
**Status**: Proposed Architecture
