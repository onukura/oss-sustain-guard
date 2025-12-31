"""Libraries.io API integration."""

import os
from typing import Any

import httpx
from rich.console import Console

from oss_sustain_guard.http_client import _get_http_client

LIBRARIESIO_API_BASE = "https://libraries.io/api"
console = Console()


def query_librariesio_api(platform: str, package_name: str) -> dict[str, Any] | None:
    """
    Queries Libraries.io API for package information including dependents count.

    Args:
        platform: Package platform (e.g., 'pypi', 'npm', 'cargo', 'maven')
        package_name: Package name

    Returns:
        Package information dict or None if API key not set or request fails

    Note:
        Requires LIBRARIESIO_API_KEY environment variable.
        Get free API key at: https://libraries.io/api
    """
    api_key = os.getenv("LIBRARIESIO_API_KEY")
    if not api_key:
        return None

    url = f"{LIBRARIESIO_API_BASE}/{platform}/{package_name}"
    params = {"api_key": api_key}

    try:
        client = _get_http_client()
        response = client.get(url, params=params, timeout=10)
        if response.status_code == 404:
            console.print(f"Warning: Package {package_name} not found on Libraries.io.")
            return None
        response.raise_for_status()
        console.print(f"Info: Queried Libraries.io for {package_name} on {platform}.")
        return response.json()
    except httpx.RequestError:
        console.print("Warning: Libraries.io API request failed.")
        return None
