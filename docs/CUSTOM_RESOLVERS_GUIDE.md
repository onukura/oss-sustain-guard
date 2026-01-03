# Custom Resolvers Guide

OSS Sustain Guard supports **custom resolvers through a plugin system**. You can add support for new programming languages or package ecosystems either as built-in resolvers (contributing to the core project) or as external plugins (separate packages).

## 📋 Table of Contents

- [Overview](#overview)
- [Built-in Resolvers](#built-in-resolvers)
- [External Plugin Resolvers](#external-plugin-resolvers)
- [Resolver Development Guide](#resolver-development-guide)
- [Best Practices](#best-practices)
- [Examples](#examples)

## Overview

### Plugin Architecture

OSS Sustain Guard uses a **plugin-based resolver system** with automatic discovery:

1. **Entry Points**: Resolvers are discovered via `[project.entry-points."oss_sustain_guard.resolvers"]`
2. **LanguageResolver**: Each resolver exports a `LanguageResolver` instance
3. **Automatic Loading**: Resolvers are loaded automatically by `load_resolvers()`

### Resolver Types

| Type | Use Case | Distribution |
| ---- | -------- | ------------ |
| **Built-in** | Core language/package ecosystem support | Part of `oss-sustain-guard` package |
| **External Plugin** | Custom/specialized ecosystems | Separate Python packages |

## Built-in Resolvers

Built-in resolvers are part of the OSS Sustain Guard core package and support major programming languages and package ecosystems.

### Supported Ecosystems

| Ecosystem | Registry | Languages |
| --------- | -------- | --------- |
| `python` | PyPI | Python |
| `javascript` | npm | JavaScript, TypeScript |
| `java` | Maven Central | Java, Kotlin, Scala |
| `csharp` | NuGet | C# |
| `go` | Go Modules | Go |
| `rust` | Crates.io | Rust |
| `ruby` | RubyGems | Ruby |
| `php` | Packagist | PHP |
| `swift` | Swift Package Index | Swift |
| `dart` | pub.dev | Dart |
| `elixir` | Hex | Elixir |
| `haskell` | Hackage | Haskell |
| `perl` | CPAN | Perl |
| `r` | CRAN | R |

## External Plugin Resolvers

External plugins allow you to add support for new ecosystems without modifying the core package.

### Installing a Resolver Plugin

```bash
pip install my-custom-resolver-plugin
```

### Creating a Resolver Plugin

#### 1. Create Package Structure

```shell
my_resolver_plugin/
├── pyproject.toml
├── src/
│   └── my_resolver_plugin/
│       ├── __init__.py
│       └── mylang.py
```

#### 2. Implement Resolver

Create `src/my_resolver_plugin/mylang.py`:

```python
"""MyLang package resolver."""

from oss_sustain_guard.repository import RepositoryReference, parse_repository_url
from oss_sustain_guard.resolvers.base import LanguageResolver, PackageInfo


class MyLangResolver(LanguageResolver):
    """Resolver for MyLang packages."""

    @property
    def ecosystem_name(self) -> str:
        return "mylang"

    async def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """
        Resolve MyLang package to repository.

        Args:
            package_name: Package name in MyLang ecosystem

        Returns:
            RepositoryReference or None if not found
        """
        # Implement package registry lookup
        # Return RepositoryReference(platform, owner, repo)
        return None

    async def get_manifest_files(self) -> list[str]:
        """Return manifest file patterns for MyLang."""
        return ["myproject.toml", "mylang.json"]

    async def get_lockfiles(self) -> list[str]:
        """Return lockfile patterns for MyLang."""
        return ["mylang.lock"]

    async def parse_manifest(self, content: str) -> list[PackageInfo]:
        """Parse MyLang manifest file."""
        # Parse manifest and return PackageInfo list
        return []

    async def parse_lockfile(self, content: str) -> list[PackageInfo]:
        """Parse MyLang lockfile."""
        # Parse lockfile and return PackageInfo list
        return []


RESOLVER = MyLangResolver()
```

#### 3. Configure Entry Points

In `pyproject.toml`:

```toml
[project.entry-points."oss_sustain_guard.resolvers"]
mylang = "my_resolver_plugin.mylang:RESOLVER"
```

#### 4. Install and Test

```bash
pip install -e .
oss-guard check mypackage --ecosystem mylang
```

## Resolver Development Guide

### Core Concepts

#### LanguageResolver Interface

All resolvers must inherit from `LanguageResolver`:

```python
from oss_sustain_guard.resolvers.base import LanguageResolver

class MyResolver(LanguageResolver):
    @property
    def ecosystem_name(self) -> str:
        """Return ecosystem identifier (e.g., 'python', 'javascript')."""
        return "myeco"

    async def resolve_repository(self, package_name: str) -> RepositoryReference | None:
        """Resolve package name to RepositoryReference."""
        pass
```

#### RepositoryReference

```python
from oss_sustain_guard.repository import RepositoryReference

# Create reference
ref = RepositoryReference(
    platform="github",  # "github", "gitlab", etc.
    owner="myorg",
    repo="myrepo"
)
```

#### PackageInfo

```python
from oss_sustain_guard.resolvers.base import PackageInfo

# Create package info
pkg = PackageInfo(
    name="mypackage",
    ecosystem="myeco",
    version="1.0.0",
    registry_url="https://registry.example.com/mypackage"
)
```

### Required Methods

#### resolve_repository()

**Purpose**: Map package name to source repository.

**Implementation**:

- Query package registry API
- Extract repository URL from package metadata
- Parse URL to RepositoryReference
- Handle errors gracefully (return None)

**Example**:

```python
async def resolve_repository(self, package_name: str) -> RepositoryReference | None:
    try:
        # Query registry
        response = await client.get(f"https://api.example.com/packages/{package_name}")
        data = response.json()

        # Extract repository URL
        repo_url = data.get("repository", {}).get("url")
        if not repo_url:
            return None

        # Parse to RepositoryReference
        return parse_repository_url(repo_url)
    except Exception:
        return None
```

#### get_manifest_files()

**Purpose**: Return manifest file patterns for ecosystem detection.

**Examples**:

- Python: `["pyproject.toml", "setup.py", "requirements.txt"]`
- JavaScript: `["package.json"]`
- Java: `["pom.xml", "build.gradle", "build.gradle.kts"]`

#### get_lockfiles()

**Purpose**: Return lockfile patterns for dependency resolution.

**Examples**:

- Python: `["poetry.lock", "Pipfile.lock"]`
- JavaScript: `["package-lock.json", "yarn.lock"]`
- Rust: `["Cargo.lock"]`

#### parse_manifest()

**Purpose**: Parse manifest files to extract dependencies.

**Implementation**:

- Parse JSON/TOML/XML as appropriate
- Extract dependency names and versions
- Return list of PackageInfo

#### parse_lockfile()

**Purpose**: Parse lockfiles for exact dependency versions.

**Implementation**:

- Parse lockfile format
- Extract locked dependency versions
- Return list of PackageInfo with exact versions

### Error Handling

- **Network errors**: Return None (resolver will be skipped)
- **Parse errors**: Raise ValueError with descriptive message
- **Missing data**: Return empty lists or None as appropriate

### Async/Await

All resolver methods are async to support:

- HTTP requests to registries
- File I/O operations
- Concurrent processing

## Best Practices

### Registry Integration

1. **Use official APIs**: Prefer official registry APIs over scraping
2. **Handle rate limits**: Implement backoff/retry logic
3. **Cache responses**: Respect registry caching headers
4. **Timeout requests**: Set reasonable timeouts (10 seconds)

### Repository Detection

1. **Multiple URL formats**: Support various repository URL formats
2. **Platform detection**: Correctly identify GitHub, GitLab, Bitbucket, etc.
3. **Fallback parsing**: Use `parse_repository_url()` helper

### Manifest Parsing

1. **Robust parsing**: Handle malformed files gracefully
2. **Version handling**: Support various version specifiers
3. **Dependency types**: Distinguish dev vs runtime dependencies

### Naming Conventions

1. **Ecosystem names**: Use lowercase, no spaces (e.g., `dotnet`, `node`)
2. **Class names**: `{Language}Resolver` (e.g., `DotNetResolver`)
3. **Entry points**: Match ecosystem name

## Examples

### Complete Resolver Example

See built-in resolvers in `oss_sustain_guard/resolvers/` for complete examples:

- `python.py` - PyPI resolver
- `javascript.py` - npm resolver
- `csharp.py` - NuGet resolver

### Testing Your Resolver

```python
import pytest
from oss_sustain_guard.resolvers import get_resolver

def test_my_resolver():
    resolver = get_resolver("mylang")
    assert resolver is not None
    assert resolver.ecosystem_name == "mylang"

@pytest.mark.asyncio
async def test_resolve_repository():
    resolver = get_resolver("mylang")
    ref = await resolver.resolve_repository("mypackage")
    assert ref is not None
    assert ref.platform == "github"
```

### Plugin Package Example

Complete plugin package: <https://github.com/example/my-resolver-plugin>

## Troubleshooting

### Common Issues

**Resolver not found**: Check entry point configuration in `pyproject.toml`

**Import errors**: Ensure all dependencies are installed

**Network timeouts**: Increase timeout or check network connectivity

**Parse errors**: Validate manifest/lockfile formats

### Debug Commands

```bash
# List available resolvers
python -c "from oss_sustain_guard.resolvers import get_all_resolvers; print([r.ecosystem_name for r in get_all_resolvers()])"

# Test resolver loading
python -c "from oss_sustain_guard.resolvers import get_resolver; print(get_resolver('mylang'))"
```

## Contributing

To contribute a built-in resolver:

1. Create `oss_sustain_guard/resolvers/{ecosystem}.py`
2. Add `RESOLVER = {ResolverClass}()`
3. Update `_BUILTIN_MODULES` in `__init__.py`
4. Add entry point in `pyproject.toml`
5. Add tests in `tests/resolvers/test_{ecosystem}.py`
6. Update documentation in `docs/CUSTOM_RESOLVERS_GUIDE.md`
