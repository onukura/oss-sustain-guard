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

## Directory Exclusions (Recursive Scanning)

When using recursive scanning (`--recursive`), you can also configure which directories to exclude. This section provides practical examples.

### Basic Configuration

#### Option 1: Use Defaults Only (Recommended)

The simplest configuration - use all default exclusions:

```toml
# .oss-sustain-guard.toml
[tool.oss-sustain-guard.exclude-dirs]
# Nothing to configure - defaults are used automatically
use_defaults = true
use_gitignore = true
```

This excludes:

- 36+ common directories (node_modules, venv, __pycache__, etc.)
- Patterns from your `.gitignore`

#### Option 2: Add Custom Patterns

Add your own patterns in addition to defaults:

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = ["scratch", "experiments", "legacy"]
use_defaults = true
use_gitignore = true
```

Result: Excludes defaults + .gitignore + your custom patterns.

#### Option 3: Minimal Exclusions (Experts Only)

Use only your custom patterns, disable defaults:

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = ["my_cache", "temp"]
use_defaults = false
use_gitignore = false
```

**Warning:** This may scan build outputs and dependencies unnecessarily.

### Advanced Examples

#### Example 1: Monorepo with Shared Cache

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = [
    "shared_cache",
    "common_builds",
    "archived_projects",
]
use_defaults = true
use_gitignore = true
```

#### Example 2: Respect .gitignore Only

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = []
use_defaults = false  # Disable built-in patterns
use_gitignore = true  # Only use .gitignore
```

Useful when you have a comprehensive `.gitignore`.

#### Example 3: Custom Development Environment

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = [
    "bazel-out",        # Bazel build outputs
    ".pants.d",         # Pants build system
    "buck-out",         # Buck build outputs
    "cmake-build-*",    # CMake builds
]
use_defaults = true
```

### .gitignore Integration Examples

#### Example .gitignore

```gitignore
# Build outputs
dist
build
*.pyc

# Development
.vscode/
.idea/

# Custom caches
cache
temp_data
experimental
```

With `use_gitignore = true`, the following will be excluded:

- `dist`
- `build`
- `cache`
- `temp_data`
- `experimental`

Note: `*.pyc` is a file pattern and won't be used for directory exclusion.

### Common Use Cases

#### Data Science Projects

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = [
    "data",
    "datasets",
    "models",
    "checkpoints",
    "notebooks/.ipynb_checkpoints",
]
use_defaults = true
```

#### Microservices Monorepo

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = [
    "archived-services",
    "docker-volumes",
    "k8s-temp",
]
use_defaults = true
use_gitignore = true
```

#### Multi-Language Project

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = [
    "cmake-build-debug",
    "cmake-build-release",
    ".cargo",
    "zig-cache",
]
use_defaults = true  # Already covers most languages
```

### Testing Your Configuration

#### Verify Exclusions

```bash
# Run with verbose to see what's being scanned
oss-guard check --recursive --verbose

# Check a specific directory
oss-guard check --root-dir ./my-project --recursive
```

#### Debug Configuration

```python
from oss_sustain_guard.config import get_exclusion_patterns
from pathlib import Path

# Get all exclusion patterns for a directory
patterns = get_exclusion_patterns(Path("."))
print(f"Total patterns: {len(patterns)}")
print(f"Sample patterns: {sorted(list(patterns))[:20]}")
```

### Troubleshooting

#### Too Many Directories Excluded

If scanning finds nothing:

1. Check `.gitignore` - it might be too aggressive
2. Set `use_gitignore = false` temporarily
3. Review `patterns` list for accidental exclusions

#### Unwanted Directories Scanned

If build directories are being scanned:

1. Ensure `use_defaults = true`
2. Add specific patterns to `patterns`
3. Check if directory names match exclusion patterns exactly

#### Permission Errors

OSS Sustain Guard automatically skips directories it can't read. No configuration needed.

### Best Practices

1. **Start with defaults:** Always use `use_defaults = true` unless you have a specific reason not to
2. **Leverage .gitignore:** Set `use_gitignore = true` to automatically exclude ignored directories
3. **Add project-specific patterns:** Use `patterns` for directories unique to your project
4. **Test before committing:** Run with `--recursive` to verify the configuration works as expected

## References

- [TOML Documentation](https://toml.io/)
- [Recursive Scanning Guide](./RECURSIVE_SCANNING_GUIDE.md) - More details on recursive scanning behavior
- [Getting Started](./GETTING_STARTED.md)
