"""Shared HTTP client handling."""

from ssl import SSLContext
from typing import Union

import httpx

from oss_sustain_guard.config import get_verify_ssl

_async_http_client: httpx.AsyncClient | None = None
_http_client_verify_ssl: Union[SSLContext | bool, None] = None


async def _get_async_http_client() -> httpx.AsyncClient:
    """Get or create an asynchronous HTTP client with connection pooling."""
    global _async_http_client, _http_client_verify_ssl
    current_verify_ssl: SSLContext | bool = get_verify_ssl()
    if (
        _async_http_client is None
        or _async_http_client.is_closed
        or _http_client_verify_ssl != current_verify_ssl
    ):
        if _async_http_client is not None and not _async_http_client.is_closed:
            await _async_http_client.aclose()

        _async_http_client = httpx.AsyncClient(
            verify=current_verify_ssl,
            timeout=30,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
        )
        _http_client_verify_ssl = current_verify_ssl
    return _async_http_client


async def close_async_http_client():
    """Close the global asynchronous HTTP client. Call this when shutting down."""
    global _async_http_client, _http_client_verify_ssl
    if _async_http_client is not None and not _async_http_client.is_closed:
        await _async_http_client.aclose()
        _async_http_client = None
        _http_client_verify_ssl = None
