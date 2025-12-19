# Community Contribution Guide

> **Help build the most comprehensive open-source sustainability database!** 🌱

Share your package analysis results with the community and help expand coverage for everyone.

## 🎯 Why Contribute?

When you analyze packages locally, you're creating valuable data that can benefit the entire community:

- **Expand Coverage**: Help analyze packages not yet in the official database
- **Faster Updates**: Share recent analysis for popular packages
- **Support Community**: Give back to the open-source ecosystem
- **Recognition**: Get attributed for your contributions

## ✨ How It Works

```
You Analyze → Export Results → Submit PR → Review & Merge → Everyone Benefits
```

### Simple 3-Step Process

1. **Analyze** packages you care about (requires your own `GITHUB_TOKEN`)
2. **Export** results in a standardized format (automatic sanitization)
3. **Submit** via GitHub Pull Request (we handle the rest!)

## 🚀 Quick Start

### Prerequisites

- OSS Sustain Guard installed (`pip install oss-sustain-guard`)
- GitHub account (for submitting contributions)
- GitHub Personal Access Token (for analysis)

### Step 1: Set Up Your Token

```bash
# Create a GitHub token: https://github.com/settings/tokens
# Required scopes: public_repo (read-only)

# Set environment variable
export GITHUB_TOKEN=ghp_your_token_here

# Or save in .env file
echo "GITHUB_TOKEN=ghp_your_token_here" > .env
```

### Step 2: Analyze Packages

```bash
# Analyze packages you're interested in
oss-guard check requests flask django numpy

# The results are automatically saved to your local cache
# Location: ~/.cache/oss-sustain-guard/
```

### Step 3: Export Your Results

```bash
# Export all Python packages from your cache
oss-guard export python

# This creates: contribution-python-20251219-210000.json
```

### Step 4: Submit Contribution

```bash
# 1. Fork the repository on GitHub
# Visit: https://github.com/onukura/oss-sustain-guard
# Click "Fork" button

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/oss-sustain-guard.git
cd oss-sustain-guard

# 3. Create a contribution branch
git checkout -b contrib/python-packages

# 4. Copy your contribution file
cp ~/contribution-python-*.json data/contributions/

# 5. Commit your contribution
git add data/contributions/
git commit -m "contrib: add Python package analysis"

# 6. Push to your fork
git push origin contrib/python-packages

# 7. Create Pull Request on GitHub
# Visit your fork and click "Create Pull Request"
```

## 📝 Export Command Reference

### Basic Usage

```bash
# Export specific ecosystem
oss-guard export python
oss-guard export javascript
oss-guard export rust

# Export with custom output location
oss-guard export python --output my-contribution.json

# Export with contributor name
oss-guard export python --contributor myGitHubUsername
```

### Export Options

| Option | Description | Example |
|--------|-------------|---------|
| `ecosystem` | Target ecosystem to export | `python`, `javascript`, `rust`, `go`, etc. |
| `--output` | Custom output file path | `--output ~/my-contrib.json` |
| `--contributor` | Your GitHub username | `--contributor octocat` |
| `--exclude` | Exclude specific packages | `--exclude internal-pkg` |

### What Gets Exported?

✅ **Included:**
- Package names and GitHub URLs
- Sustainability metrics and scores
- Analysis metadata (timestamp, tool version)
- Cache metadata (when analyzed)

❌ **Automatically Removed (Sanitization):**
- Personal information
- API tokens or credentials
- Local file paths
- System-specific data

## 🔍 Contribution File Structure

Your export creates a JSON file like this:

```json
{
  "_contribution_metadata": {
    "schema_version": "2.0",
    "contributor": "your-github-username",
    "contribution_date": "2025-12-19T21:00:00Z",
    "tool_version": "0.7.0",
    "ecosystem": "python",
    "package_count": 5
  },
  "packages": {
    "python:requests": {
      "ecosystem": "python",
      "package_name": "requests",
      "github_url": "https://github.com/psf/requests",
      "metrics": [...],
      "models": [...],
      "signals": {...}
    }
  }
}
```

## ✅ Validation & Review Process

### Automated Validation

When you submit a PR, our CI automatically checks:

- ✓ Schema compliance
- ✓ Valid package names
- ✓ GitHub repository URLs exist
- ✓ No malicious content
- ✓ Data sanitization complete

### Maintainer Review

A maintainer will:

- Review contribution volume and source
- Spot-check metrics for reasonableness
- Approve and merge your contribution

### Timeline

- **Automated checks**: ~5 minutes
- **Maintainer review**: Usually within 7 days
- **Integration**: Next weekly database update

## 📊 Contribution Examples

### Example 1: New Packages

You've analyzed some niche packages not yet in the database:

```bash
# Analyze new packages
oss-guard check my-favorite-lib another-cool-package

# Export results
oss-guard export python --contributor yourname

# Submit PR with title: "contrib: add Python packages - my-favorite-lib, another-cool-package"
```

### Example 2: Updated Analysis

Official data is outdated, you have fresh analysis:

```bash
# Analyze packages with recent activity
oss-guard check requests --no-cache

# Export fresh results
oss-guard export python

# Submit PR with title: "contrib: update Python packages - fresh metrics"
```

### Example 3: Multiple Ecosystems

You work with multiple languages:

```bash
# Analyze Python packages
oss-guard check requests flask

# Analyze JavaScript packages
oss-guard check npm:react npm:vue

# Export both
oss-guard export python
oss-guard export javascript

# Submit PR with both files
```

## 🛡️ Security & Privacy

### Your Privacy is Protected

We automatically sanitize all contributions to remove:

- Personal identification information
- API tokens or credentials
- Local file paths
- System-specific information

### You Control What You Share

- Choose which ecosystems to export
- Exclude specific packages if needed
- Review the export file before submitting
- Delete contributions anytime (Git history)

### Safe Submission

- Contributions are public (GitHub PR)
- Your GitHub username is attributed
- All changes are reversible
- No private data is collected

## ❓ FAQ

### Q: Do I need a GitHub token to export?

**A:** No! You need a token to **analyze** packages (fetch GitHub data), but **exporting** doesn't require any tokens. The export command just packages your local cache data.

### Q: Will my personal information be shared?

**A:** No. All exports are automatically sanitized to remove personal information, API tokens, and local file paths. Only the package analysis data is included.

### Q: What if I analyze proprietary/private packages?

**A:** Don't export those! Only export results for public packages you want to share. You can use `--exclude` to skip specific packages.

### Q: How do I exclude certain packages?

**A:** Either:
1. Use `--exclude` flag: `oss-guard export python --exclude internal-pkg`
2. Configure in `.oss-sustain-guard.toml`:
   ```toml
   [tool.oss-sustain-guard]
   exclude = ["internal-pkg", "proprietary-lib"]
   ```

### Q: Can I contribute anonymously?

**A:** Not completely. Your GitHub username will be associated with the PR. However, you can use a separate GitHub account if you prefer pseudonymity.

### Q: What if my contribution is rejected?

**A:** Contributions might be rejected if:
- Validation checks fail (bad data format)
- Data appears malicious or suspicious
- Duplicates existing recent data

You'll receive feedback in the PR comments explaining the issue.

### Q: How often are contributions integrated?

**A:** Approved contributions are merged to `main` immediately, but integrated into the official database during weekly update jobs (typically once per week).

### Q: Can I contribute to multiple ecosystems at once?

**A:** Yes! You can create multiple export files and include them all in a single PR. Just export each ecosystem separately:
```bash
oss-guard export python
oss-guard export javascript
oss-guard export rust
# Include all files in your PR
```

### Q: What if I made a mistake in my contribution?

**A:** You can:
1. Update your PR with corrections before it's merged
2. Submit a follow-up PR to fix mistakes after merge
3. Comment on the PR to request changes

### Q: Will my contributions be attributed?

**A:** Yes! Your GitHub username and contribution timestamp are included in the contribution metadata. You'll be recognized for helping the community.

## 🎓 Best Practices

### Do's ✅

- **Analyze packages you use**: Share data for packages you actually work with
- **Fresh analysis**: Use `--no-cache` to get recent data
- **Clear PR descriptions**: Explain what packages you're contributing
- **Check validation**: Ensure your export file passes validation locally
- **Small batches**: Submit 10-50 packages per PR (easier to review)

### Don'ts ❌

- **Don't export private packages**: Only share public package data
- **Don't submit stale data**: Use recent analysis (< 7 days old)
- **Don't spam**: Avoid submitting hundreds of packages at once
- **Don't include credentials**: Export automatically removes them, but double-check
- **Don't game metrics**: Submit honest analysis results only

## 📚 Additional Resources

- [Architecture Documentation](./COMMUNITY_CONTRIBUTION_ARCHITECTURE.md) - Technical details
- [Database Schema](./DATABASE_SCHEMA.md) - Data format specification
- [FAQ](./TROUBLESHOOTING_FAQ.md) - Common questions and troubleshooting
- [Contributing Guidelines](../CONTRIBUTING.md) - General contribution info

## 🤝 Community Guidelines

### Our Philosophy

OSS Sustain Guard is designed to spark thoughtful conversations about open-source sustainability, not to pass judgment. When contributing:

- 📊 **Be honest**: Share accurate analysis results
- 🤝 **Be respectful**: Recognize that every project has unique circumstances
- 🌱 **Be supportive**: Help the community, don't criticize
- 💝 **Be thankful**: Appreciate maintainers and contributors

### Getting Help

Need help contributing? Reach out:

- **GitHub Issues**: [Ask a question](https://github.com/onukura/oss-sustain-guard/issues/new)
- **GitHub Discussions**: [Join the community](https://github.com/onukura/oss-sustain-guard/discussions)
- **Email**: Check the repository for contact information

## 🎉 Recognition

Top contributors will be featured in:

- Project README
- Release notes
- Community highlights

Thank you for helping make OSS Sustain Guard better for everyone! 🌟

---

**Version**: 1.0  
**Last Updated**: 2025-12-19  
**Questions?** Open an issue on GitHub!
