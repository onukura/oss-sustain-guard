"""
GitHub VCS provider implementation for OSS Sustain Guard.

This module implements the GitHub-specific VCS provider using the GitHub GraphQL API
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

# GitHub API endpoint
GITHUB_GRAPHQL_API = "https://api.github.com/graphql"

# Sample size constants from GraphQL queries
GRAPHQL_SAMPLE_LIMITS = {
    "commits": 100,
    "merged_prs": 50,
    "closed_prs": 50,
    "open_issues": 20,
    "closed_issues": 50,
    "releases": 10,
    "vulnerability_alerts": 10,
    "forks": 20,
}


class GitHubProvider(BaseVCSProvider):
    """GitHub VCS provider using GraphQL API."""

    def __init__(self, token: str | None = None):
        """
        Initialize GitHub provider.

        Args:
            token: GitHub Personal Access Token. If not provided, reads from
                   GITHUB_TOKEN environment variable.

        Raises:
            ValueError: If token is not provided and GITHUB_TOKEN env var is not set
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token or len(self.token) == 0:
            raise ValueError(
                "GITHUB_TOKEN is required for GitHub provider.\n"
                "\n"
                "To get started:\n"
                "1. Create a GitHub Personal Access Token (classic):\n"
                "   → https://github.com/settings/tokens/new\n"
                "2. Select scopes: 'public_repo' and 'security_events'\n"
                "3. Set the token:\n"
                "   export GITHUB_TOKEN='your_token_here'  # Linux/macOS\n"
                "   or add to your .env file: GITHUB_TOKEN=your_token_here\n"
            )

    def get_platform_name(self) -> str:
        """Return 'github' as the platform identifier."""
        return "github"

    def validate_credentials(self) -> bool:
        """Check if GitHub token is configured."""
        return self.token is not None and len(self.token) > 0

    def get_repository_url(self, owner: str, repo: str) -> str:
        """Construct GitHub repository URL."""
        return f"https://github.com/{owner}/{repo}"

    async def get_repository_data(self, owner: str, repo: str) -> VCSRepositoryData:
        """
        Fetch repository data from GitHub GraphQL API.

        Args:
            owner: GitHub repository owner (username or organization)
            repo: GitHub repository name

        Returns:
            Normalized VCSRepositoryData structure

        Raises:
            ValueError: If repository not found or is inaccessible
            httpx.HTTPStatusError: If GitHub API returns an error
        """
        query = self._get_graphql_query()
        variables = {"owner": owner, "name": repo}
        raw_data = await self._query_graphql(query, variables)

        if "repository" not in raw_data or raw_data["repository"] is None:
            raise ValueError(f"Repository {owner}/{repo} not found or is inaccessible.")

        repo_info = raw_data["repository"]
        return self._normalize_github_data(repo_info)

    async def _query_graphql(
        self, query: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute GraphQL query against GitHub API.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Response data dictionary

        Raises:
            httpx.HTTPStatusError: If API returns an error
        """
        headers = {
            "Authorization": f"bearer {self.token}",
            "Content-Type": "application/json",
        }
        client = await _get_async_http_client()
        response = await client.post(
            GITHUB_GRAPHQL_API,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise httpx.HTTPStatusError(
                f"GitHub API Errors: {data['errors']}",
                request=response.request,
                response=response,
            )

        return data.get("data", {})

    def _get_graphql_query(self) -> str:
        """Return the GraphQL query to fetch repository metrics."""
        return """
        query GetRepository($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            isArchived
            pushedAt
            owner {
              __typename
              login
              ... on Organization {
                name
                login
              }
            }
            defaultBranchRef {
              name
              target {
                ... on Commit {
                  history(first: 100) {
                    edges {
                      node {
                        authoredDate
                        author {
                          user {
                            login
                            company
                          }
                          email
                        }
                      }
                    }
                    totalCount
                  }
                  checkSuites(last: 1) {
                    nodes {
                      conclusion
                      status
                    }
                  }
                }
              }
            }
            pullRequests(first: 50, states: MERGED, orderBy: {field: UPDATED_AT, direction: DESC}) {
              edges {
                node {
                  mergedAt
                  createdAt
                  mergedBy {
                    login
                  }
                  reviews(first: 10) {
                    totalCount
                    edges {
                      node {
                        createdAt
                      }
                    }
                  }
                }
              }
            }
            closedPullRequests: pullRequests(first: 50, states: CLOSED, orderBy: {field: UPDATED_AT, direction: DESC}) {
              totalCount
              edges {
                node {
                  closedAt
                  createdAt
                  merged
                  reviews(first: 1) {
                    edges {
                      node {
                        createdAt
                      }
                    }
                  }
                }
              }
            }
            mergedPullRequestsCount: pullRequests(states: MERGED) {
              totalCount
            }
            releases(first: 10, orderBy: {field: CREATED_AT, direction: DESC}) {
              edges {
                node {
                  publishedAt
                  tagName
                }
              }
            }
            issues(first: 20, states: OPEN, orderBy: {field: CREATED_AT, direction: DESC}) {
              totalCount
              edges {
                node {
                  createdAt
                  comments(first: 1) {
                    edges {
                      node {
                        createdAt
                      }
                    }
                  }
                }
              }
            }
            closedIssues: issues(first: 50, states: CLOSED, orderBy: {field: UPDATED_AT, direction: DESC}) {
              totalCount
              edges {
                node {
                  createdAt
                  closedAt
                  updatedAt
                  timelineItems(first: 1, itemTypes: CLOSED_EVENT) {
                    edges {
                      node {
                        ... on ClosedEvent {
                          actor {
                            login
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            vulnerabilityAlerts(first: 10) {
              edges {
                node {
                  securityVulnerability {
                    severity
                  }
                  dismissedAt
                }
              }
            }
            isSecurityPolicyEnabled
            fundingLinks {
              platform
              url
            }
            hasWikiEnabled
            hasIssuesEnabled
            hasDiscussionsEnabled
            codeOfConduct {
              name
              url
            }
            licenseInfo {
              name
              spdxId
              url
            }
            primaryLanguage {
              name
            }
            repositoryTopics(first: 20) {
              nodes {
                topic {
                  name
                }
              }
            }
            stargazerCount
            forkCount
            watchers {
              totalCount
            }
            forks(first: 20, orderBy: {field: PUSHED_AT, direction: DESC}) {
              edges {
                node {
                  createdAt
                  pushedAt
                  defaultBranchRef {
                    target {
                      ... on Commit {
                        history(first: 1) {
                          edges {
                            node {
                              committedDate
                            }
                          }
                        }
                      }
                    }
                  }
                  owner {
                    login
                  }
                }
              }
            }
            readmeUpperCase: object(expression: "HEAD:README.md") {
              ... on Blob {
                byteSize
                text
              }
            }
            readmeLowerCase: object(expression: "HEAD:readme.md") {
              ... on Blob {
                byteSize
                text
              }
            }
            readmeAllCaps: object(expression: "HEAD:README") {
              ... on Blob {
                byteSize
                text
              }
            }
            contributingFile: object(expression: "HEAD:CONTRIBUTING.md") {
              ... on Blob {
                byteSize
              }
            }
            description
            homepageUrl
          }
        }
        """

    def _normalize_github_data(self, repo_info: dict[str, Any]) -> VCSRepositoryData:
        """
        Normalize GitHub GraphQL response to VCSRepositoryData format.

        Args:
            repo_info: GitHub repository data from GraphQL response

        Returns:
            Normalized VCSRepositoryData structure
        """
        # Extract owner information
        owner_data = repo_info.get("owner", {})
        owner_type = owner_data.get("__typename", "User")
        owner_login = owner_data.get("login", "")
        owner_name = owner_data.get("name")

        # Extract repository metadata
        star_count = repo_info.get("stargazerCount", 0)
        description = repo_info.get("description")
        homepage_url = repo_info.get("homepageUrl")
        topics_data = repo_info.get("repositoryTopics", {})
        topics_nodes = topics_data.get("nodes", []) if topics_data else []
        topics = []
        for node in topics_nodes:
            topic = node.get("topic") if node else None
            name = topic.get("name") if isinstance(topic, dict) else None
            if name:
                topics.append(name)
        readme_candidates = [
            repo_info.get("readmeUpperCase"),
            repo_info.get("readmeLowerCase"),
            repo_info.get("readmeAllCaps"),
        ]
        readme_size = None
        for candidate in readme_candidates:
            if candidate is None:
                continue
            if "byteSize" in candidate:
                readme_size = candidate.get("byteSize")
                break
        contributing_file = repo_info.get("contributingFile")
        contributing_file_size = (
            contributing_file.get("byteSize") if contributing_file else None
        )
        watchers_count = repo_info.get("watchers", {}).get("totalCount", 0)
        primary_language = repo_info.get("primaryLanguage")
        language = primary_language.get("name") if primary_language else None

        # Extract commits
        commits = []
        total_commits = 0
        default_branch = repo_info.get("defaultBranchRef")
        if default_branch and default_branch.get("target"):
            history = default_branch["target"].get("history", {})
            commits = [edge["node"] for edge in history.get("edges", [])]
            total_commits = history.get("totalCount", len(commits))

        # Extract pull requests
        merged_prs_data = repo_info.get("pullRequests", {})
        merged_prs = [edge["node"] for edge in merged_prs_data.get("edges", [])]

        closed_prs_data = repo_info.get("closedPullRequests", {})
        closed_prs = [
            edge["node"]
            for edge in closed_prs_data.get("edges", [])
            if not edge["node"].get("merged", False)
        ]

        total_merged_prs = repo_info.get("mergedPullRequestsCount", {}).get(
            "totalCount", len(merged_prs)
        )

        # Extract releases
        releases_data = repo_info.get("releases", {})
        releases = [edge["node"] for edge in releases_data.get("edges", [])]

        # Extract issues
        open_issues_data = repo_info.get("issues", {})
        open_issues = [edge["node"] for edge in open_issues_data.get("edges", [])]
        open_issues_count = open_issues_data.get("totalCount", len(open_issues))

        closed_issues_data = repo_info.get("closedIssues", {})
        closed_issues = [edge["node"] for edge in closed_issues_data.get("edges", [])]
        total_closed_issues = closed_issues_data.get("totalCount", len(closed_issues))

        # Extract vulnerability alerts
        vuln_data = repo_info.get("vulnerabilityAlerts", {})
        vulnerability_alerts = (
            [edge["node"] for edge in vuln_data.get("edges", [])] if vuln_data else None
        )

        # Extract code of conduct
        coc = repo_info.get("codeOfConduct")
        code_of_conduct = {"name": coc["name"], "url": coc["url"]} if coc else None

        # Extract license info
        license_data = repo_info.get("licenseInfo")
        license_info = (
            {
                "name": license_data["name"],
                "spdxId": license_data.get("spdxId", ""),
                "url": license_data.get("url", ""),
            }
            if license_data
            else None
        )

        # Extract funding links
        funding_links_raw = repo_info.get("fundingLinks", [])
        funding_links = [
            {"platform": link["platform"], "url": link["url"]}
            for link in funding_links_raw
        ]

        # Extract forks
        forks_data = repo_info.get("forks", {})
        forks = [edge["node"] for edge in forks_data.get("edges", [])]
        total_forks = repo_info.get("forkCount", len(forks))

        # Extract CI/CD status
        ci_status = None
        if default_branch and default_branch.get("target"):
            check_suites = default_branch["target"].get("checkSuites", {})
            nodes = check_suites.get("nodes", [])
            if nodes:
                latest_suite = nodes[0]
                ci_status = {
                    "conclusion": latest_suite.get("conclusion", ""),
                    "status": latest_suite.get("status", ""),
                }

        # Sample counts
        sample_counts = {
            "commits": len(commits),
            "merged_prs": len(merged_prs),
            "closed_prs": len(closed_prs),
            "open_issues": len(open_issues),
            "closed_issues": len(closed_issues),
            "releases": len(releases),
            "vulnerability_alerts": len(vulnerability_alerts)
            if vulnerability_alerts
            else 0,
            "forks": len(forks),
        }

        return VCSRepositoryData(
            is_archived=repo_info.get("isArchived", False),
            pushed_at=repo_info.get("pushedAt"),
            owner_type=owner_type,
            owner_login=owner_login,
            owner_name=owner_name,
            star_count=star_count,
            description=description,
            homepage_url=homepage_url,
            topics=topics,
            readme_size=readme_size,
            contributing_file_size=contributing_file_size,
            default_branch=default_branch.get("name") if default_branch else None,
            watchers_count=watchers_count,
            open_issues_count=open_issues_count,
            language=language,
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
            has_security_policy=repo_info.get("isSecurityPolicyEnabled", False),
            code_of_conduct=code_of_conduct,
            license_info=license_info,
            has_wiki=repo_info.get("hasWikiEnabled", False),
            has_issues=repo_info.get("hasIssuesEnabled", True),
            has_discussions=repo_info.get("hasDiscussionsEnabled", False),
            funding_links=funding_links,
            forks=forks,
            total_forks=total_forks,
            ci_status=ci_status,
            sample_counts=sample_counts,
            raw_data=repo_info,  # Keep original data for debugging
        )


PROVIDER = GitHubProvider
