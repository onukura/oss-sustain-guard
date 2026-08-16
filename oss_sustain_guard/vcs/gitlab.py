"""
GitLab VCS provider implementation for OSS Sustain Guard.

This module implements the GitLab-specific VCS provider using the GitLab GraphQL API
to fetch repository data for sustainability analysis.
"""

import os
from typing import Any

import httpx
from dotenv import load_dotenv

from oss_sustain_guard.http_client import _get_async_http_client
from oss_sustain_guard.vcs.base import BaseVCSProvider, VCSRepositoryData

# Load environment variables
load_dotenv()

# GitLab API endpoint
GITLAB_GRAPHQL_API = "https://gitlab.com/api/graphql"

# Sample size constants by scan depth
SCAN_DEPTH_LIMITS = {
    "shallow": {
        "commits": 50,
        "merged_mrs": 20,
        "closed_mrs": 20,
        "open_issues": 10,
        "closed_issues": 20,
        "releases": 5,
        "forks": 10,
        "reviews": 3,
    },
    "default": {
        "commits": 100,
        "merged_mrs": 50,
        "closed_mrs": 50,
        "open_issues": 20,
        "closed_issues": 50,
        "releases": 10,
        "forks": 20,
        "reviews": 10,
    },
    "deep": {
        "commits": 100,
        "merged_mrs": 100,
        "closed_mrs": 100,
        "open_issues": 50,
        "closed_issues": 100,
        "releases": 20,
        "forks": 50,
        "reviews": 20,
    },
    "very_deep": {
        "commits": 100,
        "merged_mrs": 100,
        "closed_mrs": 100,
        "open_issues": 100,
        "closed_issues": 100,
        "releases": 50,
        "forks": 100,
        "reviews": 50,
    },
}

# Legacy constant for backward compatibility
GRAPHQL_SAMPLE_LIMITS = SCAN_DEPTH_LIMITS["default"]


class GitLabProvider(BaseVCSProvider):
    """GitLab VCS provider using GraphQL API."""

    def __init__(self, token: str | None = None):
        """
        Initialize GitLab provider.

        Args:
            token: GitLab Personal Access Token. If not provided, reads from
                   GITLAB_TOKEN environment variable.

        Raises:
            ValueError: If token is not provided and GITLAB_TOKEN env var is not set
        """
        self.token = token or os.getenv("GITLAB_TOKEN")
        if not self.token or len(self.token) == 0:
            raise ValueError(
                "GITLAB_TOKEN is required for GitLab provider.\n"
                "\n"
                "To get started:\n"
                "1. Create a GitLab Personal Access Token:\n"
                "   → https://gitlab.com/-/user_settings/personal_access_tokens\n"
                "2. Select scopes: 'read_api' and 'read_repository'\n"
                "3. Set the token:\n"
                "   export GITLAB_TOKEN='your_token_here'  # Linux/macOS\n"
                "   or add to your .env file: GITLAB_TOKEN=your_token_here\n"
            )

    def get_platform_name(self) -> str:
        """Return 'gitlab' as the platform identifier."""
        return "gitlab"

    def validate_credentials(self) -> bool:
        """Check if GitLab token is configured."""
        return self.token is not None and len(self.token) > 0

    def get_repository_url(self, owner: str, repo: str) -> str:
        """Construct GitLab repository URL."""
        return f"https://gitlab.com/{owner}/{repo}"

    async def get_repository_data(
        self,
        owner: str,
        repo: str,
        scan_depth: str = "default",
        days_lookback: int | None = None,
        time_window: tuple[str, str] | None = None,
    ) -> VCSRepositoryData:
        """
        Fetch repository data from GitLab GraphQL API.

        Args:
            owner: GitLab repository owner (username or organization)
            repo: GitLab repository name
            scan_depth: Sampling depth - "shallow", "default", or "deep"
            days_lookback: Optional time filter (days to look back), None = no limit
            time_window: Optional (since, until) ISO timestamp tuple for precise window.
                        If provided, takes precedence over days_lookback.

        Returns:
            Normalized VCSRepositoryData structure

        Raises:
            ValueError: If repository not found or is inaccessible
            httpx.HTTPStatusError: If GitLab API returns an error
        """
        from datetime import datetime, timedelta, timezone

        # Get sample limits based on scan depth
        limits = SCAN_DEPTH_LIMITS.get(scan_depth, SCAN_DEPTH_LIMITS["default"])

        # Determine time filter parameters
        since_date = None
        until_date = None

        if time_window is not None:
            # Use explicit time window (for trend analysis)
            since_date, until_date = time_window
        elif days_lookback is not None:
            # Use days_lookback (for regular analysis)
            since_date = (
                datetime.now(timezone.utc) - timedelta(days=days_lookback)
            ).isoformat()

        # GitLab uses full path for project queries
        full_path = f"{owner}/{repo}"
        query = self._get_graphql_query(limits)
        variables = {"fullPath": full_path}
        raw_data = await self._query_graphql(query, variables)

        if "project" not in raw_data or raw_data["project"] is None:
            raise ValueError(f"Repository {owner}/{repo} not found or is inaccessible.")

        project_info = raw_data["project"]
        return await self._normalize_gitlab_data(
            project_info, owner, repo, since_date, limits, until_date
        )

    async def _query_graphql(
        self, query: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute GraphQL query against GitLab API.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Response data dictionary

        Raises:
            httpx.HTTPStatusError: If API returns an error
        """
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        client = await _get_async_http_client()
        response = await client.post(
            GITLAB_GRAPHQL_API,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise httpx.HTTPStatusError(
                f"GitLab API Errors: {data['errors']}",
                request=response.request,
                response=response,
            )

        return data.get("data", {})

    def _get_graphql_query(self, limits: dict[str, int]) -> str:
        """
        Return the GraphQL query to fetch project metrics.

        Args:
            limits: Dictionary with sample size limits for each data type
        """
        return f"""
        query GetProject($fullPath: ID!) {{
          project(fullPath: $fullPath) {{
            archived
            lastActivityAt
            namespace {{
              fullPath
              name
            }}
            repository {{
              rootRef
            }}
            mergeRequests(first: {limits["merged_mrs"]}, state: merged, sort: UPDATED_DESC) {{
              edges {{
                node {{
                  mergedAt
                  createdAt
                  mergeUser {{
                    username
                  }}
                  approvedBy {{
                    nodes {{
                      createdAt
                    }}
                  }}
                }}
              }}
              pageInfo {{
                hasNextPage
              }}
              count
            }}
            closedMergeRequests: mergeRequests(first: {limits["closed_mrs"]}, state: closed, sort: UPDATED_DESC) {{
              edges {{
                node {{
                  closedAt
                  createdAt
                  state
                }}
              }}
              count
            }}
            releases(first: {limits["releases"]}, sort: CREATED_DESC) {{
              edges {{
                node {{
                  releasedAt
                  tagName
                }}
              }}
            }}
            issues(first: {limits["open_issues"]}, state: opened, sort: CREATED_DESC) {{
              edges {{
                node {{
                  createdAt
                  notes(first: 1) {{
                    edges {{
                      node {{
                        createdAt
                      }}
                    }}
                  }}
                }}
              }}
            }}
            closedIssues: issues(first: {limits["closed_issues"]}, state: closed, sort: UPDATED_DESC) {{
              edges {{
                node {{
                  createdAt
                  closedAt
                  updatedAt
                }}
              }}
              count
            }}
            issuesEnabled
            wikiEnabled
            starCount
            forksCount
            description
            webUrl
          }}
        }}
        """

    async def _normalize_gitlab_data(
        self,
        project_info: dict[str, Any],
        owner: str,
        repo: str,
        since_date: str | None = None,
        limits: dict[str, int] | None = None,
        until_date: str | None = None,
    ) -> VCSRepositoryData:
        """
        Normalize GitLab GraphQL response to VCSRepositoryData format.

        Args:
            project_info: GitLab project data from GraphQL response
            owner: Repository owner
            repo: Repository name
            since_date: ISO format date string for time filtering (start), None = no limit
            limits: Sample size limits for data fetching
            until_date: ISO format date string for time filtering (end), None = no limit

        Returns:
            Normalized VCSRepositoryData structure
        """
        from datetime import datetime

        # For backward compatibility with client-side filtering (MRs and issues)
        cutoff_date = None
        until_cutoff_date = None

        if since_date:
            cutoff_date = datetime.fromisoformat(since_date.replace("Z", "+00:00"))
        if until_date:
            until_cutoff_date = datetime.fromisoformat(
                until_date.replace("Z", "+00:00")
            )

        # Extract namespace (owner) information
        namespace = project_info.get("namespace", {})
        owner_login = namespace.get("fullPath", owner).split("/")[0]
        owner_name = namespace.get("name")
        owner_type = "Group" if "/" in namespace.get("fullPath", "") else "User"

        # Extract repository metadata
        star_count = project_info.get("starCount", 0)
        description = project_info.get("description")
        homepage_url = None
        topics = project_info.get("topics", []) or []
        default_branch = project_info.get("repository", {}).get("rootRef")
        watchers_count = 0
        readme_size = None
        contributing_file_size = None
        full_path = f"{owner}/{repo}"

        if default_branch:
            refs_to_try = [default_branch]
        else:
            refs_to_try = []
        for fallback_ref in ("main", "master"):
            if fallback_ref not in refs_to_try:
                refs_to_try.append(fallback_ref)

        for ref in refs_to_try:
            if readme_size is None:
                readme_size = await self._fetch_first_matching_file_size(
                    full_path,
                    ref,
                    ["README.md", "readme.md", "README"],
                )
            if contributing_file_size is None:
                contributing_file_size = await self._fetch_first_matching_file_size(
                    full_path,
                    ref,
                    ["CONTRIBUTING.md", "CONTRIBUTING.MD", "CONTRIBUTING"],
                )
            if readme_size is not None and contributing_file_size is not None:
                break

        # Fetch commits separately (GitLab GraphQL doesn't support commits in project query easily)
        # Pass since_date and limits to use API-level filtering
        commits = []
        total_commits = 0
        try:
            per_page = limits.get("commits", 100) if limits else 100
            commits_data = await self._fetch_commits(
                f"{owner}/{repo}", since=since_date, per_page=per_page
            )
            commits = commits_data.get("commits", [])
            total_commits = commits_data.get("total_commits", len(commits))
        except Exception:
            # If commits fetch fails, continue without commit data
            pass

        # Extract merge requests (GitLab's equivalent of pull requests)
        merged_mrs_data = project_info.get("mergeRequests", {})
        all_merged_prs = [
            self._normalize_merge_request(edge["node"])
            for edge in merged_mrs_data.get("edges", [])
        ]

        # Apply time filter if specified
        if cutoff_date or until_cutoff_date:
            merged_prs = []
            for pr in all_merged_prs:
                merged_at = pr.get("mergedAt")
                if not merged_at:
                    continue
                merged_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                if cutoff_date and merged_dt < cutoff_date:
                    continue
                if until_cutoff_date and merged_dt > until_cutoff_date:
                    continue
                merged_prs.append(pr)
        else:
            merged_prs = all_merged_prs

        closed_mrs_data = project_info.get("closedMergeRequests", {})
        all_closed_prs = [
            self._normalize_merge_request(edge["node"])
            for edge in closed_mrs_data.get("edges", [])
        ]

        # Apply time filter if specified
        if cutoff_date or until_cutoff_date:
            closed_prs = []
            for pr in all_closed_prs:
                closed_at = pr.get("closedAt")
                if not closed_at:
                    continue
                closed_dt = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
                if cutoff_date and closed_dt < cutoff_date:
                    continue
                if until_cutoff_date and closed_dt > until_cutoff_date:
                    continue
                closed_prs.append(pr)
        else:
            closed_prs = all_closed_prs

        total_merged_prs = merged_mrs_data.get("count", len(merged_prs))

        # Extract releases
        releases_data = project_info.get("releases", {})
        releases = [
            self._normalize_release(edge["node"])
            for edge in releases_data.get("edges", [])
        ]

        # Extract issues
        open_issues_data = project_info.get("issues", {})
        open_issues = [
            self._normalize_issue(edge["node"])
            for edge in open_issues_data.get("edges", [])
        ]
        open_issues_count = open_issues_data.get("count", len(open_issues))

        closed_issues_data = project_info.get("closedIssues", {})
        closed_issues = [
            self._normalize_issue(edge["node"])
            for edge in closed_issues_data.get("edges", [])
        ]
        rest_closed_issues = await self._fetch_closed_issues(full_path)
        if rest_closed_issues is not None:
            closed_issues = rest_closed_issues
        total_closed_issues = closed_issues_data.get("count", len(closed_issues))

        # GitLab doesn't expose vulnerability alerts via GraphQL (requires REST API)
        vulnerability_alerts = None

        # GitLab doesn't have built-in security policy detection via GraphQL
        has_security_policy = False

        # GitLab doesn't have built-in code of conduct detection
        code_of_conduct = None

        # GitLab doesn't expose license info via GraphQL easily
        license_info = None

        # Extract funding links (GitLab doesn't have built-in funding links)
        funding_links: list[dict[str, str]] = []

        # Fetch forks data
        forks: list[dict[str, Any]] = []
        total_forks = project_info.get("forksCount", 0)
        try:
            if total_forks > 0:
                forks_data = await self._fetch_forks(f"{owner}/{repo}")
                forks = forks_data.get("forks", [])
        except Exception:
            # If forks fetch fails, continue with just the count
            pass

        # GitLab CI/CD status (would require separate query)
        ci_status = None

        # Sample counts
        sample_counts = {
            "commits": len(commits),
            "merged_prs": len(merged_prs),
            "closed_prs": len(closed_prs),
            "open_issues": len(open_issues),
            "closed_issues": len(closed_issues),
            "releases": len(releases),
            "vulnerability_alerts": 0,
            "forks": len(forks),
        }

        return VCSRepositoryData(
            is_archived=project_info.get("archived", False),
            pushed_at=project_info.get("lastActivityAt"),
            owner_type=owner_type,
            owner_login=owner_login,
            owner_name=owner_name,
            star_count=star_count,
            description=description,
            homepage_url=homepage_url,
            topics=topics,
            readme_size=readme_size,
            contributing_file_size=contributing_file_size,
            default_branch=default_branch,
            watchers_count=watchers_count,
            open_issues_count=open_issues_count,
            language=None,
            commits=commits,
            total_commits=total_commits,
            merged_prs=merged_prs,
            closed_prs=closed_prs,
            total_merged_prs=total_merged_prs,
            releases=releases,
            open_issues=open_issues,
            closed_issues=closed_issues,
            total_closed_issues=total_closed_issues,
            vulnerability_alerts=vulnerability_alerts,
            has_security_policy=has_security_policy,
            code_of_conduct=code_of_conduct,
            license_info=license_info,
            has_wiki=project_info.get("wikiEnabled", False),
            has_issues=project_info.get("issuesEnabled", True),
            has_discussions=False,  # GitLab doesn't expose discussions in this way
            funding_links=funding_links,
            forks=forks,
            total_forks=total_forks,
            ci_status=ci_status,
            sample_counts=sample_counts,
            raw_data=None,  # Don't use raw_data to force proper reconstruction
        )

    async def _fetch_first_matching_file_size(
        self, full_path: str, ref: str, candidates: list[str]
    ) -> int | None:
        for file_path in candidates:
            size = await self._fetch_repository_file_size(full_path, ref, file_path)
            if size is not None:
                return size
        return None

    async def _fetch_repository_file_size(
        self, full_path: str, ref: str, file_path: str
    ) -> int | None:
        """
        Fetch repository file size using GitLab REST API.

        Args:
            full_path: Full project path (owner/repo)
            ref: Branch or tag name
            file_path: File path in repository

        Returns:
            File size in bytes if file exists
        """
        try:
            import urllib.parse

            encoded_path = urllib.parse.quote(full_path, safe="")
            encoded_file = urllib.parse.quote(file_path, safe="")
            url = (
                f"https://gitlab.com/api/v4/projects/{encoded_path}"
                f"/repository/files/{encoded_file}"
            )
            headers = {"Authorization": f"Bearer {self.token}"}
            client = await _get_async_http_client()

            response = await client.get(
                url,
                headers=headers,
                params={"ref": ref},
                timeout=30,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            size = data.get("size")
            if isinstance(size, int):
                return size
            if isinstance(size, str):
                try:
                    return int(size)
                except ValueError:
                    return None
            return None
        except Exception as exc:
            print(
                "Warning: Failed to fetch file size "
                f"for {full_path}/{file_path}@{ref}: {exc}"
            )
            return None

    async def _fetch_closed_issues(self, full_path: str) -> list[dict[str, Any]] | None:
        """
        Fetch closed issues using GitLab REST API to capture close actors.

        Args:
            full_path: Full project path (owner/repo)

        Returns:
            List of normalized closed issue objects or None on failure
        """
        try:
            import urllib.parse

            encoded_path = urllib.parse.quote(full_path, safe="")
            url = f"https://gitlab.com/api/v4/projects/{encoded_path}/issues"
            headers = {"Authorization": f"Bearer {self.token}"}
            client = await _get_async_http_client()

            response = await client.get(
                url,
                headers=headers,
                params={
                    "state": "closed",
                    "order_by": "updated_at",
                    "sort": "desc",
                    "per_page": 50,
                    "page": 1,
                },
                timeout=30,
            )
            response.raise_for_status()
            issues_data = response.json()
            if not isinstance(issues_data, list):
                return []

            return [self._normalize_issue(issue) for issue in issues_data]
        except Exception as exc:
            print(f"Warning: Failed to fetch closed issues for {full_path}: {exc}")
            return None

    async def _fetch_commits(
        self, full_path: str, since: str | None = None, per_page: int = 100
    ) -> dict[str, Any]:
        """
        Fetch commit data using GitLab REST API.

        Args:
            full_path: Full project path (owner/repo)
            since: ISO 8601 format date string to get commits after this date
            per_page: Number of commits to fetch (default: 100)

        Returns:
            Dictionary with commits list and total count
        """
        try:
            # URL encode the project path
            import urllib.parse

            encoded_path = urllib.parse.quote(full_path, safe="")

            # Fetch commits via REST API with optional time filtering
            url = (
                f"https://gitlab.com/api/v4/projects/{encoded_path}/repository/commits"
            )
            headers = {"Authorization": f"Bearer {self.token}"}
            client = await _get_async_http_client()

            # Build params with optional 'since' parameter
            params: dict[str, Any] = {"per_page": per_page, "page": 1}
            if since:
                params["since"] = since

            response = await client.get(
                url,
                headers=headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            commits_data = response.json()

            # Normalize commits to GitHub format
            commits = [
                {
                    "committedDate": commit.get("committed_date"),
                    "author": {
                        "name": commit.get("author_name"),
                        "email": commit.get("author_email"),
                        "user": {"login": commit.get("author_email", "").split("@")[0]}
                        if commit.get("author_email")
                        else None,
                    },
                }
                for commit in commits_data
            ]

            # Get total commit count from project stats
            stats_url = f"https://gitlab.com/api/v4/projects/{encoded_path}"
            stats_response = await client.get(
                stats_url,
                headers=headers,
                timeout=30,
            )
            stats_response.raise_for_status()
            project_data = stats_response.json()

            # Get statistics if available
            statistics = project_data.get("statistics", {})
            total_commits = statistics.get("commit_count", len(commits))

            return {"commits": commits, "total_commits": total_commits}

        except Exception as e:
            # If commit fetch fails, return empty data
            # Log the error but don't fail the entire analysis
            print(f"Warning: Failed to fetch commits for {full_path}: {e}")
            return {"commits": [], "total_commits": 0}

    async def _fetch_forks(self, full_path: str) -> dict[str, Any]:
        """
        Fetch fork data using GitLab REST API.

        Args:
            full_path: Full project path (owner/repo)

        Returns:
            Dictionary with forks list
        """
        try:
            import urllib.parse

            encoded_path = urllib.parse.quote(full_path, safe="")

            # Fetch forks via REST API (first 20 forks)
            url = f"https://gitlab.com/api/v4/projects/{encoded_path}/forks"
            headers = {"Authorization": f"Bearer {self.token}"}
            client = await _get_async_http_client()

            response = await client.get(
                url,
                headers=headers,
                params={"per_page": 20, "page": 1},
                timeout=30,
            )
            response.raise_for_status()
            forks_data = response.json()

            # Normalize forks to GitHub format
            forks = [self._normalize_fork(fork) for fork in forks_data]

            return {"forks": forks}

        except Exception as e:
            print(f"Warning: Failed to fetch forks for {full_path}: {e}")
            return {"forks": []}

    def _normalize_merge_request(self, mr_node: dict[str, Any]) -> dict[str, Any]:
        """Normalize GitLab merge request to GitHub PR format."""
        return {
            "mergedAt": mr_node.get("mergedAt"),
            "closedAt": mr_node.get("closedAt"),
            "createdAt": mr_node.get("createdAt"),
            "merged": mr_node.get("state") == "merged",
            "mergedBy": {"login": mr_node.get("mergeUser", {}).get("username", "")}
            if mr_node.get("mergeUser")
            else None,
            "reviews": {
                "totalCount": len(mr_node.get("approvedBy", {}).get("nodes", [])),
                "edges": [
                    {"node": {"createdAt": node["createdAt"]}}
                    for node in mr_node.get("approvedBy", {}).get("nodes", [])
                ],
            },
        }

    def _normalize_release(self, release_node: dict[str, Any]) -> dict[str, Any]:
        """Normalize GitLab release to GitHub release format."""
        return {
            "publishedAt": release_node.get("releasedAt"),
            "tagName": release_node.get("tagName"),
        }

    def _normalize_issue(self, issue_node: dict[str, Any]) -> dict[str, Any]:
        """Normalize GitLab issue to GitHub issue format."""
        created_at = issue_node.get("createdAt") or issue_node.get("created_at")
        closed_at = issue_node.get("closedAt") or issue_node.get("closed_at")
        updated_at = issue_node.get("updatedAt") or issue_node.get("updated_at")

        notes = issue_node.get("notes", {})
        note_edges = []
        if isinstance(notes, dict):
            note_edges = [
                {"node": edge.get("node", {})}
                for edge in notes.get("edges", [])
                if isinstance(edge, dict)
            ]

        closed_by = issue_node.get("closedBy") or issue_node.get("closed_by")
        closed_by_login = None
        if isinstance(closed_by, dict):
            closed_by_login = closed_by.get("login") or closed_by.get("username")

        normalized = {
            "createdAt": created_at,
            "closedAt": closed_at,
            "updatedAt": updated_at,
            "comments": {"edges": note_edges},
        }
        if closed_by_login:
            normalized["closedBy"] = {"login": closed_by_login}
        return normalized

    def _normalize_fork(self, fork_node: dict[str, Any]) -> dict[str, Any]:
        """Normalize GitLab fork (from REST API) to GitHub fork format."""
        # Extract owner login from namespace
        namespace = fork_node.get("namespace", {})
        owner_login = (
            namespace.get("path")
            or namespace.get("fullPath", "").split("/")[0]
            or fork_node.get("owner", {}).get("username", "")
        )

        return {
            "createdAt": fork_node.get("createdAt") or fork_node.get("created_at"),
            "pushedAt": fork_node.get("lastActivityAt")
            or fork_node.get("last_activity_at"),
            "owner": {"login": owner_login},
        }


PROVIDER = GitLabProvider
