# Pre-Commit Integration Guide

OSS Sustain Guard can be used as a Pre-Commit hook, automatically checking the sustainability of dependency packages before committing code.

## Setup

### 1. Install Pre-Commit

```bash
pip install pre-commit
```

### 2. Configure `.pre-commit-config.yaml`

Create a `.pre-commit-config.yaml` file in your project root with the following configuration:

```yaml
repos:
  - repo: https://github.com/onukura/oss-sustain-guard
    rev: v0.1.0
    hooks:
      - id: oss-sustain-guard-requirements
```

For multi-language support, add language-specific resolvers as needed.

### 3. Install Pre-Commit Hooks

```bash
pre-commit install
```

The hooks will automatically run on your next commit.

## Usage

### Automatic Execution on Commit

When `requirements.txt` is staged, the hook automatically runs:

```bash
git commit -m "Update dependencies"
```

### Manual Hook Execution

Run the hook manually on all files:

```bash
pre-commit run oss-sustain-guard-requirements --all-files
```

Skip the hook if needed:

```bash
git commit -m "Your message" --no-verify
```

## Hook Configuration

### Hook 1: Automatic `requirements.txt` Check

```yaml
- id: oss-sustain-guard-requirements
```

- **Trigger:** Automatically runs when `requirements.txt` is committed
- **Files:** Only monitors `requirements.txt` (Python dependencies)
- **Scope:** Analyzes all packages listed in the file
- **💡 Tip:** Use the `--compact` format for cleaner pre-commit output

### Hook 2: Interactive Manual Check

```yaml
- id: oss-sustain-guard-pyproject
  stages: [manual]
```

For manual execution with specific packages:

```bash
pre-commit run oss-sustain-guard-pyproject --hook-stage manual
```

Then provide package names as arguments:

```bash
oss-guard check flask django numpy --compact
```

**Best Practice:** Add `--compact` to your hook configuration for readable output:

```yaml
repos:
  - repo: https://github.com/onukura/oss-sustain-guard
    rev: v0.1.0
    hooks:
      - id: oss-sustain-guard-requirements
        args: ['--compact']
```

## Multi-Language Support

OSS Sustain Guard supports multiple package ecosystems:

```bash
# Python packages
oss-guard check requests flask

# JavaScript (npm)
oss-guard check npm:react npm:vue

# Rust (crates.io)
oss-guard check rust:tokio rust:serde

# Go
oss-guard check go:github.com/golang/go

# Other languages
oss-guard check ruby:rails php:symfony/console
```

## Hook Behavior

1. **Package Detection:** Reads package names from the monitored file or command arguments
2. **Sustainability Analysis:** Evaluates each package using 9 key metrics:
   - Bus Factor
   - Maintainer Drain
   - Zombie Check
   - Merge Velocity
   - CI Status
   - Funding
   - Release Cadence
   - Security Posture
   - Community Health
3. **Cache-Based Lookup:** Uses pre-computed scores from `data/database.json` for fast results
4. **Result Display:** Shows results in a rich formatted table with color-coded risk levels

### Output Example

```text
🔍 Analyzing 3 package(s)...
  -> Found flask in cache.
  -> Found django in cache.
  -> requests not in cache. Performing real-time analysis...

OSS Sustain Guard Report
┏━━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Package ┃ Score ┃ Risk   ┃ Details         ┃
┡━━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ flask   │  80   │ ⚠️ Med  │ Release Good    │
│ django  │  82   │ ✅ Low  │ Security Good   │
│ requests│  85   │ ✅ Low  │ Excellent       │
└─────────┴───────┴────────┴─────────────────┘
```

### Risk Levels

| Score | Risk Level | Color |
|-------|-----------|-------|
| < 50  | Critical  | 🔴 Red |
| 50-79 | Warning   | 🟡 Yellow |
| ≥ 80  | Safe      | 🟢 Green |

## Troubleshooting

### Hook Not Running

Reinstall the hooks:

```bash
pre-commit uninstall
pre-commit install
```

### Missing GitHub Token Error

OSS Sustain Guard uses the GitHub GraphQL API. For packages not in the cache, a GitHub token is required:

```bash
export GITHUB_TOKEN=your_github_token
```

Or configure in `.env`:

```bash
GITHUB_TOKEN=your_github_token
```

**Important:** Set the token before running hooks.

### Cache Issues

To refresh or update the sustainability database:

```bash
python builder/build_db.py
```

This updates `data/database.json` with the latest package scores.

## Best Practices

1. **Use `--compact` for better readability**

   The compact format produces one-line-per-package output, perfect for pre-commit hooks:

   ```yaml
   repos:
     - repo: https://github.com/onukura/oss-sustain-guard
       rev: v0.1.0
       hooks:
         - id: oss-sustain-guard-requirements
           args: ['--compact']
   ```

2. **Keep Cache Updated**

   Regularly update the database for latest metrics:

   ```bash
   python builder/build_db.py
   ```

3. **Handle Failures Gracefully**

   - Network errors are handled gracefully and don't block commits
   - Use `--no-verify` to bypass hooks in emergencies

4. **Multi-Stage Hooks**

   Configure hooks to run at different stages:

   ```yaml
   hooks:
     - id: oss-sustain-guard-requirements
       stages: [commit, push, manual]
   ```

5. **Exclude Problematic Packages**

   Configure excluded packages in `oss_sustain_guard/config.py` if needed.

## Related Documentation

- [Pre-Commit Documentation](https://pre-commit.com/)
- [Getting Started](./GETTING_STARTED.md)
- [Database Schema](./DATABASE_SCHEMA.md)
- [GitHub Token Setup](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
