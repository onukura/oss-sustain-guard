# Release Process Reference

## Contents

- [GitHub Actions Workflow](#github-actions-workflow)
- [Semantic Versioning Guide](#semantic-versioning-guide)
- [Conventional Commits](#conventional-commits)
- [PyPI Trusted Publishing](#pypi-trusted-publishing-openid-connect)
- [Lock File Management](#lock-file-management)
- [Git Tag Management](#git-tag-management)
- [CHANGELOG Format](#changelog-format)
- [Checklist](#checklist)
- [FAQ](#faq)

## GitHub Actions Workflow

### publish.yml Structure

```yaml
name: Publish Python 🐍 distribution 📦 to PyPI and TestPyPI

on:
  push:
    branches:
      - main
    tags:
      - 'v*'  # Triggers on tags like v0.15.0
```

**Trigger Conditions**:
- Normal push to `main` branch: Build only (no PyPI publishing)
- Tag push matching `v*` pattern: Build + PyPI publishing + GitHub Release creation

### Job Dependencies

```
build (always runs)
  ↓
publish-to-pypi (tag push only, depends on build)
  ↓
github-release (tag push only, depends on publish-to-pypi)
```

## Semantic Versioning Guide

### Version Format: MAJOR.MINOR.PATCH

- **MAJOR (1.0.0)**: Breaking changes
  - Fundamental API changes
  - Users must update their code
  - Example: Complete rewrite of metric calculation logic

- **MINOR (0.15.0)**: Backward-compatible new features
  - New metrics added
  - New ecosystem support
  - New CLI options
  - Existing code continues to work

- **PATCH (0.14.1)**: Backward-compatible bug fixes
  - Cache TTL validation bug fix
  - Minor calculation adjustments
  - Documentation fixes

### Examples

```
v0.13.0 → v0.14.0  MINOR: New features (profiles, JSON/HTML export)
v0.14.0 → v0.14.1  PATCH: Bug fixes (cache handling)
v0.14.1 → v1.0.0   MAJOR: API breaking changes
```

## Conventional Commits

OSS Sustain Guard uses Conventional Commits for all commits:

### Commit Types

- **feat**: New feature
  ```bash
  git commit -m "feat: add JSON report export"
  ```

- **fix**: Bug fix
  ```bash
  git commit -m "fix: resolve cache TTL validation issue"
  ```

- **docs**: Documentation changes
  ```bash
  git commit -m "docs: update README with examples"
  ```

- **test**: Test additions/modifications
  ```bash
  git commit -m "test: add coverage for JavaScript resolver"
  ```

- **refactor**: Code improvements (no feature changes)
  ```bash
  git commit -m "refactor: simplify metric calculation"
  ```

- **perf**: Performance improvements
  ```bash
  git commit -m "perf: optimize GraphQL query batching"
  ```

- **chore**: Maintenance (builds, dependencies, etc.)
  ```bash
  git commit -m "chore: release version 0.15.0"
  ```

### Release Commits

Release commits always use `chore` type with format:

```bash
git commit -m "chore: release version X.Y.Z"
```

## PyPI Trusted Publishing (OpenID Connect)

Current setup uses OpenID Connect-based authentication:

### Benefits

- **Security**: No need to store PyPI API tokens as secrets
- **Simplicity**: Only `id-token: write` permission needed
- **Short-lived**: GitHub Actions tokens automatically expire

### Configuration Location

- GitHub: Settings > Environments > pypi
- PyPI: https://pypi.org/manage/account/publishing/

### Usage in GitHub Actions

```yaml
environment:
  name: pypi
  url: https://pypi.org/p/oss-sustain-guard
permissions:
  id-token: write  # Required for Trusted Publishing

- name: Publish distribution 📦 to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
```

## Lock File Management

### Why Update Lock Files?

The `uv.lock` file (UV package manager's lock file) must be synchronized with `pyproject.toml` whenever the version changes. This ensures:

1. **Version consistency**: Lock file reflects the new version
2. **Build reproducibility**: Dependencies are locked to exact versions
3. **CI/CD consistency**: Automated workflows use the same dependency versions

### Updating uv.lock

After updating the version in `pyproject.toml`, run:

```bash
# Synchronize lock file with pyproject.toml
uv sync

# Output example:
# Resolved 42 packages in 0.23s
# Prepared 42 packages in 0.15s
# Installed 42 packages in 0.28s
```

### What Gets Updated in uv.lock

- Version metadata for the project
- Hash values reflecting version changes
- Timestamp of synchronization
- Dependency resolution metadata

### Commit Lock File Changes

Both files must be committed together:

```bash
git add pyproject.toml uv.lock CHANGELOG.md
git commit -m "chore: release version 0.15.0"
```

**Never** commit one without the other, as this creates inconsistency between the source version and the locked dependencies.

## Git Tag Management

### Creating Tags

**Lightweight tag** (not recommended):
```bash
git tag v0.15.0
```

**Signed tag** (recommended):
```bash
git tag -s -m "Release version 0.15.0" v0.15.0
```

- `-s`: Add GPG signature
- `-m`: Tag message

### Verifying Tags

```bash
# List all tags
git tag -l

# List tags matching pattern
git tag -l "v*"

# Show tag details
git show v0.15.0
```

### Deleting Tags

```bash
# Delete local tag
git tag -d v0.15.0

# Delete remote tag
git push origin :v0.15.0
```

## CHANGELOG Format

### Section Structure

```markdown
## vX.Y.Z - YYYY-MM-DD

- **Added**: New features (newly added functionality)
- **Fixed**: Bug fixes (what was fixed)
- **Changed**: Changes (modifications to existing features)
- **Improved**: Improvements (enhancements to existing features)
- **Removed**: Removed features (deleted functionality)
- **Deprecated**: Deprecation warnings (deprecated items)
```

### Example

```markdown
## v0.15.0 - 2026-01-15

- Added support for Dart package ecosystem (pub.dev)
- Added custom metric system with entry point discovery
- Fixed cache invalidation for profile changes
- Improved error messages for network failures
- Changed default scoring profile to "balanced"
- Removed legacy metric schema migration code
```

### Format Rules

1. **Date format**: ISO 8601 (YYYY-MM-DD)
2. **Version format**: v{MAJOR}.{MINOR}.{PATCH}
3. **Description**: Concise, user-focused language in active voice
4. **Order**: Newest versions at the top

## Checklist

### Before Release

- [ ] No uncommitted important changes (`git log`)
- [ ] `main` branch is up to date (`git fetch upstream`)
- [ ] `make test` passes
- [ ] `make lint` has no errors
- [ ] `make doc-build` succeeds

### During Release

- [ ] pyproject.toml version updated
- [ ] `uv sync` executed to update uv.lock
- [ ] CHANGELOG.md created/updated
- [ ] All three files committed: pyproject.toml, uv.lock, CHANGELOG.md
- [ ] Commit message format: `chore: release version X.Y.Z`
- [ ] Tag format: `vX.Y.Z`
- [ ] Tag pushed to remote

### After Release

- [ ] GitHub Actions successful (https://github.com/onukura/oss-sustain-guard/actions)
- [ ] New version on PyPI (https://pypi.org/project/oss-sustain-guard/)
- [ ] New release on GitHub Releases
- [ ] Sigstore signature files included
- [ ] `pip install oss-sustain-guard==X.Y.Z` works

## FAQ

### Q: Pipeline won't start

**A**: Verify tag format matches `v*` pattern:

```bash
# ❌ Won't start
git tag 0.15.0
git tag release-0.15.0

# ✅ Will start
git tag v0.15.0
```

### Q: PyPI authorization error

**A**: Verify Trusted Publishing configuration:

1. Check GitHub Repository Settings > Environments > pypi
2. Check PyPI Publishing tab for registered GitHub trusted publisher
3. Verify `id-token: write` permission in publish.yml

### Q: Need to recreate tag

**A**: Delete from both local and remote, then recreate:

```bash
git tag -d v0.15.0
git push origin :v0.15.0
git tag -s -m "Release version 0.15.0" v0.15.0
git push origin v0.15.0
```

### Q: Want to add changes after release

**A**: Create new release or patch version:

- **Small fixes**: Patch release (v0.15.1)
- **New features**: Minor release (v0.16.0)
- **Major changes**: Major release (v1.0.0)

## Reference Links

- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
- [Sigstore Python](https://sigstore.dev/)
- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [GitHub CLI Release Creation](https://cli.github.com/manual/gh_release_create)

## GitHub Actions Workflow

### publish.yml Structure

```yaml
name: Publish Python 🐍 distribution 📦 to PyPI and TestPyPI

on:
  push:
    branches:
      - main
    tags:
      - 'v*'  # Triggers on tags like v0.15.0
```

**Trigger Conditions**:
- Normal push to `main` branch: Build only (no PyPI publishing)
- Tag push matching `v*` pattern: Build + PyPI publishing + GitHub Release creation

### Job Dependencies

```
build (always runs)
  ↓
publish-to-pypi (tag push only, depends on build)
  ↓
github-release (tag push only, depends on publish-to-pypi)
```

## Semantic Versioning Guide

### Version Format: MAJOR.MINOR.PATCH

- **MAJOR (1.0.0)**: Breaking changes
  - Fundamental API changes
  - Users must update their code
  - Example: Complete rewrite of metric calculation logic

- **MINOR (0.15.0)**: Backward-compatible new features
  - New metrics added
  - New ecosystem support
  - New CLI options
  - Existing code continues to work

- **PATCH (0.14.1)**: Backward-compatible bug fixes
  - Cache TTL validation bug fix
  - Minor calculation adjustments
  - Documentation fixes

### Examples

```
v0.13.0 → v0.14.0  MINOR: New features (profiles, JSON/HTML export)
v0.14.0 → v0.14.1  PATCH: Bug fixes (cache handling)
v0.14.1 → v1.0.0   MAJOR: API breaking changes
```

## Conventional Commits

OSS Sustain Guard uses Conventional Commits for all commits:

### Commit Types

- **feat**: New feature
  ```bash
  git commit -m "feat: add JSON report export"
  ```

- **fix**: Bug fix
  ```bash
  git commit -m "fix: resolve cache TTL validation issue"
  ```

- **docs**: Documentation changes
  ```bash
  git commit -m "docs: update README with examples"
  ```

- **test**: Test additions/modifications
  ```bash
  git commit -m "test: add coverage for JavaScript resolver"
  ```

- **refactor**: Code improvements (no feature changes)
  ```bash
  git commit -m "refactor: simplify metric calculation"
  ```

- **perf**: Performance improvements
  ```bash
  git commit -m "perf: optimize GraphQL query batching"
  ```

- **chore**: Maintenance (builds, dependencies, etc.)
  ```bash
  git commit -m "chore: release version 0.15.0"
  ```

### Release Commits

Release commits always use `chore` type with format:

```bash
git commit -m "chore: release version X.Y.Z"
```

## PyPI Trusted Publishing (OpenID Connect)

Current setup uses OpenID Connect-based authentication:

### Benefits

- **Security**: No need to store PyPI API tokens as secrets
- **Simplicity**: Only `id-token: write` permission needed
- **Short-lived**: GitHub Actions tokens automatically expire

### Configuration Location

- GitHub: Settings > Environments > pypi
- PyPI: https://pypi.org/manage/account/publishing/

### Usage in GitHub Actions

```yaml
environment:
  name: pypi
  url: https://pypi.org/p/oss-sustain-guard
permissions:
  id-token: write  # Required for Trusted Publishing

- name: Publish distribution 📦 to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
```

## Git Tag Management

### Creating Tags

**Lightweight tag** (not recommended):
```bash
git tag v0.15.0
```

**Signed tag** (recommended):
```bash
git tag -s -m "Release version 0.15.0" v0.15.0
```

- `-s`: Add GPG signature
- `-m`: Tag message

### Verifying Tags

```bash
# List all tags
git tag -l

# List tags matching pattern
git tag -l "v*"

# Show tag details
git show v0.15.0
```

### Deleting Tags

```bash
# Delete local tag
git tag -d v0.15.0

# Delete remote tag
git push origin :v0.15.0
```

## CHANGELOG Format

### Section Structure

```markdown
## vX.Y.Z - YYYY-MM-DD

- **Added**: New features (newly added functionality)
- **Fixed**: Bug fixes (what was fixed)
- **Changed**: Changes (modifications to existing features)
- **Improved**: Improvements (enhancements to existing features)
- **Removed**: Removed features (deleted functionality)
- **Deprecated**: Deprecation warnings (deprecated items)
```

### Example

```markdown
## v0.15.0 - 2026-01-15

- Added support for Dart package ecosystem (pub.dev)
- Added custom metric system with entry point discovery
- Fixed cache invalidation for profile changes
- Improved error messages for network failures
- Changed default scoring profile to "balanced"
- Removed legacy metric schema migration code
```

### Format Rules

1. **Date format**: ISO 8601 (YYYY-MM-DD)
2. **Version format**: v{MAJOR}.{MINOR}.{PATCH}
3. **Description**: Concise, user-focused language in active voice
4. **Order**: Newest versions at the top

## Checklist

### Before Release

- [ ] No uncommitted important changes (`git log`)
- [ ] `main` branch is up to date (`git fetch upstream`)
- [ ] `make test` passes
- [ ] `make lint` has no errors
- [ ] `make doc-build` succeeds

### During Release

- [ ] pyproject.toml version updated
- [ ] `uv sync` executed to update uv.lock
- [ ] CHANGELOG.md created/updated
- [ ] All three files committed: pyproject.toml, uv.lock, CHANGELOG.md
- [ ] Commit message format: `chore: release version X.Y.Z`
- [ ] Tag format: `vX.Y.Z`
- [ ] Tag pushed to remote

### After Release

- [ ] GitHub Actions successful (https://github.com/onukura/oss-sustain-guard/actions)
- [ ] New version on PyPI (https://pypi.org/project/oss-sustain-guard/)
- [ ] New release on GitHub Releases
- [ ] Sigstore signature files included
- [ ] `pip install oss-sustain-guard==X.Y.Z` works

## FAQ

### Q: Pipeline won't start

**A**: Verify tag format matches `v*` pattern:

```bash
# ❌ Won't start
git tag 0.15.0
git tag release-0.15.0

# ✅ Will start
git tag v0.15.0
```

### Q: PyPI authorization error

**A**: Verify Trusted Publishing configuration:

1. Check GitHub Repository Settings > Environments > pypi
2. Check PyPI Publishing tab for registered GitHub trusted publisher
3. Verify `id-token: write` in publish.yml

### Q: Need to recreate tag

**A**: Delete from both local and remote, then recreate:

```bash
git tag -d v0.15.0
git push origin :v0.15.0
git tag -s -m "Release version 0.15.0" v0.15.0
git push origin v0.15.0
```

### Q: Want to add changes after release

**A**: Create new release or patch version:

- **Small fixes**: Patch release (v0.15.1)
- **New features**: Minor release (v0.16.0)
- **Major changes**: Major release (v1.0.0)

## Reference Links

- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
- [Sigstore Python](https://sigstore.dev/)
- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [GitHub CLI Release Creation](https://cli.github.com/manual/gh_release_create)
