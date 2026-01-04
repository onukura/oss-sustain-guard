# Pre-Commit Integration (Quick Guide)

OSS Sustain Guard can be used as a pre-commit hook to automatically check the sustainability of your dependencies before every commit.

## Quick Start

### 1. Install pre-commit

```shell
pip install pre-commit
```

### 2. Add a `.pre-commit-config.yaml` to your project root

```yaml
repos:
  - repo: https://github.com/onukura/oss-sustain-guard
    rev: v0.18.0
    hooks:
      - id: oss-sustain-guard
        args: [-o, compact]
        verbose: true
```

### 3. Install the hook

```bash
pre-commit install
```

### 4. Commit Changes

Now, whenever you commit changes to dependency files, OSS Sustain Guard will automatically scan your dependencies

## FAQ

- **Do I need a token?**: Yes. `GITHUB_TOKEN` covers most repos; `GITLAB_TOKEN` is only needed for gitlab.com sources:

```bash
export GITHUB_TOKEN=your_github_token
```

```bash
export GITLAB_TOKEN=your_gitlab_token
```

- **Does it support other languages?**: Yes! You can check npm, Rust, Go, Ruby, PHP, etc. (e.g. `os4g check npm:react`)
- **How do I run the check manually?**: Run: `pre-commit run oss-sustain-guard --all-files`

For more details or troubleshooting, see the [official pre-commit docs](https://pre-commit.com/) or [Getting Started](./GETTING_STARTED.md).
