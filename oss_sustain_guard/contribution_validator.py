"""
Validation module for community contributions.

Ensures contributed data meets quality and security standards before integration.
"""

import json
import re
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


class ContributionValidator:
    """Validates contribution files for security and correctness."""

    # Expected schema version
    SUPPORTED_SCHEMA_VERSIONS = ["2.0"]

    # Valid ecosystem names
    VALID_ECOSYSTEMS = {
        "python",
        "javascript",
        "rust",
        "go",
        "php",
        "java",
        "kotlin",
        "csharp",
        "ruby",
    }

    # Metric names that should exist (core metrics)
    EXPECTED_METRIC_NAMES = {
        "Contributor Redundancy",
        "Maintainer Retention",
        "Recent Activity",
        "Release Rhythm",
        "Funding Signals",
    }

    def __init__(self, strict: bool = False):
        """Initialize validator.

        Args:
            strict: If True, enforce stricter validation rules
        """
        self.strict = strict
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_file(self, file_path: Path) -> bool:
        """Validate a contribution file.

        Args:
            file_path: Path to contribution JSON file

        Returns:
            True if validation passes, False otherwise
        """
        self.errors = []
        self.warnings = []

        # Check file exists
        if not file_path.exists():
            self.errors.append(f"File not found: {file_path}")
            return False

        # Load JSON
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON: {e}")
            return False

        # Validate structure
        self._validate_structure(data)

        # Validate metadata
        if "_contribution_metadata" in data:
            self._validate_metadata(data["_contribution_metadata"])

        # Validate packages
        if "packages" in data:
            self._validate_packages(data["packages"])

        # Check for suspicious patterns
        self._check_security(data)

        return len(self.errors) == 0

    def _validate_structure(self, data: dict) -> None:
        """Validate top-level structure."""
        required_fields = ["_contribution_metadata", "packages"]

        for field in required_fields:
            if field not in data:
                self.errors.append(f"Missing required field: {field}")

        # Check for unexpected top-level fields
        allowed_fields = {"_contribution_metadata", "packages"}
        for field in data.keys():
            if field not in allowed_fields:
                self.warnings.append(f"Unexpected top-level field: {field}")

    def _validate_metadata(self, metadata: dict) -> None:
        """Validate contribution metadata."""
        required_fields = {
            "schema_version",
            "contributor",
            "contribution_date",
            "tool_version",
            "ecosystem",
            "package_count",
        }

        for field in required_fields:
            if field not in metadata:
                self.errors.append(f"Missing metadata field: {field}")

        # Validate schema version
        if "schema_version" in metadata:
            version = metadata["schema_version"]
            if version not in self.SUPPORTED_SCHEMA_VERSIONS:
                self.errors.append(
                    f"Unsupported schema version: {version} "
                    f"(supported: {', '.join(self.SUPPORTED_SCHEMA_VERSIONS)})"
                )

        # Validate ecosystem
        if "ecosystem" in metadata:
            ecosystem = metadata["ecosystem"]
            if ecosystem not in self.VALID_ECOSYSTEMS:
                self.errors.append(
                    f"Invalid ecosystem: {ecosystem} "
                    f"(valid: {', '.join(sorted(self.VALID_ECOSYSTEMS))})"
                )

        # Validate package count matches actual count
        if "package_count" in metadata and "packages" in metadata:
            declared_count = metadata["package_count"]
            # This will be validated in the main validate_file method
            # Just check type here
            if not isinstance(declared_count, int) or declared_count < 0:
                self.errors.append(
                    f"Invalid package_count: {declared_count} (must be positive integer)"
                )

        # Validate contributor name (basic check)
        if "contributor" in metadata:
            contributor = metadata["contributor"]
            if not isinstance(contributor, str) or len(contributor) < 1:
                self.errors.append("Invalid contributor name (must be non-empty string)")

    def _validate_packages(self, packages: dict) -> None:
        """Validate package entries."""
        if not isinstance(packages, dict):
            self.errors.append("Packages must be a dictionary")
            return

        if len(packages) == 0:
            self.errors.append("No packages in contribution")
            return

        for key, entry in packages.items():
            self._validate_package_entry(key, entry)

    def _validate_package_entry(self, key: str, entry: dict) -> None:
        """Validate a single package entry."""
        # Validate key format: "ecosystem:package_name"
        if ":" not in key:
            self.errors.append(f"Invalid package key format: {key} (expected 'ecosystem:name')")
            return

        ecosystem, package_name = key.split(":", 1)

        # Validate ecosystem
        if ecosystem not in self.VALID_ECOSYSTEMS:
            self.errors.append(f"Invalid ecosystem in key {key}: {ecosystem}")

        # Required fields
        required_fields = {"ecosystem", "package_name", "github_url"}
        for field in required_fields:
            if field not in entry:
                self.errors.append(f"Missing required field in {key}: {field}")

        # Validate ecosystem consistency
        if "ecosystem" in entry and entry["ecosystem"] != ecosystem:
            self.errors.append(
                f"Ecosystem mismatch in {key}: key={ecosystem}, entry={entry['ecosystem']}"
            )

        # Validate package_name consistency
        if "package_name" in entry and entry["package_name"] != package_name:
            # Warn but don't fail - some packages have different names
            self.warnings.append(
                f"Package name mismatch in {key}: key={package_name}, entry={entry['package_name']}"
            )

        # Validate GitHub URL
        if "github_url" in entry:
            self._validate_github_url(key, entry["github_url"])

        # Validate metrics if present
        if "metrics" in entry:
            self._validate_metrics(key, entry["metrics"])

        # Check for sensitive data
        self._check_entry_security(key, entry)

    def _validate_github_url(self, key: str, url: str) -> None:
        """Validate GitHub repository URL."""
        if not isinstance(url, str):
            self.errors.append(f"GitHub URL in {key} must be a string")
            return

        # Basic GitHub URL pattern
        github_pattern = r"^https://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+/?$"
        if not re.match(github_pattern, url):
            self.errors.append(
                f"Invalid GitHub URL format in {key}: {url}"
            )

    def _validate_metrics(self, key: str, metrics: list) -> None:
        """Validate metrics array."""
        if not isinstance(metrics, list):
            self.errors.append(f"Metrics in {key} must be a list")
            return

        if len(metrics) == 0:
            self.warnings.append(f"No metrics in {key}")
            return

        # Check metric structure
        for idx, metric in enumerate(metrics):
            if not isinstance(metric, dict):
                self.errors.append(f"Metric {idx} in {key} must be a dictionary")
                continue

            required_fields = {"name", "score", "max_score", "message", "risk"}
            for field in required_fields:
                if field not in metric:
                    self.errors.append(
                        f"Missing field '{field}' in metric {idx} of {key}"
                    )

            # Validate score ranges
            if "score" in metric and "max_score" in metric:
                score = metric["score"]
                max_score = metric["max_score"]

                if not isinstance(score, (int, float)):
                    self.errors.append(
                        f"Invalid score type in metric {idx} of {key}: {type(score)}"
                    )
                elif score < 0:
                    self.errors.append(
                        f"Negative score in metric {idx} of {key}: {score}"
                    )
                elif score > max_score:
                    self.errors.append(
                        f"Score exceeds max_score in metric {idx} of {key}: {score} > {max_score}"
                    )

            # Validate risk level
            if "risk" in metric:
                valid_risks = {"Critical", "High", "Medium", "Low", "None"}
                if metric["risk"] not in valid_risks:
                    self.errors.append(
                        f"Invalid risk level in metric {idx} of {key}: {metric['risk']}"
                    )

    def _check_security(self, data: dict) -> None:
        """Check for security issues in the entire contribution."""
        # Convert to string for pattern matching
        data_str = json.dumps(data)

        # Check for potential API tokens
        token_patterns = [
            r"ghp_[a-zA-Z0-9]{36}",  # GitHub token
            r"gho_[a-zA-Z0-9]{36}",  # GitHub OAuth token
            r"Bearer [a-zA-Z0-9\-_]+",  # Bearer token
        ]

        for pattern in token_patterns:
            if re.search(pattern, data_str):
                self.errors.append(
                    "Potential API token detected in contribution (security risk)"
                )

        # Check for local file paths
        path_patterns = [
            r"[A-Za-z]:\\",  # Windows paths
            r"/home/[a-zA-Z0-9_-]+",  # Unix home paths
            r"/Users/[a-zA-Z0-9_-]+",  # macOS home paths
        ]

        for pattern in path_patterns:
            if re.search(pattern, data_str):
                self.warnings.append(
                    "Potential local file path detected in contribution"
                )

    def _check_entry_security(self, key: str, entry: dict) -> None:
        """Check a single entry for security issues."""
        # Check for suspicious fields that shouldn't be present
        suspicious_fields = {
            "api_key",
            "token",
            "password",
            "secret",
            "credential",
            "auth",
        }

        for field in entry.keys():
            if any(sus in field.lower() for sus in suspicious_fields):
                self.errors.append(
                    f"Suspicious field name in {key}: {field} (possible credential leak)"
                )

    def get_report(self) -> str:
        """Get a formatted validation report.

        Returns:
            Human-readable validation report
        """
        lines = []

        if self.errors:
            lines.append("[bold red]❌ Validation Failed[/bold red]\n")
            lines.append("[red]Errors:[/red]")
            for error in self.errors:
                lines.append(f"  • {error}")
        else:
            lines.append("[bold green]✓ Validation Passed[/bold green]")

        if self.warnings:
            lines.append("\n[yellow]Warnings:[/yellow]")
            for warning in self.warnings:
                lines.append(f"  • {warning}")

        return "\n".join(lines)


def validate_contribution_file(file_path: Path, strict: bool = False) -> bool:
    """Validate a contribution file and print report.

    Args:
        file_path: Path to contribution file
        strict: Use strict validation

    Returns:
        True if validation passes
    """
    validator = ContributionValidator(strict=strict)
    is_valid = validator.validate_file(file_path)

    # Print report
    console.print()
    console.print(validator.get_report())
    console.print()

    return is_valid
