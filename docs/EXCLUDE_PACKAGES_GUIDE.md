# OSS Sustain Guard - Exclude Packages Configuration Guide

The exclude packages feature allows you to exclude specific packages from sustainability checks.

## Configuration Methods

### Method 1: `.oss-sustain-guard.toml` (Recommended - Local Project Config)

Create a `.oss-sustain-guard.toml` file in the project root:

```toml
[tool.oss-sustain-guard]
exclude = [
    "some-internal-package",
    "legacy-dependency",
    "proprietary-lib",
]
```

### Method 2: `pyproject.toml` (Project-wide Config)

Add the configuration to your existing `pyproject.toml`:

```toml
[tool.oss-sustain-guard]
exclude = [
    "internal-package",
    "legacy-dependency",
]
```

## Configuration Priority

Configuration files are loaded in the following priority order:

1. **`.oss-sustain-guard.toml`** (Highest Priority)
   - Project-specific configuration
   - When `.oss-sustain-guard.toml` exists, only this file is used

2. **`pyproject.toml`** (Fallback)
   - Used only if `.oss-sustain-guard.toml` does not exist

## Usage Examples

### Example 1: Checking requirements.txt

`requirements.txt`:

```text
flask
django
internal-lib
```

`.oss-sustain-guard.toml`:

```toml
[tool.oss-sustain-guard]
exclude = ["internal-lib"]
```

Run:

```bash
oss-guard check requirements.txt
```

Output:

```text
🔍 Analyzing 3 package(s)...
  -> Found flask in cache.
  -> Found django in cache.
  -> Skipping internal-lib (excluded)

⏭️  Skipped 1 excluded package(s).
```

### Example 2: Direct Package Specification

```bash
oss-guard check flask django internal-lib
```

Output:

```text
🔍 Analyzing 3 package(s)...
  -> Found flask in cache.
  -> Found django in cache.
  -> Skipping internal-lib (excluded)

⏭️  Skipped 1 excluded package(s).
```

## Case-Insensitive Matching

Package exclusion checks are **case-insensitive**.

The following are all treated as the same package:

```toml
[tool.oss-sustain-guard]
exclude = ["Flask"]
```

```bash
# All of these will be excluded
oss-guard check flask
oss-guard check Flask
oss-guard check FLASK
```

## Pre-Commit Integration

When used with Pre-Commit hooks, excluded packages are automatically skipped:

```bash
git add requirements.txt
git commit -m "Update dependencies"
# Pre-Commit hook runs and skips excluded packages
```

## Best Practices

1. **Exclude Internal Packages**

   ```toml
   exclude = ["my-company-lib", "internal-utils"]
   ```

2. **Exclude Legacy Dependencies**

   ```toml
   exclude = ["legacy-package", "deprecated-lib"]
   ```

3. **Use `.oss-sustain-guard.toml` for Project-Specific Settings**
   - `pyproject.toml` is used for multiple purposes
   - `.oss-sustain-guard.toml` is dedicated to this tool

## Troubleshooting

### Exclude Configuration Not Applied

1. Verify file name
   - `.oss-sustain-guard.toml` (starts with a dot)
   - `pyproject.toml`

2. Check TOML syntax

   ```bash
   # Validate TOML syntax with Python
   python -c "import tomllib; print(tomllib.loads(open('.oss-sustain-guard.toml').read()))"
   ```

3. Verify section structure

   ```toml
   [tool.oss-sustain-guard]  # Required
   exclude = [...]          # Must be a list
   ```

### Verify Configuration

Use verbose output to confirm:

```bash
oss-guard check requirements.txt -v
```

### Reset Configuration

Remove the configuration file:

```bash
rm .oss-sustain-guard.toml
```

## References

- [TOML Documentation](https://toml.io/)
- [OSS Sustain Guard README](./README.md)
