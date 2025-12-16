# Recursive Scanning Guide

## Overview

OSS Sustain Guard supports recursive scanning of directories to automatically discover and analyze packages from manifest and lockfiles across your entire project tree, including monorepos and complex project structures.

## Options

### `--recursive` / `-R`

Enables recursive scanning of subdirectories to find manifest and lockfiles.

**Default:** `False` (only scans the specified directory)

```bash
# Scan only the current directory (default)
oss-guard check

# Recursively scan all subdirectories
oss-guard check --recursive
```

### `--depth` / `-d`

Controls the maximum directory depth for recursive scanning.

**Default:** `None` (unlimited depth)

```bash
# Scan current directory and one level of subdirectories
oss-guard check --recursive --depth 1

# Scan up to 3 levels deep
oss-guard check --recursive --depth 3

# Unlimited depth (default when using --recursive)
oss-guard check --recursive
```

**Note:** `--depth 0` in recursive mode will only scan the root directory.

## Use Cases

### Monorepo Analysis

Analyze all packages across multiple subprojects in a monorepo:

```bash
# Project structure:
# monorepo/
#   ├── frontend/
#   │   └── package.json       (React, Vue, etc.)
#   ├── backend/
#   │   └── requirements.txt   (Python)
#   └── shared/
#       └── Cargo.toml         (Rust)

cd monorepo
oss-guard check --recursive
```

**Output:**

```shell
🔍 No packages specified. Recursively scanning /path/to/monorepo (unlimited depth)...
✅ Detected ecosystems: javascript, python, rust
📋 Found manifest file: frontend/package.json
   Found 10 package(s) in package.json
📋 Found manifest file: backend/requirements.txt
   Found 5 package(s) in requirements.txt
📋 Found manifest file: shared/Cargo.toml
   Found 3 package(s) in Cargo.toml
🔍 Analyzing 18 package(s)...
```

### Large Workspace with Depth Limit

For very large workspaces, limit the scan depth to avoid excessive scanning:

```bash
# Only scan immediate subdirectories (depth 1)
oss-guard check --recursive --depth 1

# Scan up to 2 levels deep
oss-guard check --recursive --depth 2
```

This is useful when you have deep directory structures but only care about top-level projects.

### Specific Ecosystem in Monorepo

Combine with ecosystem filtering to analyze only specific language packages:

```bash
# Find all Python packages recursively
oss-guard check --recursive --ecosystem python

# Find all JavaScript packages in subdirectories
oss-guard check --recursive --ecosystem javascript
```

### Include Lockfiles Recursively

Scan all lockfiles across the project tree:

```bash
# Find and analyze all packages from lockfiles recursively
oss-guard check --recursive --include-lock

# Limit depth for lockfile scanning
oss-guard check --recursive --include-lock --depth 2
```

## Ignored Directories

To optimize performance and avoid scanning irrelevant files, OSS Sustain Guard automatically skips certain directories during recursive scanning.

### Default Exclusions

The following directories are excluded by default:

**Node.js/JavaScript:**

- `node_modules/`, `.npm/`, `.yarn/`

**Python:**

- `__pycache__/`, `venv/`, `.venv/`, `env/`, `.env/`, `.virtualenv/`
- `.tox/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- `*.egg-info/`

**Rust:**

- `target/`

**Go:**

- `vendor/`

**Java/Kotlin/Scala:**

- `.gradle/`, `.m2/`, `.ivy2/`

**PHP:**

- `vendor/` (Composer)

**Ruby:**

- `.bundle/`

**.NET/C#:**

- `bin/`, `obj/`, `packages/`

**Build Outputs (General):**

- `build/`, `dist/`, `out/`, `.output/`

**Version Control:**

- `.git/`, `.svn/`, `.hg/`, `.bzr/`

**IDEs:**

- `.idea/`, `.vscode/`, `.vs/`

**Hidden Directories:**

- Any directory starting with `.` (except those explicitly listed)

### Configurable Exclusions

You can customize exclusion patterns in `.oss-sustain-guard.toml` or `pyproject.toml`:

```toml
[tool.oss-sustain-guard.exclude-dirs]
# Additional patterns to exclude (in addition to defaults)
patterns = ["custom_cache", "temp", "scratch"]

# Use default exclusions (recommended)
# Default: true
use_defaults = true

# Respect .gitignore patterns
# Default: true
use_gitignore = true
```

**Example - Disable defaults and use custom patterns only:**

```toml
[tool.oss-sustain-guard.exclude-dirs]
patterns = ["my_venv", "my_build"]
use_defaults = false
use_gitignore = false
```

### .gitignore Integration

When `use_gitignore = true` (default), OSS Sustain Guard automatically reads your `.gitignore` file and excludes matching directories.

**Example `.gitignore`:**

```gitignore
# Build outputs
dist
*.pyc

# Custom directories
temp_files
cache
```

**Result:** The `dist`, `temp_files`, and `cache` directories will be excluded from scanning.

**Limitations:**

- Only simple directory patterns are supported (no complex glob patterns)
- Negation patterns (`!pattern`) are ignored
- Path-based patterns (`src/build`) are not supported
- Only top-level patterns and `*/dirname` patterns are recognized

### Verification

To verify which directories are being scanned, use the `--verbose` flag:

```bash
oss-guard check --recursive --verbose
```

This will show which directories were found and which packages were detected.

## Examples

### Example 1: Full Monorepo Scan

```bash
# Scan entire monorepo with unlimited depth
cd /path/to/monorepo
oss-guard check --recursive --verbose
```

### Example 2: Shallow Scan for Quick Check

```bash
# Only check immediate subdirectories
oss-guard check --recursive --depth 1
```

### Example 3: Deep Scan with Lockfiles

```bash
# Scan up to 3 levels deep, including lockfiles
oss-guard check --recursive --depth 3 --include-lock
```

### Example 4: Monorepo with Specific Root

```bash
# Scan from a specific subdirectory
oss-guard check --root-dir ./projects --recursive --depth 2
```

### Example 5: Export Results for All Packages

```bash
# Scan recursively and show detailed metrics
oss-guard check --recursive --verbose --show-models
```

## Performance Considerations

1. **Depth Limit:** For large codebases, use `--depth` to limit scanning depth and improve performance
2. **Excluded Directories:** Common build/cache directories are automatically skipped
3. **Specific Manifest:** Use `--manifest` to analyze a specific file instead of auto-detection

## Combining Options

You can combine recursive scanning with other options:

```bash
# Full analysis with all features
oss-guard check \
  --recursive \
  --depth 2 \
  --include-lock \
  --verbose \
  --show-models \
  --profile security_first

# Cache-free recursive scan
oss-guard check --recursive --no-cache

# Recursive scan with custom cache settings
oss-guard check --recursive --cache-ttl 3600
```

## Troubleshooting

### No manifests found

If recursive scanning doesn't find any manifests:

1. Verify you're in the correct directory: `pwd`
2. Check if manifest files exist: `find . -name "package.json" -o -name "requirements.txt"`
3. Ensure files aren't in ignored directories (e.g., `node_modules/`)

### Too many packages detected

If scanning finds too many packages:

1. Use `--depth` to limit scanning depth
2. Use `--root-dir` to specify a more specific starting directory
3. Configure excluded packages in `.oss-sustain-guard.toml`

### Permission errors

If you encounter permission errors during scanning:

- The tool automatically skips directories it cannot read
- Check directory permissions: `ls -la`
- Run with appropriate permissions if needed

## Best Practices

1. **Start with limited depth:** Begin with `--depth 1` or `--depth 2` to understand what will be scanned
2. **Use `.oss-sustain-guard.toml`:** Configure excluded packages to skip known safe dependencies
3. **Combine with CI/CD:** Use recursive scanning in CI pipelines to monitor all subprojects
4. **Profile selection:** Choose appropriate scoring profiles for your use case

## Related Documentation

- [Exclude Packages Guide](EXCLUDE_PACKAGES_GUIDE.md)
- [Scoring Profiles Guide](SCORING_PROFILES_GUIDE.md)
- [Pre-commit Integration](PRE_COMMIT_INTEGRATION.md)
