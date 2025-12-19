# Contribution Examples

This directory contains example contribution files to help you understand the expected format.

## Files

### `example-contribution.json`

A complete example showing the structure of a valid contribution file with:
- Contribution metadata (contributor, date, tool version)
- Two package entries with metrics and signals
- Proper cache metadata marked as "user_analysis"

## How to Use These Examples

### 1. Review the Structure

Open `example-contribution.json` to see:
- Top-level `_contribution_metadata` object
- `packages` dictionary with package entries
- Required fields for each package
- Metric structure and score ranges
- Signal data format

### 2. Validate the Example

You can validate the example file to see how validation works:

```bash
oss-guard validate-contribution examples/contributions/example-contribution.json
```

### 3. Create Your Own

Use the example as a template when creating your contributions:

```bash
# Analyze packages locally
oss-guard check requests flask

# Export your results (creates a file like this example)
oss-guard export python --contributor your-github-username

# Validate before submitting
oss-guard validate-contribution contribution-python-*.json
```

## Key Points

- **Schema Version**: Always use `"2.0"`
- **Contributor**: Your GitHub username for attribution
- **Source**: Cache metadata should have `"source": "user_analysis"` (automatically set)
- **GitHub URLs**: Must be valid GitHub repository URLs
- **Scores**: Must not exceed `max_score`
- **Risk Levels**: Must be one of: `Critical`, `High`, `Medium`, `Low`, `None`

## Need Help?

- Read the [Community Contribution Guide](../../docs/COMMUNITY_CONTRIBUTION_GUIDE.md)
- Check the [Architecture Documentation](../../docs/COMMUNITY_CONTRIBUTION_ARCHITECTURE.md)
- Open an issue if you have questions
