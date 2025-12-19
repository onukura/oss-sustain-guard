# Community Contributions

This directory contains community-contributed package analysis data.

## How to Contribute

1. **Analyze packages locally** using your own GitHub token
2. **Export your results** using `oss-guard export <ecosystem>`
3. **Validate your contribution** using `oss-guard validate-contribution <file>`
4. **Submit a Pull Request** with your contribution file in this directory

See [docs/COMMUNITY_CONTRIBUTION_GUIDE.md](../../docs/COMMUNITY_CONTRIBUTION_GUIDE.md) for detailed instructions.

## File Naming Convention

Contribution files should follow this naming pattern:

```
contribution-{ecosystem}-{timestamp}.json
```

Examples:
- `contribution-python-20251219-210000.json`
- `contribution-javascript-20251219-210530.json`
- `contribution-rust-20251219-211045.json`

## Validation

All contributions are automatically validated by CI to ensure:

- ✓ Valid JSON structure
- ✓ Correct schema version
- ✓ Required fields present
- ✓ No security issues (tokens, local paths)
- ✓ Package data integrity

## Integration

Approved contributions are:

1. Merged to the `main` branch
2. Integrated into ecosystem databases during weekly builds
3. Made available to all users

## Questions?

- Read the [Contribution Guide](../../docs/COMMUNITY_CONTRIBUTION_GUIDE.md)
- Check the [Architecture](../../docs/COMMUNITY_CONTRIBUTION_ARCHITECTURE.md)
- Open an [Issue](https://github.com/onukura/oss-sustain-guard/issues)

Thank you for contributing to the OSS Sustain Guard community! 🙏
