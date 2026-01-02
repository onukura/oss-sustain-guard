# Changelog

All notable changes to OSS Sustain Guard are documented in this file.

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
