"""
GitLab VCS provider implementation for OSS Sustain Guard.

This module implements the GitLab-specific VCS provider using the GitLab GraphQL API
to fetch repository data for sustainability analysis.
"""

import os
from typing import Any

import httpx
from dotenv import load_dotenv

from oss_sustain_guard.http_client import _get_http_client
from oss_sustain_guard.vcs.base import BaseVCSProvider, VCSRepositoryData

# Load environment variables
load_dotenv()

# GitLab API endpoint
GITLAB_GRAPHQL_API = "https://gitlab.com/api/graphql"

# Sample size constants from GraphQL queries
GRAPHQL_SAMPLE_LIMITS = {
    "commits": 100,
    "merged_mrs": 50,
    "closed_mrs": 50,
    "open_issues": 20,
    "closed_issues": 50,
    "releases": 10,
    "forks": 20,
}


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

    def get_repository_data(self, owner: str, repo: str) -> VCSRepositoryData:
        """
        Fetch repository data from GitLab GraphQL API.

        Args:
            owner: GitLab repository owner (username or organization)
            repo: GitLab repository name

        Returns:
            Normalized VCSRepositoryData structure

        Raises:
            ValueError: If repository not found or is inaccessible
            httpx.HTTPStatusError: If GitLab API returns an error
        """
        # GitLab uses full path for project queries
        full_path = f"{owner}/{repo}"
        query = self._get_graphql_query()
        variables = {"fullPath": full_path}
        raw_data = self._query_graphql(query, variables)

        if "project" not in raw_data or raw_data["project"] is None:
            raise ValueError(f"Repository {owner}/{repo} not found or is inaccessible.")

        project_info = raw_data["project"]
        return self._normalize_gitlab_data(project_info, owner, repo)

    def _query_graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
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
        client = _get_http_client()
        response = client.post(
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

    def _get_graphql_query(self) -> str:
        """Return the GraphQL query to fetch project metrics."""
        return """
        query GetProject($fullPath: ID!) {
          project(fullPath: $fullPath) {
            archived
            lastActivityAt
            namespace {
              fullPath
              name
            }
            repository {
              rootRef
            }
            mergeRequests(first: 50, state: merged, sort: UPDATED_DESC) {
              edges {
                node {
                  mergedAt
                  createdAt
                  mergeUser {
                    username
                  }
                  approvedBy {
                    nodes {
                      createdAt
                    }
                  }
                }
              }
              pageInfo {
                hasNextPage
              }
              count
            }
            closedMergeRequests: mergeRequests(first: 50, state: closed, sort: UPDATED_DESC) {
              edges {
                node {
                  closedAt
                  createdAt
                  state
                }
              }
              count
            }
            releases(first: 10, sort: CREATED_DESC) {
              edges {
                node {
                  releasedAt
                  tagName
                }
              }
            }
            issues(first: 20, state: opened, sort: CREATED_DESC) {
              edges {
                node {
                  createdAt
                  notes(first: 1) {
                    edges {
                      node {
                        createdAt
                      }
                    }
                  }
                }
              }
            }
            closedIssues: issues(first: 50, state: closed, sort: UPDATED_DESC) {
              edges {
                node {
                  createdAt
                  closedAt
                  updatedAt
                }
              }
              count
            }
            issuesEnabled
            wikiEnabled
            starCount
            forksCount
            description
            webUrl
          }
        }
        """

    def _normalize_gitlab_data(
        self, project_info: dict[str, Any], owner: str, repo: str
    ) -> VCSRepositoryData:
        """
        Normalize GitLab GraphQL response to VCSRepositoryData format.

        Args:
            project_info: GitLab project data from GraphQL response
            owner: Repository owner
            repo: Repository name

        Returns:
            Normalized VCSRepositoryData structure
        """
        # Extract namespace (owner) information
        namespace = project_info.get("namespace", {})
        owner_login = namespace.get("fullPath", owner).split("/")[0]
        owner_name = namespace.get("name")
        owner_type = "Group" if "/" in namespace.get("fullPath", "") else "User"

        # Fetch commits separately (GitLab GraphQL doesn't support commits in project query easily)
        commits = []
        total_commits = 0
        try:
            commits_data = self._fetch_commits(f"{owner}/{repo}")
            commits = commits_data.get("commits", [])
            total_commits = commits_data.get("total_commits", len(commits))
        except Exception:
            # If commits fetch fails, continue without commit data
            pass

        # Extract merge requests (GitLab's equivalent of pull requests)
        merged_mrs_data = project_info.get("mergeRequests", {})
        merged_prs = [
            self._normalize_merge_request(edge["node"])
            for edge in merged_mrs_data.get("edges", [])
        ]

        closed_mrs_data = project_info.get("closedMergeRequests", {})
        closed_prs = [
            self._normalize_merge_request(edge["node"])
            for edge in closed_mrs_data.get("edges", [])
        ]

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

        closed_issues_data = project_info.get("closedIssues", {})
        closed_issues = [
            self._normalize_issue(edge["node"])
            for edge in closed_issues_data.get("edges", [])
        ]
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
                forks_data = self._fetch_forks(f"{owner}/{repo}")
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

    def _fetch_commits(self, full_path: str) -> dict[str, Any]:
        """
        Fetch commit data using GitLab REST API.

        Args:
            full_path: Full project path (owner/repo)

        Returns:
            Dictionary with commits list and total count
        """
        try:
            # URL encode the project path
            import urllib.parse

            encoded_path = urllib.parse.quote(full_path, safe="")

            # Fetch commits via REST API (first 100 commits)
            url = (
                f"https://gitlab.com/api/v4/projects/{encoded_path}/repository/commits"
            )
            headers = {"Authorization": f"Bearer {self.token}"}
            client = _get_http_client()

            response = client.get(
                url,
                headers=headers,
                params={"per_page": 100, "page": 1},
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
            stats_response = client.get(
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

    def _fetch_forks(self, full_path: str) -> dict[str, Any]:
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
            client = _get_http_client()

            response = client.get(
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
        return {
            "createdAt": issue_node.get("createdAt"),
            "closedAt": issue_node.get("closedAt"),
            "updatedAt": issue_node.get("updatedAt"),
            "comments": {
                "edges": [
                    {"node": edge["node"]}
                    for edge in issue_node.get("notes", {}).get("edges", [])
                ]
            },
        }

    def _normalize_fork(self, fork_node: dict[str, Any]) -> dict[str, Any]:
        """Normalize GitLab fork (from REST API) to GitHub fork format."""
        return {
            "createdAt": fork_node.get("created_at"),
            "pushedAt": fork_node.get("last_activity_at"),
            "owner": {
                "login": fork_node.get("namespace", {}).get("path", "")
                or fork_node.get("owner", {}).get("username", "")
            },
        }
