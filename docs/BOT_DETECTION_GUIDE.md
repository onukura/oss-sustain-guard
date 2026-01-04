# Bot Detection Customization Guide

## Overview

OSS Sustain Guard uses intelligent bot detection to exclude automated accounts (CI/CD systems, dependabot, etc.) from sustainability metrics calculations. This ensures that metrics accurately reflect human contributor activity.

## How Bot Detection Works

Bot detection operates in a multi-stage process:

### Stage 1: Exact Pattern Matching (Most Reliable)

Matches against known bot account patterns from GitHub, GitLab, and other services:

- `dependabot[bot]`
- `github-actions[bot]`
- `renovate[bot]`
- `dependabot-preview[bot]`
- And many others...

### Stage 2: Email Domain Detection

Checks if the commit author's email belongs to a bot service:

- `*@noreply.github.com`
- `*@users.noreply.github.com`
- `*@gitlab.com`

### Stage 3: Keyword-based Matching (Fallback)

Checks if the login/name contains common bot keywords:

- Contains "bot"
- Contains "action"
- Contains "ci-"
- And others...

### Stage 4: Custom Exclusion List

Allows you to explicitly mark specific users as bots through configuration.

## Configuration

### Adding Custom Excluded Users

You can configure OSS Sustain Guard to treat specific accounts as bots using either `.oss-sustain-guard.toml` or `pyproject.toml`.

#### Using `.oss-sustain-guard.toml` (Recommended)

Create or edit `.oss-sustain-guard.toml` in your project root:

```toml
[tool.oss-sustain-guard]
# Exclude specific users from contributor metrics
exclude-users = [
    "my-internal-ci-user",
    "release-automation",
    "internal-bot-account",
]
```

#### Using `pyproject.toml`

Add to your `pyproject.toml`:

```toml
[tool.oss-sustain-guard]
exclude-users = [
    "my-internal-ci-user",
    "release-automation",
]
```

## Common Use Cases

### 1. Internal CI/CD Accounts

If your organization uses internal CI/CD systems that commit under a specific account:

```toml
[tool.oss-sustain-guard]
exclude-users = ["jenkins-bot", "gitlab-runner", "company-ci"]
```

### 2. Release Automation

If you have a dedicated bot account for automatic releases:

```toml
[tool.oss-sustain-guard]
exclude-users = ["autorelease-bot", "version-bumper"]
```

### 3. Documentation Generators

If you use automated tools that commit generated files:

```toml
[tool.oss-sustain-guard]
exclude-users = ["docgen-bot", "changelog-generator"]
```

## Examples

### Example: Python Project with Internal Bot

`.oss-sustain-guard.toml`:

```toml
[tool.oss-sustain-guard]
# Exclude both built-in bot patterns and our internal CI account
exclude-users = ["internal-ci-system"]
exclude = ["test-fixtures", "example-packages"]
```

Now when analyzing your project:

- `dependabot[bot]` will be automatically excluded (built-in pattern)
- `github-actions[bot]` will be automatically excluded (built-in pattern)
- `internal-ci-system` will be excluded (custom configuration)
- Only genuine human contributors will be counted

### Example: Monorepo with Multiple Bot Systems

`.oss-sustain-guard.toml`:

```toml
[tool.oss-sustain-guard]
exclude-users = [
    "jenkins-automation",
    "gha-deployer",
    "changelog-bot",
    "security-scanner-bot",
]
```

## Troubleshooting

### Issue: A real user is being excluded as a bot

If a legitimate contributor's name contains a bot keyword (e.g., "robotics-expert"), the keyword-based detection might incorrectly classify them as a bot.

**Solution**: Use the exact pattern matching by ensuring their account doesn't match any known patterns, or contact your VCS administrator if the name pattern can be changed.

Alternatively, you can manually verify by checking the VCS API directly.

### Issue: A known bot is not being excluded

If a bot account is not in the default list and doesn't match keyword patterns:

1. Check if it should be added to the default patterns (report an issue)
2. Add it to your `exclude-users` configuration

**Example**: If your organization uses a custom bot `acme-corp-bot`:

```toml
[tool.oss-sustain-guard]
exclude-users = ["acme-corp-bot"]
```

## Built-in Bot Patterns

The following bots are automatically recognized without additional configuration:

### GitHub Bots

- `dependabot[bot]`
- `github-actions[bot]`
- `renovate[bot]`
- `snyk-bot[bot]`
- `codecov[bot]`
- `coveralls[bot]`
- And others...

### GitLab Bots

- `dependabot`
- `renovate-bot`
- `gitlab-runner`

### Email Domain Patterns

- Any email ending in `@noreply.github.com`
- Any email ending in `@users.noreply.github.com`
- Any email ending in `@gitlab.com`

### Keyword Patterns (Fallback)

- Logins containing "bot"
- Logins containing "action"
- Logins containing "ci-"
- Logins containing "copilot"
- And others...

## Impact on Metrics

Bot exclusion affects the following metrics:

- **Contributor Redundancy (Bus Factor)**: Excluded from contributor count
- **Maintainer Retention**: Excluded from maintainer analysis
- **Contributor Retention**: Excluded from retention calculations
- **Contributor Attraction**: Excluded from new contributor count
- **Organizational Diversity**: Excluded from diversity analysis
- **Contributor Count Signal**: Excluded from contributor count

## Best Practices

1. **Start with defaults**: The built-in patterns cover most common bots. Only add custom exclusions when necessary.

2. **Document your choices**: Comment your configuration to explain why specific accounts are excluded.

3. **Review periodically**: As your automation tools change, update your configuration accordingly.

4. **Be conservative**: Only exclude accounts you're certain are bots. False negatives (missing a bot) are better than false positives (incorrectly excluding humans).

5. **Test your configuration**: Run `os4g check --demo` to see how bot detection affects your metrics.

## Related Documentation

- [Scoring Profiles Guide](./SCORING_PROFILES_GUIDE.md)
- [Built-in Metrics Guide](./BUILT_IN_METRICS_GUIDE.md)
- [Custom Metrics Guide](./CUSTOM_METRICS_GUIDE.md)
