---
name: releasing-versions
description: Interactive release workflow for OSS Sustain Guard with version updates, PyPI publishing, and GitHub release notes. Use when ready to release a new version to production.
---

# Release Process - Quick Start

> **Quick guide to release a new version. For detailed info, see [workflow-details.md](../references/workflow-details.md).**

## Quick Release Checklist

```bash
# 1. Verify local setup
make test && make lint && make doc-build

# 2. Update version
# - Edit pyproject.toml: change version
# - Run: uv sync
# - Edit CHANGELOG.md: add new section with changes

# 3. Commit and tag
git add pyproject.toml uv.lock CHANGELOG.md
git commit -m "chore: release version X.Y.Z"
git tag vX.Y.Z
git push origin vX.Y.Z

# 4. Watch pipeline
# → Go to: https://github.com/onukura/oss-sustain-guard/actions
# → Wait for all jobs to succeed

# 5. Get release notes template
# → See output after push
```

## The 5 Steps

### 1️⃣ Prepare & Test

Make sure everything is ready:

```bash
git fetch upstream
make test          # All tests pass?
make lint          # Code clean?
make doc-build     # Docs build?
```

### 2️⃣ Decide Version

Use [Semantic Versioning](https://semver.org/):
- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.15.0): New features
- **PATCH** (0.14.1): Bug fixes

### 3️⃣ Update Files

**pyproject.toml** - Change version:

```toml
version = "0.15.0"
```

**Then sync lock file:**

```bash
uv sync
```

**CHANGELOG.md** - Add at top:

```markdown
## v0.15.0 - 2026-01-20

- Added: new feature
- Fixed: bug description
- Improved: enhancement
```

### 4️⃣ Commit & Tag

```bash
git add pyproject.toml uv.lock CHANGELOG.md
git commit -m "chore: release version 0.15.0"
git tag v0.15.0
git push origin v0.15.0
```

### 5️⃣ Watch & Verify

The publish workflow starts automatically:

```
GitHub Actions → build → publish-to-pypi → github-release
```

**Check:**

- [ ] All jobs pass in Actions
- [ ] New version on PyPI
- [ ] Release appears on GitHub Releases
- [ ] Can install: `pip install oss-sustain-guard==0.15.0`

## What Happens Automatically

✅ Build Python package
✅ Upload to PyPI (Trusted Publishing)
✅ Sign artifacts with Sigstore
✅ Create GitHub Release
✅ Generate release notes template (see output)

## GitHub Release Notes Template

After release completes, you'll see a template ready to copy/paste to your GitHub Release description.

> The script will provide this automatically when you run `release.sh`

## Need More Details?

See bundled references:

- [workflow-details.md](../references/workflow-details.md) - Detailed technical info
- [release-examples.md](../examples/release-examples.md) - Step-by-step examples & troubleshooting

## Common Questions

**Q: What if tests fail?**
A: Fix the issue and commit before running the release commands.

**Q: How to undo a release?**
A: Delete the tag (`git tag -d vX.Y.Z && git push origin :vX.Y.Z`) before PyPI publishes.

**Q: Tag created but pipeline didn't start?**
A: Verify tag format is `vX.Y.Z` (must start with 'v'). See troubleshooting docs.

**Q: Want to see release notes first?**
A: Use `release.sh` script - it shows release notes before pushing to remote.
