# Custom VCS Providers Guide

OSS Sustain Guard supports **custom VCS providers through a plugin system**. You can add support for new version control platforms (GitLab, Bitbucket, Gitea, etc.) either as built-in providers (contributing to the core project) or as external plugins (separate packages).

## 📋 Table of Contents

- [Overview](#overview)
- [Built-in VCS Providers](#built-in-vcs-providers)
- [External Plugin Providers](#external-plugin-providers)
- [VCS Provider Development Guide](#vcs-provider-development-guide)
- [Best Practices](#best-practices)
- [Examples](#examples)

## Overview

### Plugin Architecture

OSS Sustain Guard uses a **plugin-based VCS provider system** with automatic discovery:

1. **Entry Points**: Providers are discovered via `[project.entry-points."oss_sustain_guard.vcs"]`
2. **BaseVCSProvider**: Each provider exports a `BaseVCSProvider` subclass
3. **Automatic Loading**: Providers are loaded automatically by `load_providers()`

### Provider Types

| Type | Use Case | Distribution |
| ------ | ---------- | -------------- |
| **Built-in** | Core VCS platform support | Part of `oss-sustain-guard` package |
| **External Plugin** | Custom/specialized platforms | Separate Python packages |

## Built-in VCS Providers

Built-in providers are part of the OSS Sustain Guard core package.

### Supported Platforms

| Platform | API | Authentication |
| -------- | --- | -------------- |
| `github` | GraphQL API | Personal Access Token |
| `gitlab` | REST API | Personal Access Token |

## External Plugin Providers

External plugins allow you to add support for new VCS platforms without modifying the core package.

### Installing a VCS Provider Plugin

```bash
pip install my-custom-vcs-plugin
```

### Creating a VCS Provider Plugin

#### 1. Create Package Structure

```shell
my_vcs_plugin/
├── pyproject.toml
├── src/
│   └── my_vcs_plugin/
│       ├── __init__.py
│       └── myplatform.py
```

#### 2. Implement VCS Provider

Create `src/my_vcs_plugin/myplatform.py`:

```python
"""MyPlatform VCS provider."""

import os
from typing import Any

import httpx

from oss_sustain_guard.vcs.base import BaseVCSProvider, VCSRepositoryData


class MyPlatformProvider(BaseVCSProvider):
    """VCS provider for MyPlatform."""

    def __init__(self, token: str | None = None, host: str = "https://myplatform.com"):
        """
        Initialize MyPlatform provider.

        Args:
            token: API token for authentication
            host: MyPlatform instance URL
        """
        self.token = token or os.getenv("MYPLATFORM_TOKEN")
        self.host = host.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.host,
            headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
            timeout=30.0
        )

    async def get_repository_data(self, owner: str, repo: str) -> VCSRepositoryData:
        """
        Fetch repository data from MyPlatform.

        Args:
            owner: Repository owner/organization
            repo: Repository name

        Returns:
            Normalized VCSRepositoryData
        """
        # Implement API calls to fetch repository data
        # Transform to VCSRepositoryData structure

        # Example structure (simplified)
        return VCSRepositoryData(
            is_archived=False,
            pushed_at="2024-01-01T00:00:00Z",
            owner_type="Organization",
            owner_login=owner,
            owner_name=owner,
            description="Repository description",
            homepage_url=None,
            topics=[],
            readme_size=1024,
            contributing_file_size=None,
            default_branch="main",
            watchers_count=100,
            open_issues_count=5,
            language="Python",
            commits=[],  # List of commit dicts
            total_commits=150,
            merged_prs=[],  # List of merged PR dicts
            closed_prs=[],  # List of closed PR dicts
            total_merged_prs=45,
            releases=[],  # List of release dicts
            open_issues=[],  # List of open issue dicts
            closed_issues=[],  # List of closed issue dicts
            total_closed_issues=200,
            vulnerability_alerts=None,
            has_security_policy=True,
            code_of_conduct={"name": "Contributor Covenant", "url": "..."},
            license_info={"name": "MIT", "spdxId": "MIT", "url": "..."},
            has_wiki=True,
            has_issues=True,
            has_discussions=False,
            funding_links=[],
            forks=[],  # List of fork dicts
            total_forks=10,
            ci_status=None,
            sample_counts={"commits": 100, "issues": 20, "prs": 50},
            raw_data=None
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()


PROVIDER = MyPlatformProvider
```

#### 3. Configure Entry Points

In `pyproject.toml`:

```toml
[project.entry-points."oss_sustain_guard.vcs"]
myplatform = "my_vcs_plugin.myplatform:PROVIDER"
```

#### 4. Install and Test

```bash
pip install -e .
oss-guard check mypackage --platform myplatform
```

## VCS Provider Development Guide

### Core Concepts

#### BaseVCSProvider Interface

All providers must inherit from `BaseVCSProvider`:

```python
from oss_sustain_guard.vcs.base import BaseVCSProvider, VCSRepositoryData

class MyProvider(BaseVCSProvider):
    async def get_repository_data(self, owner: str, repo: str) -> VCSRepositoryData:
        """Fetch and normalize repository data."""
        pass
```

#### VCSRepositoryData Structure

The `VCSRepositoryData` NamedTuple contains all repository information:

```python
@dataclass
class VCSRepositoryData:
    # Basic repository info
    is_archived: bool
    pushed_at: str | None
    owner_type: str  # "Organization", "User", or "Group"
    owner_login: str
    owner_name: str | None

    # Repository metadata
    star_count: int
    description: str | None
    homepage_url: str | None
    topics: list[str]
    readme_size: int | None
    contributing_file_size: int | None
    default_branch: str | None
    watchers_count: int
    open_issues_count: int
    language: str | None

    # Commit data
    commits: list[dict[str, Any]]
    total_commits: int

    # Pull/Merge Request data
    merged_prs: list[dict[str, Any]]
    closed_prs: list[dict[str, Any]]
    total_merged_prs: int

    # Release data
    releases: list[dict[str, Any]]

    # Issue data
    open_issues: list[dict[str, Any]]
    closed_issues: list[dict[str, Any]]
    total_closed_issues: int

    # Security & compliance
    vulnerability_alerts: list[dict[str, Any]] | None
    has_security_policy: bool
    code_of_conduct: dict[str, str] | None
    license_info: dict[str, str] | None

    # Project features
    has_wiki: bool
    has_issues: bool
    has_discussions: bool

    # Funding information
    funding_links: list[dict[str, str]]

    # Fork data
    forks: list[dict[str, Any]]
    total_forks: int

    # CI/CD status
    ci_status: dict[str, str] | None

    # Metadata
    sample_counts: dict[str, int]
    raw_data: dict[str, Any] | None
```

### Required Methods

#### get_repository_data()

**Purpose**: Fetch comprehensive repository data and normalize to `VCSRepositoryData`.

**Implementation**:

- Authenticate with VCS platform API
- Make multiple API calls to gather all required data
- Transform platform-specific data to normalized format
- Handle pagination for large datasets
- Implement sampling for performance

**Key Data Sources**:

- Repository metadata (description, topics, etc.)
- Commit history (recent commits with author/date)
- Issue/PR data (open/closed counts, recent items)
- Release information
- Security policy and vulnerability alerts
- License and code of conduct information

### Data Sampling Strategy

For performance, implement sampling:

```python
SAMPLE_LIMITS = {
    "commits": 100,
    "issues": 20,
    "prs": 50,
    "releases": 10,
    "forks": 20,
}

# Sample recent items, but provide total counts
commits = await fetch_recent_commits(owner, repo, limit=SAMPLE_LIMITS["commits"])
total_commits = await fetch_commit_count(owner, repo)
```

### Authentication

Support multiple auth methods:

```python
def __init__(self, token: str | None = None, host: str = "https://api.example.com"):
    self.token = token or os.getenv("EXAMPLE_TOKEN")
    self.host = host
    self.client = httpx.AsyncClient(
        base_url=self.host,
        headers=self._get_auth_headers(),
        timeout=30.0
    )

def _get_auth_headers(self) -> dict[str, str]:
    if self.token:
        return {"Authorization": f"Bearer {self.token}"}
    return {}
```

### Error Handling

- **API errors**: Raise descriptive exceptions
- **Rate limits**: Implement exponential backoff
- **Missing data**: Use None or empty collections
- **Network issues**: Timeout and retry logic

### Async Context Management

Implement async context manager for proper resource cleanup:

```python
async def __aenter__(self):
    return self

async def __aexit__(self, exc_type, exc_val, exc_tb):
    await self.client.aclose()
```

## Best Practices

### API Integration

1. **Official APIs**: Use official REST/GraphQL APIs when available
2. **Rate limiting**: Respect API rate limits with backoff
3. **Caching**: Cache responses appropriately
4. **Timeouts**: Set reasonable request timeouts

### Data Normalization

1. **Consistent formats**: Normalize dates to ISO 8601
2. **Standard field names**: Map platform-specific fields to standard names
3. **Null handling**: Use None for missing optional data
4. **Type safety**: Ensure correct types for all fields

### Performance

1. **Concurrent requests**: Use asyncio for parallel API calls
2. **Pagination**: Handle paginated responses efficiently
3. **Sampling**: Sample large datasets intelligently
4. **Caching**: Cache expensive operations

### Security

1. **Token handling**: Never log or expose tokens
2. **HTTPS only**: Always use HTTPS for API calls
3. **Permission scope**: Request minimal required permissions

## Examples

### Complete Provider Example

See built-in providers for complete examples:

- `github.py` - GitHub GraphQL provider
- `gitlab.py` - GitLab REST provider

### Testing Your Provider

```python
import pytest
from oss_sustain_guard.vcs import get_vcs_provider

@pytest.mark.asyncio
async def test_my_provider():
    async with get_vcs_provider("myplatform", token="test_token") as provider:
        data = await provider.get_repository_data("owner", "repo")
        assert data.owner_login == "owner"
        assert isinstance(data.star_count, int)

@pytest.mark.asyncio
async def test_provider_error_handling():
    # Test error conditions
    with pytest.raises(ValueError):
        get_vcs_provider("myplatform")  # No token
```

### Plugin Package Example

Complete plugin package: <https://github.com/example/my-vcs-plugin>

## Troubleshooting

### Common Issues

**Provider not found**: Check entry point configuration

**Authentication failed**: Verify token and permissions

**API timeouts**: Check network connectivity and increase timeouts

**Data format errors**: Validate API response parsing

### Debug Commands

```bash
# List available providers
python -c "from oss_sustain_guard.vcs import list_supported_platforms; print(list_supported_platforms())"

# Test provider loading
python -c "from oss_sustain_guard.vcs import get_vcs_provider; print(get_vcs_provider('myplatform'))"
```

## Contributing

To contribute a built-in VCS provider:

1. Create `oss_sustain_guard/vcs/{platform}.py`
2. Add `PROVIDER = {ProviderClass}`
3. Update `_BUILTIN_PROVIDERS` in `__init__.py`
4. Add entry point in `pyproject.toml`
5. Add tests in `tests/vcs/test_{platform}.py`
6. Update documentation in `docs/CUSTOM_VCS_GUIDE.md`
