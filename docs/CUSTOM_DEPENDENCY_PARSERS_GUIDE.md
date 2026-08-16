# Custom Dependency Parsers Guide

This guide explains how to create custom dependency parsers to extend OSS Sustain Guard's support for additional package managers, lockfile formats, or ecosystems.

## Overview

Dependency parsers are plugins that extract dependency information from lockfiles (e.g., `package-lock.json`, `Cargo.lock`, `requirements.txt`). OSS Sustain Guard uses a plugin-based architecture that allows you to add support for:

- New package managers
- Custom lockfile formats
- Private/enterprise dependency systems
- Monorepo tools with custom dependency manifests

## Quick Start

### 1. Create a Parser Module

Create a Python module that defines a `DependencyParserSpec`:

```python
# my_parser.py
from pathlib import Path
from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo

def parse_my_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse custom lockfile format."""
    lockfile_path = Path(lockfile_path)

    if not lockfile_path.exists():
        return None

    # Parse your lockfile format
    content = lockfile_path.read_text(encoding="utf-8")

    # Extract dependencies
    deps = []
    # ... your parsing logic here ...

    return DependencyGraph(
        root_package="my-project",
        ecosystem="my-ecosystem",
        direct_dependencies=deps,
        transitive_dependencies=[],
    )

# Define the parser specification
PARSER = DependencyParserSpec(
    name="my-parser",
    lockfile_names={"my-lock.json"},
    parse=parse_my_lockfile,
)
```

### 2. Register as Plugin

Add your parser to your project's `pyproject.toml`:

```toml
[project.entry-points."oss_sustain_guard.dependency_parsers"]
my-parser = "my_package.my_parser:PARSER"
```

### 3. Test Your Parser

```bash
# OSS Sustain Guard will automatically discover and use your parser
os4g scan /path/to/project
```

## Core Concepts

### DependencyParserSpec

The `DependencyParserSpec` is the main interface for parsers:

```python
class DependencyParserSpec(NamedTuple):
    """Metadata for a dependency parser plugin."""

    name: str                           # Unique identifier for your parser
    lockfile_names: set[str]           # Lockfile patterns to match
    parse: Callable[[Path], DependencyGraph | None]  # Parser function
```

**Fields:**

- `name`: Unique identifier (e.g., `"npm"`, `"cargo"`, `"my-custom-parser"`)
- `lockfile_names`: Set of lockfile names to detect (e.g., `{"package-lock.json", "npm-shrinkwrap.json"}`)
- `parse`: Function that takes a lockfile path and returns a `DependencyGraph` or `None`

### DependencyGraph

The `DependencyGraph` represents parsed dependency information:

```python
@dataclass
class DependencyGraph:
    """Dependency graph extracted from a lockfile."""

    root_package: str                           # Root package name
    ecosystem: str                              # Ecosystem identifier
    direct_dependencies: list[DependencyInfo]   # Direct dependencies
    transitive_dependencies: list[DependencyInfo]  # Transitive dependencies
```

### DependencyInfo

Individual dependency information:

```python
@dataclass
class DependencyInfo:
    """Information about a single dependency."""

    name: str              # Package name
    ecosystem: str         # Ecosystem (python, javascript, rust, etc.)
    version: str | None    # Version (optional)
    is_direct: bool        # True if direct dependency
    depth: int             # Depth in dependency tree (0 = direct)
```

## Implementation Examples

### Example 1: Simple Requirements Parser

A minimal parser for a simple format:

```python
from pathlib import Path
from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo

def parse_simple_requirements(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse simple requirements file (one package per line)."""
    lockfile_path = Path(lockfile_path)

    if not lockfile_path.exists():
        return None

    try:
        content = lockfile_path.read_text(encoding="utf-8")
    except OSError:
        return None

    deps = []
    for line in content.splitlines():
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # Parse package name (before version specifier)
        name = line.split("==")[0].strip()
        version = line.split("==")[1].strip() if "==" in line else None

        deps.append(
            DependencyInfo(
                name=name,
                ecosystem="python",
                version=version,
                is_direct=True,
                depth=0,
            )
        )

    return DependencyGraph(
        root_package="my-project",
        ecosystem="python",
        direct_dependencies=deps,
        transitive_dependencies=[],
    )

PARSER = DependencyParserSpec(
    name="simple-requirements",
    lockfile_names={"requirements.simple"},
    parse=parse_simple_requirements,
)
```

### Example 2: JSON Lockfile Parser

A parser for JSON-based lockfiles:

```python
import json
from pathlib import Path
from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo

def parse_json_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse JSON lockfile format."""
    lockfile_path = Path(lockfile_path)

    if not lockfile_path.exists():
        return None

    try:
        with open(lockfile_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    # Extract root package info
    root_name = data.get("name", "unknown")

    # Parse dependencies
    deps = []
    for name, info in data.get("dependencies", {}).items():
        deps.append(
            DependencyInfo(
                name=name,
                ecosystem="javascript",
                version=info.get("version"),
                is_direct=True,
                depth=0,
            )
        )

    # Parse transitive dependencies (optional)
    transitive = []
    for name, info in data.get("devDependencies", {}).items():
        transitive.append(
            DependencyInfo(
                name=name,
                ecosystem="javascript",
                version=info.get("version"),
                is_direct=False,
                depth=1,
            )
        )

    return DependencyGraph(
        root_package=root_name,
        ecosystem="javascript",
        direct_dependencies=deps,
        transitive_dependencies=transitive,
    )

PARSER = DependencyParserSpec(
    name="my-json-lockfile",
    lockfile_names={"my-lock.json"},
    parse=parse_json_lockfile,
)
```

### Example 3: Advanced Parser with Error Handling

A robust parser with comprehensive error handling:

```python
from pathlib import Path
from typing import Any
from oss_sustain_guard.dependency_parsers.base import DependencyParserSpec
from oss_sustain_guard.dependency_graph import DependencyGraph, DependencyInfo

def parse_advanced_lockfile(lockfile_path: str | Path) -> DependencyGraph | None:
    """Parse lockfile with robust error handling."""
    lockfile_path = Path(lockfile_path)

    # Validate lockfile exists
    if not lockfile_path.exists():
        return None

    # Parse lockfile with error handling
    try:
        content = _read_lockfile(lockfile_path)
        data = _parse_lockfile_content(content)

        # Extract dependencies
        direct_deps = _extract_direct_dependencies(data)
        transitive_deps = _extract_transitive_dependencies(data)

        # Get root package name
        root_name = _get_root_package_name(lockfile_path, data)

        return DependencyGraph(
            root_package=root_name,
            ecosystem="my-ecosystem",
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
        )
    except Exception:
        # Silently fail and return None if parsing fails
        return None

def _read_lockfile(path: Path) -> str:
    """Read lockfile content."""
    return path.read_text(encoding="utf-8")

def _parse_lockfile_content(content: str) -> dict[str, Any]:
    """Parse lockfile content into structured data."""
    import json
    return json.loads(content)

def _extract_direct_dependencies(data: dict) -> list[DependencyInfo]:
    """Extract direct dependencies from parsed data."""
    deps = []
    for name, info in data.get("dependencies", {}).items():
        deps.append(
            DependencyInfo(
                name=name,
                ecosystem="my-ecosystem",
                version=info.get("version"),
                is_direct=True,
                depth=0,
            )
        )
    return deps

def _extract_transitive_dependencies(data: dict) -> list[DependencyInfo]:
    """Extract transitive dependencies from parsed data."""
    deps = []
    for name, info in data.get("transitive", {}).items():
        deps.append(
            DependencyInfo(
                name=name,
                ecosystem="my-ecosystem",
                version=info.get("version"),
                is_direct=False,
                depth=info.get("depth", 1),
            )
        )
    return deps

def _get_root_package_name(lockfile_path: Path, data: dict) -> str:
    """Determine root package name."""
    # Try to get from lockfile data
    if "name" in data:
        return data["name"]

    # Fall back to directory name
    return lockfile_path.parent.name

PARSER = DependencyParserSpec(
    name="advanced-parser",
    lockfile_names={"advanced.lock"},
    parse=parse_advanced_lockfile,
)
```

## Best Practices

### 1. Error Handling

Always handle errors gracefully and return `None` on failure:

```python
def parse_my_lockfile(lockfile_path: Path) -> DependencyGraph | None:
    try:
        # Parsing logic
        ...
    except Exception:
        # Don't raise exceptions - just return None
        return None
```

### 2. Validation

Validate lockfile format before parsing:

```python
def parse_my_lockfile(lockfile_path: Path) -> DependencyGraph | None:
    if not lockfile_path.exists():
        return None

    # Check file extension
    if lockfile_path.suffix != ".lock":
        return None

    # Check file size (avoid parsing huge files)
    if lockfile_path.stat().st_size > 100_000_000:  # 100MB
        return None

    # ... continue parsing ...
```

### 3. Performance

For large lockfiles, consider:

- Lazy parsing (parse only what's needed)
- Streaming JSON/YAML parsing
- Limiting depth of transitive dependencies

```python
def parse_large_lockfile(lockfile_path: Path) -> DependencyGraph | None:
    # Limit transitive dependency depth
    MAX_DEPTH = 3

    # ... parsing logic ...

    transitive_deps = [
        dep for dep in all_deps
        if dep.depth <= MAX_DEPTH
    ]
```

### 4. Testing

Test your parser with various inputs:

```python
def test_parser():
    # Test valid lockfile
    result = parse_my_lockfile("tests/fixtures/valid.lock")
    assert result is not None
    assert len(result.direct_dependencies) > 0

    # Test missing file
    result = parse_my_lockfile("nonexistent.lock")
    assert result is None

    # Test invalid format
    result = parse_my_lockfile("tests/fixtures/invalid.lock")
    assert result is None
```

## Built-in Parsers Reference

OSS Sustain Guard includes parsers for these ecosystems:

| Ecosystem | Parser | Lockfiles |
|-----------|--------|-----------|
| Python | pip | `requirements.txt` |
| Python | poetry | `poetry.lock` |
| Python | pipenv | `Pipfile.lock` |
| Python | uv | `uv.lock` |
| JavaScript | npm | `package-lock.json`, `npm-shrinkwrap.json` |
| JavaScript | yarn | `yarn.lock` |
| JavaScript | pnpm | `pnpm-lock.yaml` |
| JavaScript | bun | `bun.lockb` |
| JavaScript | deno | `deno.lock` |
| Rust | cargo | `Cargo.lock` |
| Go | go modules | `go.mod`, `go.sum` |
| Ruby | bundler | `Gemfile.lock` |
| PHP | composer | `composer.lock` |
| C# | nuget | `packages.lock.json` |
| Dart | pub | `pubspec.lock` |
| R | renv | `renv.lock` |
| Elixir | mix | `mix.lock` |
| Perl | cpan | `cpanfile.snapshot` |
| Swift | SPM | `Package.resolved` |
| Java | gradle/maven | `gradle.lockfile`, `pom.xml` |
| Kotlin | gradle/maven | `gradle.lockfile` |
| Scala | sbt | `build.sbt` |
| Haskell | cabal/stack | `cabal.project.freeze`, `stack.yaml.lock` |

You can view the source code for these parsers in `oss_sustain_guard/dependency_parsers/`.

## Plugin Distribution

### Option 1: PyPI Package

Distribute your parser as a PyPI package:

```toml
# pyproject.toml
[project]
name = "my-parser-plugin"
version = "1.0.0"

[project.entry-points."oss_sustain_guard.dependency_parsers"]
my-parser = "my_parser_plugin:PARSER"
```

Users can install with:
```bash
pip install my-parser-plugin
```

### Option 2: Local Package

For internal use, install locally:

```bash
pip install -e /path/to/my-parser
```

### Option 3: Git Repository

Install directly from Git:

```bash
pip install git+https://github.com/user/my-parser.git
```

## Troubleshooting

### Parser Not Detected

1. **Check entry point registration:**
   ```toml
   [project.entry-points."oss_sustain_guard.dependency_parsers"]
   my-parser = "my_package.my_parser:PARSER"
   ```

2. **Verify package is installed:**
   ```bash
   pip list | grep my-parser
   ```

3. **Check parser name is unique:**
   - Parser names must not conflict with built-in parsers

### Parser Returns None

Common causes:

1. **Lockfile doesn't exist**: Check `lockfile_path.exists()`
2. **Parsing error**: Add try/except blocks
3. **Invalid format**: Validate lockfile structure
4. **Encoding issues**: Use `encoding="utf-8"` when reading files

### Performance Issues

1. **Large lockfiles**: Add size limits
2. **Deep dependency trees**: Limit depth
3. **Complex parsing**: Use streaming parsers for JSON/YAML

## Examples Repository

For more examples, see:
- Built-in parsers: `oss_sustain_guard/dependency_parsers/`
- Test fixtures: `tests/fixtures/`

## Related Guides

- [Custom Resolvers](CUSTOM_RESOLVERS_GUIDE.md) - Map packages to repositories
- [Custom VCS Providers](CUSTOM_VCS_GUIDE.md) - Support new version control systems
- [Custom Metrics](CUSTOM_METRICS_GUIDE.md) - Add new sustainability metrics
