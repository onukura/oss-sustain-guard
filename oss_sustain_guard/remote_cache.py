"""
Remote cache client for Cloudflare KV.

Provides shared cache access for package sustainability analysis results.
"""

import json
import os
from typing import Any

import httpx

from oss_sustain_guard.config import get_verify_ssl
from oss_sustain_guard.schema_migrations import CURRENT_SCHEMA_VERSION

# Default Worker URL (can be overridden with environment variable)
DEFAULT_WORKER_URL = os.environ.get(
    "CLOUDFLARE_WORKER_URL",
    "https://oss-sustain-guard-cache.workers.dev",  # Replace after deployment
)


class CloudflareKVClient:
    """Client for Cloudflare KV shared cache."""

    def __init__(
        self,
        worker_url: str = DEFAULT_WORKER_URL,
        schema_version: str = CURRENT_SCHEMA_VERSION,
        timeout: int = 5,
    ):
        """
        Initialize Cloudflare KV client.

        Args:
            worker_url: Cloudflare Worker URL.
            schema_version: Schema version for cache keys.
            timeout: Request timeout in seconds (default: 5 for reads).
        """
        self.worker_url = worker_url.rstrip("/")
        self.schema_version = schema_version
        self.timeout = timeout
        self.verify_ssl = get_verify_ssl()

    def _make_key(self, ecosystem: str, package_name: str) -> str:
        """
        Generate cache key.

        Format: {schema_version}:{ecosystem}:{package_name}
        Example: 2.0:python:requests

        Args:
            ecosystem: Ecosystem name (python, javascript, etc.).
            package_name: Package name.

        Returns:
            Cache key string.
        """
        return f"{self.schema_version}:{ecosystem}:{package_name}"

    def get(self, ecosystem: str, package_name: str) -> dict[str, Any] | None:
        """
        Get single package data from cache.

        Args:
            ecosystem: Ecosystem name.
            package_name: Package name.

        Returns:
            Package data dict or None if not found/error.
        """
        key = self._make_key(ecosystem, package_name)
        url = f"{self.worker_url}/{key}"

        try:
            with httpx.Client(verify=self.verify_ssl) as client:
                response = client.get(url, timeout=self.timeout)

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                return response.json()

        except (httpx.HTTPError, json.JSONDecodeError):
            # Silently fail - allows fallback to other sources
            return None

    def batch_get(self, packages: list[tuple[str, str]]) -> dict[str, dict[str, Any]]:
        """
        Get multiple packages from cache in single request.

        Args:
            packages: List of (ecosystem, package_name) tuples.

        Returns:
            Dictionary mapping keys to package data.
            Missing packages are not included in result.
        """
        if not packages:
            return {}

        # Generate keys
        keys = [self._make_key(eco, pkg) for eco, pkg in packages]

        # Split into batches of 100 (Worker limit)
        batch_size = 100
        all_results = {}

        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i : i + batch_size]

            try:
                with httpx.Client(verify=self.verify_ssl) as client:
                    response = client.post(
                        f"{self.worker_url}/batch",
                        json={"keys": batch_keys},
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    batch_results = response.json()
                    all_results.update(batch_results)

            except (httpx.HTTPError, json.JSONDecodeError):
                # Silently fail for this batch
                continue

        return all_results

    def put(
        self, ecosystem: str, package_name: str, data: dict[str, Any], secret: str
    ) -> bool:
        """
        Store single package data to cache (requires authentication).

        Args:
            ecosystem: Ecosystem name.
            package_name: Package name.
            data: Package data to store.
            secret: Write secret for authentication.

        Returns:
            True if successful, False otherwise.
        """
        key = self._make_key(ecosystem, package_name)
        url = f"{self.worker_url}/{key}"

        try:
            with httpx.Client(verify=self.verify_ssl) as client:
                response = client.put(
                    url,
                    json=data,
                    headers={"Authorization": f"Bearer {secret}"},
                    timeout=30,  # Longer timeout for writes
                )
                response.raise_for_status()
                return True

        except httpx.HTTPError:
            return False

    def batch_put(self, entries: dict[str, dict[str, Any]], secret: str) -> int:
        """
        Store multiple packages to cache in single request (requires authentication).

        Args:
            entries: Dictionary mapping keys to package data.
                     Keys should be in format: {schema_version}:{ecosystem}:{package_name}
            secret: Write secret for authentication.

        Returns:
            Number of packages successfully written.
        """
        if not entries:
            return 0

        # Split into batches of 100 (Worker limit)
        batch_size = 100
        keys = list(entries.keys())
        total_written = 0

        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i : i + batch_size]
            batch_entries = {k: entries[k] for k in batch_keys}

            try:
                with httpx.Client(verify=self.verify_ssl) as client:
                    response = client.put(
                        f"{self.worker_url}/batch",
                        json={"entries": batch_entries},
                        headers={"Authorization": f"Bearer {secret}"},
                        timeout=30,  # Longer timeout for writes
                    )
                    response.raise_for_status()
                    result = response.json()
                    total_written += result.get("written", 0)

            except httpx.HTTPError:
                # Continue with next batch even if this one fails
                continue

        return total_written


def get_default_client() -> CloudflareKVClient:
    """
    Get a default CloudflareKVClient instance.

    Returns:
        Configured CloudflareKVClient instance.
    """
    return CloudflareKVClient()
