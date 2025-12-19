"""
Tests for community contribution functionality.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.contribution_validator import (
    ContributionValidator,
    ValidationError,
)


@pytest.fixture
def valid_contribution_data():
    """Sample valid contribution data."""
    return {
        "_contribution_metadata": {
            "schema_version": "2.0",
            "contributor": "test_user",
            "contribution_date": datetime.now(timezone.utc).isoformat(),
            "tool_version": "0.7.0",
            "ecosystem": "python",
            "package_count": 1,
            "analysis_method": "github_graphql",
        },
        "packages": {
            "python:requests": {
                "ecosystem": "python",
                "package_name": "requests",
                "github_url": "https://github.com/psf/requests",
                "metrics": [
                    {
                        "name": "Contributor Redundancy",
                        "score": 15,
                        "max_score": 20,
                        "message": "Good contributor diversity",
                        "risk": "Low",
                    }
                ],
                "models": [],
                "signals": {
                    "contributor_count": 10,
                    "funding_link_count": 2,
                },
                "cache_metadata": {
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "ttl_seconds": 604800,
                    "source": "user_analysis",
                },
            }
        },
    }


@pytest.fixture
def temp_contribution_file(tmp_path, valid_contribution_data):
    """Create a temporary contribution file."""
    file_path = tmp_path / "test_contribution.json"
    with open(file_path, "w") as f:
        json.dump(valid_contribution_data, f)
    return file_path


def test_validator_valid_contribution(temp_contribution_file):
    """Test that a valid contribution passes validation."""
    validator = ContributionValidator()
    is_valid = validator.validate_file(temp_contribution_file)

    assert is_valid
    assert len(validator.errors) == 0


def test_validator_missing_metadata(tmp_path):
    """Test that missing metadata is caught."""
    data = {"packages": {}}
    file_path = tmp_path / "test.json"
    with open(file_path, "w") as f:
        json.dump(data, f)

    validator = ContributionValidator()
    is_valid = validator.validate_file(file_path)

    assert not is_valid
    assert any("Missing required field" in error for error in validator.errors)


def test_validator_invalid_ecosystem(tmp_path):
    """Test that invalid ecosystem is caught."""
    data = {
        "_contribution_metadata": {
            "schema_version": "2.0",
            "contributor": "test",
            "contribution_date": datetime.now(timezone.utc).isoformat(),
            "tool_version": "0.7.0",
            "ecosystem": "invalid_ecosystem",
            "package_count": 0,
        },
        "packages": {},
    }
    file_path = tmp_path / "test.json"
    with open(file_path, "w") as f:
        json.dump(data, f)

    validator = ContributionValidator()
    is_valid = validator.validate_file(file_path)

    assert not is_valid
    assert any("Invalid ecosystem" in error for error in validator.errors)


def test_validator_invalid_github_url(tmp_path):
    """Test that invalid GitHub URLs are caught."""
    data = {
        "_contribution_metadata": {
            "schema_version": "2.0",
            "contributor": "test",
            "contribution_date": datetime.now(timezone.utc).isoformat(),
            "tool_version": "0.7.0",
            "ecosystem": "python",
            "package_count": 1,
        },
        "packages": {
            "python:test": {
                "ecosystem": "python",
                "package_name": "test",
                "github_url": "not-a-valid-url",
                "metrics": [],
            }
        },
    }
    file_path = tmp_path / "test.json"
    with open(file_path, "w") as f:
        json.dump(data, f)

    validator = ContributionValidator()
    is_valid = validator.validate_file(file_path)

    assert not is_valid
    assert any("Invalid GitHub URL" in error for error in validator.errors)


def test_validator_detects_token(tmp_path):
    """Test that API tokens are detected."""
    data = {
        "_contribution_metadata": {
            "schema_version": "2.0",
            "contributor": "test",
            "contribution_date": datetime.now(timezone.utc).isoformat(),
            "tool_version": "0.7.0",
            "ecosystem": "python",
            "package_count": 1,
        },
        "packages": {
            "python:test": {
                "ecosystem": "python",
                "package_name": "test",
                "github_url": "https://github.com/test/test",
                "metrics": [],
                "secret_field": "ghp_1234567890123456789012345678901234567",
            }
        },
    }
    file_path = tmp_path / "test.json"
    with open(file_path, "w") as f:
        json.dump(data, f)

    validator = ContributionValidator()
    is_valid = validator.validate_file(file_path)

    assert not is_valid
    assert any("token detected" in error.lower() for error in validator.errors)


def test_validator_score_validation(tmp_path):
    """Test that invalid scores are caught."""
    data = {
        "_contribution_metadata": {
            "schema_version": "2.0",
            "contributor": "test",
            "contribution_date": datetime.now(timezone.utc).isoformat(),
            "tool_version": "0.7.0",
            "ecosystem": "python",
            "package_count": 1,
        },
        "packages": {
            "python:test": {
                "ecosystem": "python",
                "package_name": "test",
                "github_url": "https://github.com/test/test",
                "metrics": [
                    {
                        "name": "Test Metric",
                        "score": 150,  # Exceeds max_score
                        "max_score": 100,
                        "message": "Test",
                        "risk": "Low",
                    }
                ],
            }
        },
    }
    file_path = tmp_path / "test.json"
    with open(file_path, "w") as f:
        json.dump(data, f)

    validator = ContributionValidator()
    is_valid = validator.validate_file(file_path)

    assert not is_valid
    assert any("exceeds max_score" in error for error in validator.errors)


def test_validator_invalid_risk_level(tmp_path):
    """Test that invalid risk levels are caught."""
    data = {
        "_contribution_metadata": {
            "schema_version": "2.0",
            "contributor": "test",
            "contribution_date": datetime.now(timezone.utc).isoformat(),
            "tool_version": "0.7.0",
            "ecosystem": "python",
            "package_count": 1,
        },
        "packages": {
            "python:test": {
                "ecosystem": "python",
                "package_name": "test",
                "github_url": "https://github.com/test/test",
                "metrics": [
                    {
                        "name": "Test Metric",
                        "score": 10,
                        "max_score": 100,
                        "message": "Test",
                        "risk": "InvalidRisk",
                    }
                ],
            }
        },
    }
    file_path = tmp_path / "test.json"
    with open(file_path, "w") as f:
        json.dump(data, f)

    validator = ContributionValidator()
    is_valid = validator.validate_file(file_path)

    assert not is_valid
    assert any("Invalid risk level" in error for error in validator.errors)


def test_sanitize_contribution_data():
    """Test data sanitization in export."""
    from oss_sustain_guard.cli import _sanitize_contribution_data

    raw_data = {
        "python:requests": {
            "ecosystem": "python",
            "package_name": "requests",
            "github_url": "https://github.com/psf/requests",
            "metrics": [],
            "models": [],
            "signals": {},
            "cache_metadata": {
                "fetched_at": "2025-12-19T20:00:00Z",
                "ttl_seconds": 604800,
                "source": "github",
            },
            "should_not_be_included": "sensitive_data",
        }
    }

    sanitized = _sanitize_contribution_data(raw_data)

    # Check that expected fields are present
    assert "python:requests" in sanitized
    entry = sanitized["python:requests"]
    assert "ecosystem" in entry
    assert "package_name" in entry
    assert "github_url" in entry
    assert "cache_metadata" in entry

    # Check that cache_metadata source is updated
    assert entry["cache_metadata"]["source"] == "user_analysis"

    # Check that unexpected fields are removed
    assert "should_not_be_included" not in entry


def test_export_command_integration(tmp_path, monkeypatch):
    """Test export command end-to-end."""
    # Mock cache data
    mock_cache_data = {
        "python:requests": {
            "ecosystem": "python",
            "package_name": "requests",
            "github_url": "https://github.com/psf/requests",
            "metrics": [
                {
                    "name": "Test Metric",
                    "score": 10,
                    "max_score": 20,
                    "message": "Test",
                    "risk": "Low",
                }
            ],
            "models": [],
            "signals": {},
            "cache_metadata": {
                "fetched_at": "2025-12-19T20:00:00Z",
                "ttl_seconds": 604800,
                "source": "github",
            },
        }
    }

    # Mock load_cache
    with patch("oss_sustain_guard.cli.load_cache", return_value=mock_cache_data):
        with patch("oss_sustain_guard.cli.is_package_excluded", return_value=False):
            from oss_sustain_guard.cli import _sanitize_contribution_data

            # Test sanitization
            sanitized = _sanitize_contribution_data(mock_cache_data)

            # Build contribution structure
            output_file = tmp_path / "test_export.json"
            contribution = {
                "_contribution_metadata": {
                    "schema_version": "2.0",
                    "contributor": "test_user",
                    "contribution_date": datetime.now(timezone.utc).isoformat(),
                    "tool_version": "0.7.0",
                    "ecosystem": "python",
                    "package_count": len(sanitized),
                    "analysis_method": "github_graphql",
                },
                "packages": sanitized,
            }

            # Write to file
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(contribution, f, indent=2)

            # Validate the exported file
            validator = ContributionValidator()
            is_valid = validator.validate_file(output_file)

            assert is_valid
            assert len(validator.errors) == 0

            # Check file content
            with open(output_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            assert "_contribution_metadata" in loaded
            assert "packages" in loaded
            assert "python:requests" in loaded["packages"]
            assert loaded["packages"]["python:requests"]["cache_metadata"]["source"] == "user_analysis"
