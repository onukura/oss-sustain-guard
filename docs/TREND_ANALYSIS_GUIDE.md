# Time Series Analysis & Trend Tracking Guide

OSS Sustain Guard provides powerful time series analysis capabilities to help you track how package health metrics evolve over time. This guide covers trend analysis, historical comparisons, and automated reporting features.

## 📊 Overview

The time series analysis feature enables you to:

- **Track health score trends** over time
- **Compare snapshots** from different dates
- **Identify improvement/degradation patterns**
- **Generate detailed comparison reports**
- **Monitor specific metrics** across historical data

## 🎯 Use Cases

### 1. Monitor Package Health Evolution

Track how your dependencies improve or degrade over time:

```bash
# View trend for a specific package
oss-sustain-guard trend Flask

# Focus on a specific ecosystem
oss-sustain-guard trend express --ecosystem javascript
```

### 2. Compare Before/After Changes

Compare package health between specific dates:

```bash
# Compare two snapshots
oss-sustain-guard compare requests 2025-12-11 2025-12-12

# Compare across different ecosystems
oss-sustain-guard compare lodash 2025-11-01 2025-12-01 --ecosystem javascript
```

### 3. Track Metric-Specific Trends

Focus on specific health metrics:

```bash
# Monitor bus factor trend
oss-sustain-guard trend Flask --metric "Contributor Redundancy"

# Track maintenance activity
oss-sustain-guard trend Django --metric "Recent Activity"
```

## 📅 Available Commands

### `list-snapshots`

List all available historical snapshot dates:

```bash
oss-sustain-guard list-snapshots
```

**Output:**

```shell
📅 Available Snapshot Dates

   Available Snapshots
┏━━━┳━━━━━━━━━━━━┳━━━━━━━┓
┃ # ┃ Date       ┃ Files ┃
┡━━━╇━━━━━━━━━━━━╇━━━━━━━┩
│ 1 │ 2025-12-11 │     2 │
│ 2 │ 2025-12-12 │     2 │
│ 3 │ 2025-12-13 │     2 │
└───┴────────────┴───────┘

Total snapshots: 3
Date range: 2025-12-11 to 2025-12-13
```

**Options:**

- `--archive-dir PATH` - Custom archive directory path (default: `data/archive`)

---

### `trend`

Display comprehensive trend analysis for a package:

```bash
oss-sustain-guard trend <PACKAGE_NAME> [OPTIONS]
```

**Arguments:**

- `PACKAGE_NAME` - Name of the package to analyze

**Options:**

- `--ecosystem, -e TEXT` - Package ecosystem (default: `python`)
  - Supported: `python`, `javascript`, `rust`, `java`, `kotlin`, `php`, `ruby`, `csharp`, `go`
- `--metric, -m TEXT` - Focus on specific metric (optional)
- `--archive-dir PATH` - Custom archive directory path
- `--include-latest` - Include real-time analysis if package not in archive (requires `GITHUB_TOKEN`)

**Examples:**

```bash
# Basic trend analysis
oss-sustain-guard trend requests

# JavaScript package
oss-sustain-guard trend react --ecosystem javascript

# Focus on specific metric
oss-sustain-guard trend Flask --metric "Bus Factor"

# Real-time analysis for packages not in archive (requires GITHUB_TOKEN)
oss-sustain-guard trend new-package --include-latest
```

**Behavior when package is not in archive:**

- **Without `--include-latest`**: Shows "No historical data found" message with helpful tip
- **With `--include-latest`**: Attempts real-time GitHub API analysis
  - Resolves package name to GitHub repository
  - Fetches current health metrics
  - Displays single snapshot (no historical comparison)
  - Requires `GITHUB_TOKEN` environment variable
  - Subject to GitHub API rate limits

**Output includes:**

1. **Summary Table**
   - GitHub repository URL
   - First and latest snapshot dates
   - Score progression (first, latest, average)
   - Overall trend indicator (improving 📈, stable ➡️, degrading 📉)

2. **Score History Timeline**
   - Date-by-date score progression
   - Change from previous snapshot
   - Visual status indicators

3. **Metric-Specific Details** (when using `--metric`)
   - Score evolution for specific metric
   - Risk level changes
   - Contextual notes

---

### `compare`

Generate detailed comparison report between two dates:

```bash
oss-sustain-guard compare <PACKAGE_NAME> <DATE1> <DATE2> [OPTIONS]
```

**Arguments:**

- `PACKAGE_NAME` - Name of the package to compare
- `DATE1` - Earlier date in YYYY-MM-DD format
- `DATE2` - Later date in YYYY-MM-DD format

**Options:**

- `--ecosystem, -e TEXT` - Package ecosystem (default: `python`)
- `--archive-dir PATH` - Custom archive directory path

**Examples:**

```bash
# Compare two dates
oss-sustain-guard compare requests 2025-12-11 2025-12-12

# Compare JavaScript package
oss-sustain-guard compare lodash 2025-11-01 2025-12-01 --ecosystem javascript
```

**Output includes:**

- **Overall score change** with trend indicator
- **Per-metric comparison** showing:
  - Score on both dates
  - Score delta
  - Visual change indicator
- **New/removed metrics** detection

---

## 📈 Understanding Trend Indicators

### Trend Classification

Trends are automatically classified based on score change:

| Trend | Score Change | Indicator | Meaning |
|-------|-------------|-----------|---------|
| **Improving** | > +5 | 📈 | Health score is significantly improving |
| **Stable** | -5 to +5 | ➡️ | Health score is relatively stable |
| **Degrading** | < -5 | 📉 | Health score is declining |

### Visual Status Indicators

In timeline views:

| Indicator | Meaning |
|-----------|---------|
| 🟢 | First data point (baseline) |
| 📈 | Score increased from previous |
| ➡️ | Score unchanged from previous |
| 📉 | Score decreased from previous |

### Score Colors

Scores are color-coded for quick assessment:

- **Green (≥80)**: Healthy status
- **Yellow (50-79)**: Monitor status
- **Red (<50)**: Needs attention

---

## 🗂️ Data Organization

### Archive Structure

Historical data is stored in dated snapshots:

```shell
data/
  archive/
    2025-12-11/
      python.json
      javascript.json
      rust.json
      ...
    2025-12-12/
      python.json
      javascript.json
      rust.json
      ...
```

### Snapshot Generation

Snapshots are automatically created by the build process:

1. **Automated builds** generate snapshots daily/weekly
2. Each snapshot contains **complete package data** for all ecosystems
3. Data includes:
   - Total health score
   - Individual metric scores
   - Risk assessments
   - Funding information
   - Repository metadata

---

## 💡 Best Practices

### 1. Regular Monitoring

Set up periodic trend checks for critical dependencies:

```bash
# Create a monitoring script
cat > monitor_deps.sh << 'EOF'
#!/bin/bash

PACKAGES="requests Flask Django pytest"

for pkg in $PACKAGES; do
    echo "Checking trend for $pkg..."
    oss-sustain-guard trend "$pkg"
    echo ""
done
EOF

chmod +x monitor_deps.sh
./monitor_deps.sh
```

### 2. Automated Comparisons

Compare monthly snapshots to track long-term trends:

```bash
# Compare month-over-month
oss-sustain-guard compare Flask 2025-11-01 2025-12-01
```

### 3. Metric-Specific Focus

Monitor specific areas of concern:

```bash
# Track maintainer retention
oss-sustain-guard trend mypackage --metric "Maintainer Retention"

# Monitor contributor diversity
oss-sustain-guard trend mypackage --metric "Contributor Redundancy"
```

### 4. Cross-Ecosystem Analysis

Compare trends across different ecosystems:

```bash
# Python
oss-sustain-guard trend requests

# JavaScript equivalent
oss-sustain-guard trend axios --ecosystem javascript
```

---

## 🔍 Advanced Usage

### Custom Archive Locations

Use custom archive directories:

```bash
# Use CI/CD archive
oss-sustain-guard trend Flask --archive-dir /path/to/custom/archive

# List custom archive snapshots
oss-sustain-guard list-snapshots --archive-dir /path/to/archive
```

### Scripting & Automation

Integrate trend analysis into CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Check Dependency Trends
  run: |
    oss-sustain-guard list-snapshots
    oss-sustain-guard trend requests
    oss-sustain-guard compare Flask ${{ env.PREVIOUS_DATE }} ${{ env.CURRENT_DATE }}
```

### Data Export

Combine with other tools for advanced analysis:

```bash
# Export trend data
oss-sustain-guard trend Flask > flask_trend.txt

# Automated comparison
PREV_DATE=$(date -d "7 days ago" +%Y-%m-%d)
CURR_DATE=$(date +%Y-%m-%d)
oss-sustain-guard compare Flask "$PREV_DATE" "$CURR_DATE"
```

---

## 📊 Example Workflows

### Workflow 1: Weekly Dependency Review

```bash
#!/bin/bash
# weekly_review.sh

echo "📊 Weekly Dependency Health Review"
echo "==================================="
echo ""

# List available snapshots
echo "Available Snapshots:"
oss-sustain-guard list-snapshots
echo ""

# Get dates for comparison (last week vs this week)
LAST_WEEK=$(date -d "7 days ago" +%Y-%m-%d)
THIS_WEEK=$(date +%Y-%m-%d)

# Check critical dependencies
CRITICAL_DEPS="requests Flask Django celery"

for dep in $CRITICAL_DEPS; do
    echo "Analyzing $dep..."
    oss-sustain-guard trend "$dep"
    echo ""
done
```

### Workflow 2: Pre-Upgrade Assessment

```bash
#!/bin/bash
# pre_upgrade_check.sh

PACKAGE=$1
OLD_DATE=$2
NEW_DATE=$3

echo "📊 Pre-Upgrade Assessment for $PACKAGE"
echo "======================================"
echo ""

# Show overall trend
oss-sustain-guard trend "$PACKAGE"
echo ""

# Detailed comparison
oss-sustain-guard compare "$PACKAGE" "$OLD_DATE" "$NEW_DATE"
echo ""

# Check specific metrics
for metric in "Contributor Redundancy" "Maintainer Retention" "Recent Activity"; do
    echo "Checking: $metric"
    oss-sustain-guard trend "$PACKAGE" --metric "$metric"
    echo ""
done
```

### Workflow 3: Multi-Ecosystem Monitoring

```bash
#!/bin/bash
# multi_ecosystem_monitor.sh

declare -A PACKAGES=(
    ["python"]="requests Flask"
    ["javascript"]="express react"
    ["rust"]="serde tokio"
)

for ecosystem in "${!PACKAGES[@]}"; do
    echo "📦 $ecosystem Packages"
    echo "===================="

    for pkg in ${PACKAGES[$ecosystem]}; do
        echo "Trend for $pkg:"
        oss-sustain-guard trend "$pkg" --ecosystem "$ecosystem"
        echo ""
    done
done
```

---

## 🎯 Interpreting Results

### Positive Trends 📈

When you see improving trends:

- ✅ **Maintainer engagement is increasing**
- ✅ **Contributor diversity is growing**
- ✅ **Response times are improving**
- ✅ **Release cadence is healthy**

**Action**: Continue monitoring, consider increased adoption

### Stable Trends ➡️

When trends are stable:

- ℹ️ **Consistent maintenance patterns**
- ℹ️ **Predictable release schedule**
- ℹ️ **Steady contributor base**

**Action**: Monitor for changes, maintain current usage

### Degrading Trends 📉

When you see declining trends:

- ⚠️ **Reduced maintainer activity**
- ⚠️ **Increasing bus factor risk**
- ⚠️ **Slower response times**
- ⚠️ **Funding challenges**

**Action**:

1. Investigate root causes
2. Consider alternatives
3. Support the project (funding, contributions)
4. Plan migration if critical

---

## 🔗 Related Features

- **[Recursive Scanning](RECURSIVE_SCANNING_GUIDE.md)** - Analyze entire project dependencies
- **[Exclude Packages](EXCLUDE_PACKAGES_GUIDE.md)** - Filter packages from analysis
- **[Scoring Profiles](SCORING_PROFILES_GUIDE.md)** - Customize metric weights
- **[GitHub Actions](GITHUB_ACTIONS_GUIDE.md)** - Automate trend analysis in CI/CD

---

## ❓ FAQ

### Q: How often are snapshots created?

A: Snapshots are created automatically by the build process. Check your CI/CD configuration or archive directory to see the frequency.

### Q: Can I create custom snapshots?

A: Yes! Run the database builder manually:

```bash
cd builder
python build_db.py
```

This creates a new snapshot in `data/archive/YYYY-MM-DD/`.

### Q: What if a package doesn't exist in older snapshots?

A: The trend analysis will only show data from snapshots where the package exists. The report will indicate the first available date.

### Q: Can I compare non-adjacent dates?

A: Yes! You can compare any two dates in the archive:

```bash
oss-sustain-guard compare Flask 2025-01-01 2025-12-01
```

### Q: How is the overall trend calculated?

A: Trends are based on total score change:

- **Improving**: Final score > Initial score + 5
- **Degrading**: Final score < Initial score - 5
- **Stable**: Change within ±5 points

### Q: What if a package is not in the archive?

A: You have two options:

1. **Wait for next snapshot** - The package will appear in future archives once analyzed
2. **Use `--include-latest` flag** - Perform real-time analysis:

   ```bash
   oss-sustain-guard trend mypackage --include-latest
   ```

   **Requirements**:
   - `GITHUB_TOKEN` environment variable must be set
   - Package must have a GitHub repository
   - Subject to GitHub API rate limits

   **Note**: Real-time analysis provides a single snapshot only. Historical comparison requires archived data.

---

## 🛠️ Troubleshooting

### Issue: "No historical data found"

**Cause**: Package may not exist in archive snapshots

**Solution**:

1. Check available dates: `oss-sustain-guard list-snapshots`
2. Verify package name and ecosystem
3. Use `--include-latest` flag for real-time analysis:

   ```bash
   oss-sustain-guard trend mypackage --include-latest
   ```

4. Ensure `GITHUB_TOKEN` is set if using real-time analysis
5. Ensure archive directory contains data

### Issue: "GITHUB_TOKEN environment variable is required"

**Cause**: Real-time analysis requires GitHub API access

**Solution**: Set your GitHub personal access token:

```bash
export GITHUB_TOKEN="your_token_here"
```

Get a token at: <https://github.com/settings/tokens>

### Issue: "Could not resolve package to GitHub repository"

**Cause**: Package doesn't have GitHub repository metadata or doesn't exist

**Solution**:

1. Verify package exists in the ecosystem registry (PyPI, npm, etc.)
2. Check if package has GitHub repository link in its metadata
3. Some packages may use non-GitHub hosting (GitLab, Bitbucket) - not currently supported for real-time analysis

### Issue: "Date not found in archive"

**Cause**: Specified date doesn't exist in snapshots

**Solution**: Use `list-snapshots` to see available dates

### Issue: Empty trend results

**Cause**: Package recently added, no historical data

**Solution**: Wait for more snapshots to be generated, or analyze newer packages separately

---

## 📝 Contributing

To improve time series analysis features:

1. **Suggest new metrics** for trend tracking
2. **Report visualization improvements**
3. **Share workflow examples** for common use cases
4. **Request export formats** (CSV, JSON, etc.)

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.

---

## 📚 Additional Resources

- **[Database Schema](DATABASE_SCHEMA.md)** - Understand data structure
- **[CLI Validation Report](local/CLI_VALIDATION_REPORT.md)** - Command reference
- **[CHAOSS Metrics](CHAOSS_METRICS_ALIGNMENT_VALIDATION.md)** - Metric definitions

---

**Remember**: Time series analysis is most valuable when used consistently over time. Regular monitoring helps you make informed decisions about dependency health and sustainability.
