# Roadmap

This document outlines the planned features and improvements for OSS Sustain Guard.

## Planned Features

### Time Machine Mode (Trend Analysis) ✅ Implemented in v0.20.0, released 2025-01-05

- ✅ Analyze score changes over time by collecting data across multiple time windows.
- ✅ Visualize trends in repository health metrics with terminal-based charts.
- ✅ Provide insights into how sustainability factors evolve over time.
- ✅ CLI command: `os4g trend <package>` with customizable intervals and window sizes.
- Note: Some metrics (stars, security alerts, documentation) are excluded as they cannot be historically analyzed.

### Reorganization CLI Commands ✅ Implemented in v0.22.0, released 2025-01-06

- ✅ Current commands are implemented in a single cli.py file.
- ✅ Commands have been modularized into separate files for better maintainability.

### Support for Self-Hosted VCS (GitLab, GitHub)

- Extend support to include self-hosted instances of GitLab and GitHub Enterprise.
- Allow users to configure custom VCS endpoints for analysis.
- Ensure compatibility with authentication mechanisms for self-hosted environments.

### AI-Powered Qualitative Analysis

- Integrate AI capabilities for qualitative analysis of repository data.
- Use machine learning models to provide deeper insights into maintainer behavior, community engagement, and potential risks.
- Generate natural language summaries and recommendations based on quantitative metrics.
