# Changelog

All notable changes to OSS Sustain Guard are documented in this file.

## Unreleased

## v0.23.1 - 2026-01-08

### Improved

- **Terminal tree visualization**: Removed direct dependency marker from tree output to reduce visual clutter and focus on health status indicators
- **Dependency deduplication**: Eliminated redundant platform-specific binary packages from dependency graphs, retaining only a single representative for each unique codebase while preserving functionally distinct packages from the same repository, resulting in cleaner and more accurate dependency reporting

### Fixed

- **Dependency analysis optimization**: Removed unused visualization import from dependency analysis to streamline codebase

## v0.23.0 - 2026-01-08

### Added

- **Ruby (Bundler) support for dependency tracing**: Extended `trace` command to analyze Ruby gem dependencies using Bundler, enabling comprehensive dependency tree visualization for Ruby projects alongside existing Python, JavaScript, and Rust support
- **Rust (Cargo) support for dependency tracing**: Added full Rust package manager integration for the `trace` command to visualize and analyze Cargo dependencies with performance optimization through deduplication
- **Package manager tool selection option**: New `--tool` parameter for `trace` command to explicitly specify external package manager tools (e.g., `uv`, `npm`, `pnpm`, `bun`), improving flexibility and control for users with multiple tooling environments
- **Centralized tool version configuration**: Moved language tool versions from individual fixture files to central `mise.toml` configuration, simplifying management and ensuring consistency across test environments

### Improved

- **Dependency tracing performance**: Eliminated duplicate repository analysis in trace command by deduplicating resolved repositories, significantly reducing API calls and "Analyzing..." messages when different package names resolve to the same GitHub repository
- **Terminal UI simplification**: Removed HTML/JSON output support from `trace` command to focus on terminal-based visualization, streamlining the feature and aligning with primary use cases
- **Configuration management**: Consolidated tool configuration for cleaner project structure and easier maintenance

### Fixed

- **Test script compatibility**: Updated `test_all_commands.sh` to use `uv run --directory` for proper execution from any working directory and corrected lockfile references to use absolute paths and proper lockfile names (`package-lock.json`, `Cargo.lock`)
- **Dependency analysis documentation**: Updated guides to reflect removal of HTML/JSON output and clarify terminal-only visualization approach

### Breaking Changes

- **Removed `--show-dependencies` option from `check` command**: This experimental option provided limited dependency statistics (average, min, max, count only). Use the `trace` command instead for comprehensive dependency tree analysis and visualization with full tree structure, individual package scores, and flexible visualization.

  **Migration**: Replace `os4g check <package> --show-dependencies` with `os4g trace <package>`.

## v0.22.0 - 2026-01-06

### Added

- Comprehensive CLI command test automation script (`test_all_commands.sh`) for systematically testing all major CLI commands, options, and edge cases
- Enhanced CLI modularity with subcommand organization into dedicated modules for cache, check, graph, gratitude, and trend commands
- New CLI utilities package (`cli_utils/`) for shared helpers, output formatting, constants, and loaders

### Improved

- CLI architecture with improved maintainability through modularization of monolithic CLI implementation
- SSL verification logic to consistently use `ssl.SSLContext` with support for both file and directory CA paths
- Type safety for profile weights in configuration handling
- Test reliability by aligning mock patches with new import paths
- Documentation consistency across all cache-related guides with unified `os4g cache` subcommand syntax
- Code organization and separation of concerns for easier future CLI enhancements

### Documentation

- Updated release process documentation with clearer guidance on analyzing changes before versioning
- Consolidated cache command syntax across README, guides, and troubleshooting documentation

## v0.21.0 - 2026-01-06

### Improved

- Trend analysis performance with per-window caching mechanism
  - Granular caching for VCS data by time window to minimize redundant API calls
  - Cache reuse across multiple analyses and profiles
  - Configurable cache TTL and manual cache clearing support
  - Cache statistics displayed in CLI output for transparency
  - Comprehensive documentation and unit tests for caching mechanism

## v0.20.0 - 2026-01-06

### Added

- Trend analysis feature (`os4g trend`) for tracking sustainability score changes over time
  - Support for multiple time intervals: daily, weekly, monthly, quarterly, semi-annual, annual
  - Configurable analysis periods and time window sizes
  - Client-side filtering to prevent sampling bias in historical data
  - Classification of 16 time-dependent metrics vs 8 time-independent metrics
  - Terminal visualization with score trend table, ASCII chart, and top metric changes
  - Package specification formats: `package`, `ecosystem:package`, or `-e ecosystem package`
  - Ecosystem auto-inference (defaults to Python when not specified)
  - Comprehensive trend analysis documentation
- LFX Insights integration with badges and links for ecosystem visibility

### Improved

- VCS providers (GitHub, GitLab) to support time window filtering for historical analysis
- Repository data fetching to avoid API sampling bias by filtering client-side
- Trend command to support ecosystem:package format and ecosystem inference
- Python type analysis with Ty integration for enhanced type checking
- Unit tests robustness and error handling across the codebase
- Metric API by removing legacy input support for simplified usage
- Documentation with trend analysis guide and updated getting started examples

## v0.19.0 - 2026-01-04

### Added

- Strategic product roadmap documenting planned features and future improvements
- Interactive dependency graph visualization with interactive visualization capabilities
- Launch configurations for debugging various languages in VSCode

### Improved

- Demo data with populated CHAOSS metric models and observations for better examples
- Bus Factor metric to recognize PR mergers as contributors alongside commit authors
- GitHub Actions documentation to include bun.lock and deno.lock in JavaScript ecosystem detection
- Metric messages to refer to "public contributions" instead of just "commits"
- Pre-commit hook version references to v0.18.0

### Documentation

- Added GitLab CI/CD integration guide for repository analysis workflows
- Dependency graph visualization documentation

## v0.18.0 - 2026-01-04

### Added

- Robust, multi-stage bot detection and exclusion system with configurable rules for contributor analysis
- Support for parsing pnpm-lock.yaml v9 format for improved lockfile compatibility

### Improved

- Installation instructions with expanded options (pipx, uv, Docker, GitHub Actions) and better isolation guidance
- CHAOSS metrics alignment documentation with refined table consistency and priority ordering
- Package name extraction for pnpm paths with scoped and versioned package handling
- Bun.lock parsing with array-based and dict-based package format support
- JSONC compatibility with trailing comma handling in lockfile parsing
- API rate limit handling with reduced default parallel worker count (10 → 5)
- Bus factor metric documentation emphasizing estimation limitations and encouraging further investigation
- Overall transparency in contributor redundancy metrics with explicit warnings about data accuracy

### Fixed

- Markdown links for Quality & Maintenance and Visibility & Adoption metrics documentation
- Async result handling in make_resolver_parser function
- Type hint for _coerce_int function parameter

## v0.17.0 - 2026-01-03

### Removed

- Optional dependents analysis feature
- Libraries.io integration for dependents analysis

## v0.16.0 - 2026-01-03

### Added

- GitLab VCS provider support for GitLab repository analysis

### Improved

- Metric checking refactored to use VCS-agnostic data model for better multi-provider support
- Cache file format updated to JSON gzip with improved metric naming (Cache Build Health metric)
- Plugin loading error handling with enhanced warning messages for better visibility of metric issues
- Overall score calculation now uses weighted metric scoring

### Fixed

- Enhanced warning messages for metric plugin loading errors
- Updated metric name to "Build Health" for consistency

## v0.15.0 - 2026-01-02

### Added

- VCS abstraction layer for flexible version control system support.
- Demo mode support for testing without actual API calls.
- Skipped metric reporting in analysis results.
- Plugin metric weight warnings for better transparency.
- Code of Conduct detection as a community health signal.
- Support for Swift Package.resolved, Haskell stack.yaml.lock, and Perl cpanfile.snapshot lockfile formats.
- Multi-ecosystem dependency summary with enhanced lockfile support.

### Improved

- Unified metric naming to 'Community Health' for consistency.
- Optional field handling across multiple resolvers for better Python compatibility.
- Dependency extraction capabilities for Swift, Stack (Haskell), and CPAN (Perl) ecosystems.
- Ecosystem descriptions to accurately reflect supported languages.

### Documentation

- Clarified dependency analysis as an experimental feature.
- Enhanced release process documentation with detailed CHANGELOG guidelines.
- Renamed 'Maintainer Responsiveness' metric to 'Community Health' for better alignment.

## v0.14.3 - 2026-01-02

- Added: scoring profile support to batch repository analysis.
- Improved: HTML report templating and ecosystem help text.
- Improved: batch item normalization and formatting for clearer output.
- Updated: demo GIF for improved visual representation.

## v0.14.2 - 2026-01-02

- Fixed: clarified GitHub token requirements in documentation.
- Fixed: improved documentation for minimal setup and GitHub-hosted analysis.
- Improved: standardized user-facing messages and clarified dependents metric.
- Improved: updated demo assets and timing documentation.

## v0.14.1 - 2026-01-02

- Bug fixes and improvements to enhance stability.

## v0.14.0 - 2026-01-02

- Added a pluggable metrics registry with modular built-in metrics and entry-point discovery.
- Added JSON and HTML report export with a new HTML report template.
- Added configurable scoring profiles and profile overrides.
- Improved SSL configuration with custom CA certificate support and clearer --insecure handling.
- Centralized cache write logic and expanded docs and test coverage.

## v0.13.3 - 2025-12-31

- Added CHAOSS model generation using computed metric data.
- Added on-demand analysis for uncached dependencies.

## v0.13.2 - 2025-12-31

- Added advanced analysis options and expanded GitHub Actions documentation.

## v0.13.1 - 2025-12-31

- Improved batch repository analysis and community-driven project detection.
- Refreshed demo assets.

## v0.13.0 - 2025-12-31

- Added cache management commands (clear-cache, list-cache) with filtering and sorting.
- Improved cache validation, invalidation, and expired-entry handling.

## v0.12.0 - 2025-12-31

- Standardized all metrics to a 0-10 scale with integer weights.
- Added new metrics: maintainer load distribution, stale issue ratio, and PR merge speed.
- Improved README detection and symlink handling; expanded metric documentation.

## v0.11.2 - 2025-12-30

- Refined scoring logic for funding, issue resolution, and missing CI/test signals.
- Added ecosystem display/tracking in results and recalculated gratitude scores from metrics.
- Removed legacy schema migration logic and refreshed tooling/docs.

## v0.11.1 - 2025-12-30

- Centralized error handling and removed inline logging.

## v0.11.0 - 2025-12-30

- Added batch GraphQL analysis with lockfile caching.
- Added parallel analysis and HTTP client pooling for faster runs.
- Cleaned up workflows and improved project structure and Makefile targets.

## v0.10.0 - 2025-12-30

- Breaking change: simplified to a GitHub-token-only architecture.

## v0.9.2 - 2025-12-26

- Added per-package dependency extraction from lockfiles.
- Improved dependency score calculation using metrics.

## v0.9.1 - 2025-12-26

- Excluded bot accounts from contributor metrics.

## v0.9.0 - 2025-12-26

- Added support for Dart, Elixir, Haskell, Perl, R, and Swift ecosystems.

## v0.8.1 - 2025-12-26

- Unified repository URL parsing across ecosystems.
- Expanded CLI/display tests and Java resolver coverage.
- Added release process guidance and improved TestPyPI workflow conditions.

## v0.8.0 - 2025-12-24

- Added the os4g CLI alias and updated documentation.
- Added output style controls and analysis version controls.

## v0.7.0 - 2025-12-20

- Added dependency score analysis and reporting with new documentation.
- Added Cloudflare KV caching for historical trend analysis.
- Improved database workflows and adjusted scoring weights/thresholds.

## v0.6.0 - 2025-12-16

- Added the MkDocs documentation site.
- Added time-series trend analysis and improved fork activity evaluation.
- Added Kotlin ecosystem support.
- Added gzip compression for cache/database files and compact CLI output.

## v0.5.0 - 2025-12-11

- Added an optional downstream dependents metric via Libraries.io.
- Clarified that dependents are informational only.

## v0.4.0 - 2025-12-11

- Added recursive scanning with directory exclusions and lockfile parsing improvements.
- Added the Gratitude Vending Machine feature and documentation.
- Expanded to 21 metrics and introduced category-weighted scoring.
- Added pnpm lockfile support and a scoring profile comparison example.

## v0.3.0 - 2025-12-10

- Added the CHAOSS Metrics Alignment Validation report and CHAOSS models.
- Added community engagement metrics and updated README guidance.

## v0.2.0 - 2025-12-09

- Introduced local caching for analysis results and database data.
- Added funding links and community-driven status in outputs.
- Added root-dir and manifest options, plus pyproject.toml and Pipfile support.
- Expanded GitHub URL resolution and added Go ecosystem support.
- Added publishing workflows, Python 3.14 support, and documentation refreshes.
