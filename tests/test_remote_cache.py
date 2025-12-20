"""
Tests for remote_cache module (Cloudflare KV client).
"""

from unittest.mock import Mock, patch

import httpx
import pytest

from oss_sustain_guard.remote_cache import CloudflareKVClient


@pytest.fixture
def mock_client():
    """Create a CloudflareKVClient for testing."""
    return CloudflareKVClient(
        worker_url="https://test.workers.dev",
        schema_version="2.0",
        timeout=5,
    )


class TestCloudflareKVClient:
    """Tests for CloudflareKVClient."""

    def test_make_key(self, mock_client):
        """Test cache key generation."""
        key = mock_client._make_key("python", "requests")
        assert key == "2.0:python:requests"

    def test_make_key_special_chars(self, mock_client):
        """Test cache key with special characters in package name."""
        key = mock_client._make_key("javascript", "@babel/core")
        assert key == "2.0:javascript:@babel/core"

    @patch("httpx.Client")
    def test_get_success(self, mock_httpx_client, mock_client):
        """Test successful single package retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ecosystem": "python",
            "package_name": "requests",
            "github_url": "https://github.com/psf/requests",
        }

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        mock_context.get.return_value = mock_response
        mock_httpx_client.return_value = mock_context

        result = mock_client.get("python", "requests")

        assert result is not None
        assert result["package_name"] == "requests"
        mock_context.get.assert_called_once_with(
            "https://test.workers.dev/2.0:python:requests", timeout=5
        )

    @patch("httpx.Client")
    def test_get_not_found(self, mock_httpx_client, mock_client):
        """Test get when package not found."""
        mock_response = Mock()
        mock_response.status_code = 404

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        mock_context.get.return_value = mock_response
        mock_httpx_client.return_value = mock_context

        result = mock_client.get("python", "nonexistent")

        assert result is None

    @patch("httpx.Client")
    def test_get_network_error(self, mock_httpx_client, mock_client):
        """Test get with network error."""
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        mock_context.get.side_effect = httpx.RequestError("Network error")
        mock_httpx_client.return_value = mock_context

        result = mock_client.get("python", "requests")

        assert result is None

    @patch("httpx.Client")
    def test_batch_get_success(self, mock_httpx_client, mock_client):
        """Test successful batch retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "2.0:python:requests": {"package_name": "requests"},
            "2.0:python:django": {"package_name": "django"},
        }

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        mock_context.post.return_value = mock_response
        mock_httpx_client.return_value = mock_context

        packages = [("python", "requests"), ("python", "django")]
        result = mock_client.batch_get(packages)

        assert len(result) == 2
        assert "2.0:python:requests" in result
        assert "2.0:python:django" in result

    @patch("httpx.Client")
    def test_batch_get_empty(self, mock_httpx_client, mock_client):
        """Test batch_get with empty list."""
        result = mock_client.batch_get([])
        assert result == {}

    @patch("httpx.Client")
    def test_batch_get_splits_large_batch(self, mock_httpx_client, mock_client):
        """Test that large batches are split into multiple requests."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        mock_context.post.return_value = mock_response
        mock_httpx_client.return_value = mock_context

        # Create 150 packages (should split into 2 batches of 100 and 50)
        packages = [(f"eco{i}", f"pkg{i}") for i in range(150)]
        mock_client.batch_get(packages)

        # Should make 2 POST requests
        assert mock_context.post.call_count == 2

    @patch("httpx.Client")
    def test_put_success(self, mock_httpx_client, mock_client):
        """Test successful single package write."""
        mock_response = Mock()
        mock_response.status_code = 200

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        mock_context.put.return_value = mock_response
        mock_httpx_client.return_value = mock_context

        data = {"package_name": "requests", "ecosystem": "python"}
        result = mock_client.put("python", "requests", data, "secret123")

        assert result is True
        mock_context.put.assert_called_once()
        call_kwargs = mock_context.put.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer secret123"

    @patch("httpx.Client")
    def test_put_unauthorized(self, mock_httpx_client, mock_client):
        """Test put with invalid authentication."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=Mock(), response=mock_response
        )

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        mock_context.put.return_value = mock_response
        mock_httpx_client.return_value = mock_context

        data = {"package_name": "requests"}
        result = mock_client.put("python", "requests", data, "wrong_secret")

        assert result is False

    @patch("httpx.Client")
    def test_batch_put_success(self, mock_httpx_client, mock_client):
        """Test successful batch write."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "written": 2}

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        mock_context.put.return_value = mock_response
        mock_httpx_client.return_value = mock_context

        entries = {
            "2.0:python:requests": {"package_name": "requests"},
            "2.0:python:django": {"package_name": "django"},
        }
        result = mock_client.batch_put(entries, "secret123")

        assert result == 2

    @patch("httpx.Client")
    def test_batch_put_empty(self, mock_httpx_client, mock_client):
        """Test batch_put with empty dict."""
        result = mock_client.batch_put({}, "secret123")
        assert result == 0

    @patch("httpx.Client")
    def test_batch_put_splits_large_batch(self, mock_httpx_client, mock_client):
        """Test that large batches are split into multiple requests."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"written": 50}

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        mock_context.put.return_value = mock_response
        mock_httpx_client.return_value = mock_context

        # Create 150 entries (should split into 2 batches)
        entries = {
            f"2.0:eco{i}:pkg{i}": {"package_name": f"pkg{i}"} for i in range(150)
        }
        result = mock_client.batch_put(entries, "secret123")

        # Should make 2 PUT requests
        assert mock_context.put.call_count == 2
        # Each batch returns 50, so total is 100
        assert result == 100

    @patch("httpx.Client")
    def test_batch_put_partial_failure(self, mock_httpx_client, mock_client):
        """Test batch_put continues after partial failure."""
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"written": 50}

        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=Mock(), response=mock_response_fail
        )

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        # First batch succeeds, second fails
        mock_context.put.side_effect = [mock_response_success, mock_response_fail]
        mock_httpx_client.return_value = mock_context

        entries = {f"2.0:eco{i}:pkg{i}": {"pkg": i} for i in range(150)}
        result = mock_client.batch_put(entries, "secret123")

        # Only first batch succeeded
        assert result == 50


def test_get_default_client():
    """Test default client creation."""
    from oss_sustain_guard.remote_cache import get_default_client

    client = get_default_client()
    assert isinstance(client, CloudflareKVClient)
    assert client.schema_version == "2.0"
