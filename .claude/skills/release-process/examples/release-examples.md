# Release Process Examples

Quick reference for common release scenarios.

## Scenario 1: Minor Release (New Features)

> Version bumps from 0.14.0 to 0.15.0

```bash
# 1. Prepare
make test && make lint && make doc-build

# 2. Update files
# Edit pyproject.toml: version = "0.15.0"
uv sync
# Edit CHANGELOG.md: add ## v0.15.0 section with features

# 3. Release
git add pyproject.toml uv.lock CHANGELOG.md
git commit -m "chore: release version 0.15.0"
git tag v0.15.0
git push origin v0.15.0

# → Watch: https://github.com/onukura/oss-sustain-guard/actions
# → Copy release notes template from script output to GitHub Releases
```

## Scenario 2: Patch Release (Bug Fix)

> Version bumps from 0.15.0 to 0.15.1

```bash
# Fix is already committed
git log -1  # Verify fix is there

# Update version only
# Edit pyproject.toml: version = "0.15.1"
uv sync
# Edit CHANGELOG.md: add ## v0.15.1 with one-line fix

git add pyproject.toml uv.lock CHANGELOG.md
git commit -m "chore: release version 0.15.1"
git tag v0.15.1
git push origin v0.15.1
```

## Scenario 3: Using release.sh Script

> Automated version and release notes generation

```bash
# Make script executable
chmod +x .claude/skills/release-process/scripts/release.sh

# Run release script
.claude/skills/release-process/scripts/release.sh 0.16.0

# Script will:
# ✅ Run tests and linting
# ✅ Show current CHANGELOG
# ✅ Prompt you to edit CHANGELOG
# ✅ Update pyproject.toml with new version
# ✅ Run uv sync
# ✅ Create commit and tag
# ✅ Generate GitHub Release notes template
# ✅ Push to remote (with confirmation)
```

## GitHub Release Notes Template Output Example

After running the script, you'll see:

```markdown
## What's New in v0.15.0

- Added custom metric system with plugin architecture (entry points)
- Added Dart (pub.dev) package ecosystem support
- Added recursive dependency scanning with --recursive flag
- Fixed cache invalidation when scoring profiles change
- Improved error messages for network timeouts
- Changed default output style to "normal" for better readability

## Installation

pip install oss-sustain-guard==0.15.0

## Verification

To verify the installation:

os4g --version
os4g check requests
```

👉 **Copy this template to GitHub Releases page**

## Verifying a Release

After the GitHub Actions pipeline completes:

```bash
# Install from PyPI
pip install oss-sustain-guard==X.Y.Z

# Verify
os4g --version
os4g check requests -v
```

## If Something Goes Wrong

**Tag was created but pipeline didn't start?**
```bash
git tag -d v0.15.0
git push origin :v0.15.0
# Fix the issue, then recreate tag
git tag v0.15.0
git push origin v0.15.0
```

**Need to undo before PyPI publishes?**
```bash
# Delete tag immediately (before PyPI publishes - takes 5-10 min)
git tag -d v0.15.0
git push origin :v0.15.0
```

**Already published with wrong version?**
```bash
# Release a patch version with fix
# Version will be v0.15.1
# Old version remains on PyPI but new version is default
```

See [workflow-details.md](../references/workflow-details.md) for more troubleshooting.
