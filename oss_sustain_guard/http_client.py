"""Shared HTTP client handling."""

import httpx

from oss_sustain_guard.config import get_verify_ssl

_http_client: httpx.Client | None = None
_http_client_verify_ssl: bool | None = None


def _get_http_client() -> httpx.Client:
    """Get or create a global HTTP client with connection pooling.

    Recreates the client if SSL verification setting has changed.
    """
    global _http_client, _http_client_verify_ssl
    current_verify_ssl = get_verify_ssl()

    # Recreate client if setting changed or client is closed/None
    if (
        _http_client is None
        or _http_client.is_closed
        or _http_client_verify_ssl != current_verify_ssl
    ):
        # Close existing client if necessary
        if _http_client is not None and not _http_client.is_closed:
            _http_client.close()

        _http_client = httpx.Client(
            verify=current_verify_ssl,
            timeout=10,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
        )
        _http_client_verify_ssl = current_verify_ssl
    return _http_client


def close_http_client():
    """Close the global HTTP client. Call this when shutting down."""
    global _http_client, _http_client_verify_ssl
    if _http_client is not None and not _http_client.is_closed:
        _http_client.close()
        _http_client = None
        _http_client_verify_ssl = None
