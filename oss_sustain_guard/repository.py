"""
Repository URL parsing utilities.
"""

from typing import NamedTuple
from urllib.parse import urlparse


class RepositoryReference(NamedTuple):
    """Unified repository reference for supported hosting providers."""

    provider: str
    host: str
    path: str
    owner: str
    name: str

    @property
    def url(self) -> str:
        """Return the canonical HTTPS URL for the repository."""
        return f"https://{self.host}/{self.path}"


def _sanitize_repository_segments(segments: list[str]) -> list[str]:
    """Trim repository path segments to the repository root."""
    stop_tokens = {
        "-",
        "tree",
        "blob",
        "issues",
        "pull",
        "merge_requests",
        "releases",
        "commit",
        "commits",
    }
    cleaned: list[str] = []
    for segment in segments:
        if segment in stop_tokens:
            break
        cleaned.append(segment)
    return cleaned


def parse_repository_url(url: str) -> RepositoryReference | None:
    """
    Parse a repository URL and return a repository reference.

    Supports GitHub and GitLab URLs, including SSH-style URLs.
    """
    if not url:
        return None

    normalized = url.strip().rstrip("/")

    if normalized.startswith("git@") and ":" in normalized:
        host_part, path_part = normalized.split(":", 1)
        host = host_part.split("@", 1)[-1]
        path = path_part
    else:
        parsed = urlparse(
            normalized if "://" in normalized else f"https://{normalized}"
        )
        host = parsed.netloc
        path = parsed.path.lstrip("/")

    if not host:
        return None

    if "@" in host:
        host = host.split("@", 1)[-1]
    host = host.lower()

    supported_hosts = {"github.com": "github", "gitlab.com": "gitlab"}
    provider = supported_hosts.get(host)
    if not provider:
        return None

    if path.endswith(".git"):
        path = path[:-4]

    segments = [segment for segment in path.split("/") if segment]
    segments = _sanitize_repository_segments(segments)
    if provider == "github" and len(segments) < 2:
        return None
    if provider == "gitlab" and len(segments) < 2:
        return None

    owner = segments[0]
    name = segments[-1]
    repo_path = "/".join(segments)

    return RepositoryReference(
        provider=provider,
        host=host,
        path=repo_path,
        owner=owner,
        name=name,
    )
