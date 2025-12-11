# Directory Exclusion Configuration Examples

This document provides practical examples for configuring directory exclusions in OSS Sustain Guard.

## Basic Configuration

### Example 1: Use Defaults Only

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

### Example 2: Add Custom Patterns

Add your own patterns in addition to defaults:

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = ["scratch", "experiments", "legacy"]
use_defaults = true
use_gitignore = true
```

Result: Excludes defaults + .gitignore + your custom patterns.

### Example 3: Minimal Exclusions (Experts Only)

Use only your custom patterns, disable defaults:

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = ["my_cache", "temp"]
use_defaults = false
use_gitignore = false
```

**Warning:** This may scan build outputs and dependencies unnecessarily.

## Advanced Examples

### Example 4: Monorepo with Shared Cache

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

### Example 5: Respect .gitignore Only

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = []
use_defaults = false  # Disable built-in patterns
use_gitignore = true  # Only use .gitignore
```

Useful when you have a comprehensive `.gitignore`.

### Example 6: Custom Development Environment

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

## .gitignore Integration Examples

### Example .gitignore

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

## Testing Your Configuration

### Verify Exclusions

```bash
# Run with verbose to see what's being scanned
oss-guard check --recursive --verbose

# Check a specific directory
oss-guard check --root-dir ./my-project --recursive
```

### Debug Configuration

```python
from oss_sustain_guard.config import get_exclusion_patterns
from pathlib import Path

# Get all exclusion patterns for a directory
patterns = get_exclusion_patterns(Path("."))
print(f"Total patterns: {len(patterns)}")
print(f"Sample patterns: {sorted(list(patterns))[:20]}")
```

## Best Practices

1. **Start with defaults:** Always use `use_defaults = true` unless you have a specific reason not to
2. **Leverage .gitignore:** Set `use_gitignore = true` to automatically exclude ignored directories
3. **Add project-specific patterns:** Use `patterns` for directories unique to your project
4. **Test before committing:** Run with `--recursive` to verify the configuration works as expected

## Common Use Cases

### Data Science Projects

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

### Microservices Monorepo

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

### Multi-Language Project

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

## Troubleshooting

### Too Many Directories Excluded

If scanning finds nothing:

1. Check `.gitignore` - it might be too aggressive
2. Set `use_gitignore = false` temporarily
3. Review `patterns` list for accidental exclusions

### Unwanted Directories Scanned

If build directories are being scanned:

1. Ensure `use_defaults = true`
2. Add specific patterns to `patterns`
3. Check if directory names match exclusion patterns exactly

### Permission Errors

OSS Sustain Guard automatically skips directories it can't read. No configuration needed.

## See Also

- [Recursive Scanning Guide](RECURSIVE_SCANNING_GUIDE.md)
- [Exclude Packages Guide](EXCLUDE_PACKAGES_GUIDE.md)

