"""
Tests for the Downstream Dependents metric using Libraries.io API.
"""

import os
from unittest.mock import MagicMock, patch

from oss_sustain_guard.core import check_dependents_count
from oss_sustain_guard.librariesio import query_librariesio_api


class TestLibrariesioAPIIntegration:
    """Test Libraries.io API query functionality."""

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_api_key"})
    @patch("oss_sustain_guard.librariesio._get_http_client")
    def test_query_librariesio_api_success(self, mock_get_client):
        """Test successful Libraries.io API query."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "requests",
            "platform": "Pypi",
            "dependents_count": 500000,
            "dependent_repos_count": 150000,
        }

        # Mock client
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = query_librariesio_api("Pypi", "requests")

        assert result is not None
        assert result["dependents_count"] == 500000
        assert result["dependent_repos_count"] == 150000

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": ""}, clear=True)
    def test_query_librariesio_api_no_key(self):
        """Test that API query returns None when API key not set."""
        result = query_librariesio_api("Pypi", "requests")
        assert result is None

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_api_key"})
    @patch("oss_sustain_guard.librariesio._get_http_client")
    def test_query_librariesio_api_not_found(self, mock_get_client):
        """Test Libraries.io API query when package not found."""
        # Mock 404 response
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = query_librariesio_api("Pypi", "nonexistent-package")
        assert result is None


class TestDependentsCountMetric:
    """Test the check_dependents_count metric function."""

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": ""}, clear=True)
    def test_dependents_count_no_api_key(self):
        """Test that metric returns None when API key not configured."""
        result = check_dependents_count(
            "https://github.com/psf/requests", "Pypi", "requests"
        )
        assert result is None

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    @patch("oss_sustain_guard.metrics.dependents_count.query_librariesio_api")
    def test_dependents_count_critical_infrastructure(self, mock_query):
        """Test metric for packages with very high dependents count."""
        mock_query.return_value = {
            "dependents_count": 15000,
            "dependent_repos_count": 5000,
        }

        result = check_dependents_count(
            "https://github.com/psf/requests", "Pypi", "requests"
        )

        assert result is not None
        assert result.name == "Downstream Dependents"
        assert result.score == 10  # 20/20 → 10/10
        assert result.max_score == 10
        assert result.risk == "None"
        assert "Critical infrastructure" in result.message
        assert "15,000" in result.message

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    @patch("oss_sustain_guard.metrics.dependents_count.query_librariesio_api")
    def test_dependents_count_widely_adopted(self, mock_query):
        """Test metric for widely adopted packages."""
        mock_query.return_value = {
            "dependents_count": 2500,
            "dependent_repos_count": 800,
        }

        result = check_dependents_count(
            "https://github.com/example/package", "NPM", "example-package"
        )

        assert result is not None
        assert result.score == 9  # 18/20 → 9/10
        assert result.max_score == 10
        assert "Widely adopted" in result.message

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    @patch("oss_sustain_guard.metrics.dependents_count.query_librariesio_api")
    def test_dependents_count_no_dependents(self, mock_query):
        """Test metric for packages with no dependents."""
        mock_query.return_value = {
            "dependents_count": 0,
            "dependent_repos_count": 0,
        }

        result = check_dependents_count(
            "https://github.com/example/new-package", "Cargo", "new-package"
        )

        assert result is not None
        assert result.score == 0
        assert result.risk == "Low"
        assert "No downstream dependencies" in result.message

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    @patch("oss_sustain_guard.core._query_librariesio_api")
    def test_dependents_count_package_not_found(self, mock_query):
        """Test metric when package not found on Libraries.io."""
        mock_query.return_value = None

        result = check_dependents_count(
            "https://github.com/example/unknown", "Pypi", "unknown-package"
        )

        assert result is not None
        assert result.score == 0
        assert "not found" in result.message

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    def test_dependents_count_no_platform(self):
        """Test metric returns None when platform not provided."""
        result = check_dependents_count(
            "https://github.com/example/package", platform=None, package_name="package"
        )
        assert result is None

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    def test_dependents_count_no_package_name(self):
        """Test metric returns None when package_name not provided."""
        result = check_dependents_count(
            "https://github.com/example/package", platform="Pypi", package_name=None
        )
        assert result is None

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    @patch("oss_sustain_guard.metrics.dependents_count.query_librariesio_api")
    def test_dependents_count_scoring_tiers(self, mock_query):
        """Test all scoring tiers for dependents count."""
        # Test data: (dependents_count, expected_score, expected_risk)
        test_cases = [
            (15000, 10, "None"),  # Critical infrastructure: 20/20 → 10/10
            (2000, 9, "None"),  # Widely adopted: 18/20 → 9/10
            (600, 8, "None"),  # Popular: 15/20 → 8/10
            (150, 6, "Low"),  # Established: 12/20 → 6/10
            (75, 5, "Low"),  # Growing: 9/20 → 5/10
            (25, 3, "Low"),  # Early adoption: 6/20 → 3/10
            (5, 2, "Low"),  # Used by others: 3/20 → 2/10
            (0, 0, "Low"),  # No dependents
        ]

        for dependents_count, expected_score, expected_risk in test_cases:
            mock_query.return_value = {
                "dependents_count": dependents_count,
                "dependent_repos_count": dependents_count // 3,
            }

            result = check_dependents_count(
                "https://github.com/test/package", "Pypi", "test-package"
            )

            assert result is not None
            assert result.score == expected_score, (
                f"Failed for {dependents_count} dependents: expected {expected_score}, got {result.score}"
            )
            assert result.risk == expected_risk
