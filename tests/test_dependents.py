"""
Tests for the Downstream Dependents metric using Libraries.io API.
"""

import os
from unittest.mock import MagicMock, patch


class TestLibrariesioAPIIntegration:
    """Test Libraries.io API query functionality."""

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_api_key"})
    @patch("oss_sustain_guard.core.httpx.Client")
    def test_query_librariesio_api_success(self, mock_client_class):
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

        # Mock client context manager
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Reload module to get updated environment variable
        from importlib import reload

        import oss_sustain_guard.core as core_module

        reload(core_module)

        result = core_module._query_librariesio_api("Pypi", "requests")

        assert result is not None
        assert result["dependents_count"] == 500000
        assert result["dependent_repos_count"] == 150000

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": ""}, clear=True)
    def test_query_librariesio_api_no_key(self):
        """Test that API query returns None when API key not set."""
        # Reload module to get updated environment variable
        from importlib import reload

        import oss_sustain_guard.core as core_module

        core_module = reload(core_module)

        result = core_module._query_librariesio_api("Pypi", "requests")
        assert result is None

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_api_key"})
    @patch("oss_sustain_guard.core.httpx.Client")
    def test_query_librariesio_api_not_found(self, mock_client_class):
        """Test Libraries.io API query when package not found."""
        # Mock 404 response
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Reload module
        from importlib import reload

        import oss_sustain_guard.core as core_module

        reload(core_module)

        result = core_module._query_librariesio_api("Pypi", "nonexistent-package")
        assert result is None


class TestDependentsCountMetric:
    """Test the check_dependents_count metric function."""

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": ""}, clear=True)
    def test_dependents_count_no_api_key(self):
        """Test that metric returns None when API key not configured."""
        # Reload module to get updated environment variable
        from importlib import reload

        import oss_sustain_guard.core as core_module

        reload(core_module)

        result = core_module.check_dependents_count(
            "https://github.com/psf/requests", "Pypi", "requests"
        )
        assert result is None

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    @patch("oss_sustain_guard.core._query_librariesio_api")
    def test_dependents_count_critical_infrastructure(self, mock_query):
        """Test metric for packages with very high dependents count."""
        mock_query.return_value = {
            "dependents_count": 15000,
            "dependent_repos_count": 5000,
        }

        from oss_sustain_guard.core import check_dependents_count

        result = check_dependents_count(
            "https://github.com/psf/requests", "Pypi", "requests"
        )

        assert result is not None
        assert result.name == "Downstream Dependents"
        assert result.score == 20
        assert result.max_score == 20
        assert result.risk == "None"
        assert "Critical infrastructure" in result.message
        assert "15,000" in result.message

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    @patch("oss_sustain_guard.core._query_librariesio_api")
    def test_dependents_count_widely_adopted(self, mock_query):
        """Test metric for widely adopted packages."""
        mock_query.return_value = {
            "dependents_count": 2500,
            "dependent_repos_count": 800,
        }

        from oss_sustain_guard.core import check_dependents_count

        result = check_dependents_count(
            "https://github.com/example/package", "NPM", "example-package"
        )

        assert result is not None
        assert result.score == 18
        assert "Widely adopted" in result.message

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    @patch("oss_sustain_guard.core._query_librariesio_api")
    def test_dependents_count_no_dependents(self, mock_query):
        """Test metric for packages with no dependents."""
        mock_query.return_value = {
            "dependents_count": 0,
            "dependent_repos_count": 0,
        }

        from oss_sustain_guard.core import check_dependents_count

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

        from oss_sustain_guard.core import check_dependents_count

        result = check_dependents_count(
            "https://github.com/example/unknown", "Pypi", "unknown-package"
        )

        assert result is not None
        assert result.score == 0
        assert "not found" in result.message

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    def test_dependents_count_no_platform(self):
        """Test metric returns None when platform not provided."""
        from oss_sustain_guard.core import check_dependents_count

        result = check_dependents_count(
            "https://github.com/example/package", platform=None, package_name="package"
        )
        assert result is None

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    def test_dependents_count_no_package_name(self):
        """Test metric returns None when package_name not provided."""
        from oss_sustain_guard.core import check_dependents_count

        result = check_dependents_count(
            "https://github.com/example/package", platform="Pypi", package_name=None
        )
        assert result is None

    @patch.dict(os.environ, {"LIBRARIESIO_API_KEY": "test_key"})
    @patch("oss_sustain_guard.core._query_librariesio_api")
    def test_dependents_count_scoring_tiers(self, mock_query):
        """Test all scoring tiers for dependents count."""
        from oss_sustain_guard.core import check_dependents_count

        # Test data: (dependents_count, expected_score, expected_risk)
        test_cases = [
            (15000, 20, "None"),  # Critical infrastructure
            (2000, 18, "None"),  # Widely adopted
            (600, 15, "None"),  # Popular
            (150, 12, "Low"),  # Established
            (75, 9, "Low"),  # Growing
            (25, 6, "Low"),  # Early adoption
            (5, 3, "Low"),  # Used by others
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
