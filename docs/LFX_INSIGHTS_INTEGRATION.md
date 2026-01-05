# LFX Insights Integration

OSS Sustain Guard integrates with [LFX Insights](https://insights.linuxfoundation.org/) to provide additional context about your dependencies through badges and links in HTML and JSON reports.

## Overview

This integration is designed to be:

- **Resilient**: No HTTP requests to LFX servers during analysis - only URL generation
- **Fast**: No network overhead or API rate limits
- **Simple**: No API keys or authentication required
- **Optional**: Can be easily disabled if not needed

## Features

- **Project Links**: Direct links to LFX Insights project dashboards
- **Health Badges**: Visual badges showing project health metrics
- **Multiple Badge Types**: Support for health-score, active-contributors, and more
- **Configurable**: Explicit project mapping for accurate LFX links

## Configuration

LFX Insights integration is configured in `.oss-sustain-guard.toml` or `pyproject.toml`:

```toml
[tool.oss-sustain-guard.integrations.lfx]
# Enable/disable LFX integration
enabled = true

# Badge types to display
# Available: "health-score", "active-contributors", "contributors"
badges = ["health-score", "active-contributors"]

# Explicit package to LFX project slug mapping
# This is the most reliable way to ensure correct LFX links
[tool.oss-sustain-guard.integrations.lfx.project_map]
"npm:react" = "facebook-react"
"pypi:requests" = "psf-requests"
"github:kubernetes/kubernetes" = "kubernetes-kubernetes"
```

## How It Works

### Project Slug Resolution

The integration resolves package names to LFX project slugs using the following priority:

1. **Explicit Configuration** (highest priority)
   - Use the `project_map` in your config file
   - Most reliable method
   - Example: `"npm:react" = "facebook-react"`

2. **Heuristic Inference**
   - Automatically infers from GitHub URLs
   - Pattern: `{owner}-{repo}`
   - Example: `https://github.com/facebook/react` → `facebook-react`

3. **Unable to Resolve**
   - If neither method works, LFX info is not displayed
   - Analysis continues normally

### Badge Types

Available badge types:

- **`health-score`**: Overall project health score from LFX
- **`active-contributors`**: Number of active contributors
- **`contributors`**: Total contributor count

## Usage

### Terminal Output

LFX information appears in table and detailed terminal output formats when enabled:

```bash
# Default table format
os4g check https://github.com/facebook/react

# Detailed format
os4g check https://github.com/facebook/react --output-style detail
```

Output includes:
- Direct link to the LFX Insights dashboard
- Displayed in **table** and **detailed** formats
- **Not displayed in compact format** (for CI/CD friendliness)

Example output:
```
📊 facebook/react - LFX Insights: https://insights.linuxfoundation.org/project/facebook-react
```

### HTML Reports

LFX information appears automatically in HTML reports when enabled:

```bash
os4g check https://github.com/facebook/react --output-format html
```

The HTML report will include:
- A clickable "View" link to the LFX Insights dashboard
- Badge images showing health metrics
- Automatic dark/light mode support

### JSON Output

LFX information is included in JSON output:

```bash
os4g check https://github.com/facebook/react --output-format json
```

JSON structure:

```json
{
  "results": [
    {
      "repo_url": "https://github.com/facebook/react",
      "lfx": {
        "project_slug": "facebook-react",
        "project_url": "https://insights.linuxfoundation.org/project/facebook-react",
        "badges": {
          "health-score": "https://insights.linuxfoundation.org/api/badge/health-score?project=facebook-react",
          "active-contributors": "https://insights.linuxfoundation.org/api/badge/active-contributors?project=facebook-react&repos=..."
        },
        "resolution": "heuristic"
      }
    }
  ]
}
```

## Disabling LFX Integration

To disable LFX integration:

```toml
[tool.oss-sustain-guard.integrations.lfx]
enabled = false
```

Or remove the entire `[tool.oss-sustain-guard.integrations.lfx]` section.

## Best Practices

### 1. Use Explicit Mapping for Critical Dependencies

For dependencies where accuracy is important, use explicit mapping:

```toml
[tool.oss-sustain-guard.integrations.lfx.project_map]
"npm:your-critical-package" = "exact-lfx-slug"
```

### 2. Verify Badge URLs

LFX badge endpoints are stable, but you can verify by visiting:
- `https://insights.linuxfoundation.org/project/{slug}`

### 3. Handle Missing Data Gracefully

If a package doesn't have LFX data:
- Terminal output does not show LFX link
- HTML reports show "—" in the LFX column
- JSON output omits the `lfx` field
- Analysis continues normally

## Examples

### Example 1: React (Heuristic)

```bash
# Package: npm:react
# Repo: https://github.com/facebook/react
# LFX Slug: facebook-react (inferred)
# LFX URL: https://insights.linuxfoundation.org/project/facebook-react
```

### Example 2: Kubernetes (Config Mapping)

```toml
[tool.oss-sustain-guard.integrations.lfx.project_map]
"github:kubernetes/kubernetes" = "kubernetes-kubernetes"
```

```bash
# Package: github:kubernetes/kubernetes
# Repo: https://github.com/kubernetes/kubernetes
# LFX Slug: kubernetes-kubernetes (config)
# LFX URL: https://insights.linuxfoundation.org/project/kubernetes-kubernetes
```

## Troubleshooting

### LFX Links Not Appearing

1. **Check if LFX is enabled**:
   ```toml
   [tool.oss-sustain-guard.integrations.lfx]
   enabled = true
   ```

2. **Verify repository URL**:
   - LFX integration works best with GitHub URLs
   - Ensure the repository URL is in the analysis results

3. **Add explicit mapping**:
   - If heuristic resolution fails, add an explicit mapping

### Incorrect LFX Project

If the wrong LFX project is linked:

1. Add an explicit mapping in your config:
   ```toml
   [tool.oss-sustain-guard.integrations.lfx.project_map]
   "ecosystem:package" = "correct-lfx-slug"
   ```

2. Find the correct slug by visiting the LFX Insights website

## Related Resources

- [LFX Insights](https://insights.linuxfoundation.org/)
- [LFX Insights Documentation](https://docs.linuxfoundation.org/lfx/insights)
- [CHAOSS Metrics](https://chaoss.community/) - Metrics framework used by LFX

## Implementation Details

### URL Generation Only

This integration does NOT:
- Make HTTP requests to LFX servers
- Require API keys or authentication
- Impact analysis performance
- Fail if LFX is down

It ONLY generates URLs that browsers/tools can fetch independently.

### Resilience

The integration is designed to never break analysis:
- If resolution fails, LFX data is simply omitted
- Errors are silently handled
- Analysis continues normally

### Performance

URL generation adds negligible overhead:
- No network calls during analysis
- Simple string operations only
- Caching not required
