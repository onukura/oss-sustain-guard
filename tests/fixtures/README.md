# Test Fixtures Documentation

This directory contains real-world dependency files from popular open-source projects, used as fixtures for integration testing.

## Purpose

These fixtures validate that OSS Sustain Guard correctly:
- Parses package dependency files from various ecosystems
- Handles multi-language project structures
- Processes real package names and versions

## Fixture Files

### JavaScript/npm

- **package.json** - Node.js project with React, Express, TypeScript, and common dependencies

### Python

- **requirements.txt** - Django project with REST framework, Celery, and testing tools
- **pyproject.toml** - Poetry project with FastAPI, SQLAlchemy, and Pydantic

### Rust

- **Cargo.toml** - Tokio-based async application with Actix-web and SQLx

### Java

- **pom.xml** - Spring Boot application with Maven dependencies

### PHP

- **composer.json** - Laravel project with Guzzle, Monolog, and Doctrine

### Ruby

- **Gemfile** - Rails application with Sidekiq, Devise, and RSpec

### C#/.NET

- **packages.config** - .NET project with Newtonsoft.Json, Entity Framework, and Serilog

### Go

- **go.mod** - Go application with Gin, GORM, Viper, and Cobra

## Usage in Tests

The `test_fixtures_integration.py` file demonstrates how to:

1. **Parse dependency files** - Read and extract package names from each format
2. **Mock analysis results** - Create `AnalysisResult` objects with proper `Metric` data
3. **Test CLI commands** - Invoke `oss-guard check <package>` with mocked backend
4. **Cross-language validation** - Verify support for all 8 programming languages

## Example Test Pattern

```python
def test_parse_and_check_package():
    # Load fixture
    with open(FIXTURES_DIR / "package.json") as f:
        data = json.load(f)

    # Extract packages
    packages = list(data["dependencies"].keys())

    # Mock and test
    with patch("oss_sustain_guard.cli.analyze_package") as mock:
        mock.return_value = AnalysisResult(
            repo_url="https://github.com/example/repo",
            total_score=80,
            metrics=[Metric(...)],
        )
        result = runner.invoke(app, ["check", f"npm:{package}"])
        assert result.exit_code == 0
```

## Adding New Fixtures

To add a new language or update existing fixtures:

1. Create/update the dependency file in `tests/fixtures/`
2. Use real package names from popular projects
3. Include both production and dev dependencies
4. Add corresponding test class in `test_fixtures_integration.py`

## Benefits

- **Realistic Testing** - Use actual dependency file formats
- **Documentation** - Fixtures serve as examples of supported formats
- **Regression Prevention** - Catch parsing issues early
- **Multi-language Validation** - Ensure all resolvers work correctly

