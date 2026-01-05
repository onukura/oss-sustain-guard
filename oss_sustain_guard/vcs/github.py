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

# Sample size constants by scan depth
# shallow: Quick scan with minimal data
# default: Balanced sampling for typical analysis
# deep: Comprehensive sampling for thorough analysis
SCAN_DEPTH_LIMITS = {
    "shallow": {
        "commits": 50,
        "merged_prs": 20,
        "closed_prs": 20,
        "open_issues": 10,
        "closed_issues": 20,
        "releases": 5,
        "vulnerability_alerts": 5,
        "forks": 10,
        "reviews": 3,
    },
    "default": {
        "commits": 100,
        "merged_prs": 50,
        "closed_prs": 50,
        "open_issues": 20,
        "closed_issues": 50,
        "releases": 10,
        "vulnerability_alerts": 10,
        "forks": 20,
        "reviews": 10,
    },
    "deep": {
        "commits": 100,  # GitHub API limit: max 100 per query
        "merged_prs": 100,
        "closed_prs": 100,
        "open_issues": 50,
        "closed_issues": 100,
        "releases": 20,
        "vulnerability_alerts": 20,
        "forks": 50,
        "reviews": 20,
    },
    "very_deep": {
        "commits": 100,  # GitHub API limit: max 100 per query
        "merged_prs": 100,  # GitHub API limit: max 100 per query
        "closed_prs": 100,  # GitHub API limit: max 100 per query
        "open_issues": 100,
        "closed_issues": 100,  # GitHub API limit: max 100 per query
        "releases": 30,
        "vulnerability_alerts": 30,
        "forks": 70,
        "reviews": 30,
    },
}

# Legacy constant for backward compatibility (uses default)
GRAPHQL_SAMPLE_LIMITS = SCAN_DEPTH_LIMITS["default"]


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

    async def get_repository_data(
        self,
        owner: str,
        repo: str,
        scan_depth: str = "default",
        days_lookback: int | None = None,
        time_window: tuple[str, str] | None = None,
    ) -> VCSRepositoryData:
        """
        Fetch repository data from GitHub GraphQL API.

        Args:
            owner: GitHub repository owner (username or organization)
            repo: GitHub repository name
            scan_depth: Sampling depth - "shallow", "default", or "deep"
            days_lookback: Optional time filter (days to look back), None = no limit
            time_window: Optional (since, until) ISO timestamp tuple for precise window.
                        If provided, takes precedence over days_lookback.
                        Note: GitHub API only supports 'since', so 'until' is applied
                        as a post-fetch filter.

        Returns:
            Normalized VCSRepositoryData structure

        Raises:
            ValueError: If repository not found or is inaccessible
            httpx.HTTPStatusError: If GitHub API returns an error
        """
        from datetime import datetime, timedelta, timezone

        # Get sample limits based on scan depth
        limits = SCAN_DEPTH_LIMITS.get(scan_depth, SCAN_DEPTH_LIMITS["default"])

        # Determine time filter parameters
        since_date = None
        until_date = None

        if time_window is not None:
            # Use explicit time window (for trend analysis)
            # IMPORTANT: Don't use 'since' parameter for trend analysis because:
            # - GitHub API returns the LATEST N items since that date
            # - For old time windows, this means we get recent data and filter it out
            # - This creates sampling bias where old windows have fewer/no data
            # Instead, fetch all data and filter client-side
            since_date, until_date = time_window
            # Don't pass since_date to API, only use for client-side filtering
            api_since_date = None
        elif days_lookback is not None:
            # Use days_lookback (for regular analysis)
            api_since_date = (
                datetime.now(timezone.utc) - timedelta(days=days_lookback)
            ).isoformat()
        else:
            api_since_date = None

        query = self._get_graphql_query(limits, use_since=api_since_date is not None)
        variables = {"owner": owner, "name": repo}
        if api_since_date:
            variables["since"] = api_since_date

        raw_data = await self._query_graphql(query, variables)

        if "repository" not in raw_data or raw_data["repository"] is None:
            raise ValueError(f"Repository {owner}/{repo} not found or is inaccessible.")

        repo_info = raw_data["repository"]

        # If time_window is specified, filter the data by both since and until
        if (
            time_window is not None
            and since_date is not None
            and until_date is not None
        ):
            repo_info = self._filter_data_by_time_window(
                repo_info, since_date, until_date
            )

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

    def _get_graphql_query(
        self, limits: dict[str, int], use_since: bool = False
    ) -> str:
        """
        Return the GraphQL query to fetch repository metrics.

        Args:
            limits: Dictionary with sample size limits for each data type
            use_since: Whether to include $since variable for time filtering
        """
        # Build query signature with optional $since parameter
        query_params = "$owner: String!, $name: String!"
        if use_since:
            query_params += ", $since: GitTimestamp"

        # Build history() parameters
        history_params = f"first: {limits['commits']}"
        if use_since:
            history_params += ", since: $since"

        return f"""
        query GetRepository({query_params}) {{
          repository(owner: $owner, name: $name) {{
            isArchived
            pushedAt
            owner {{
              __typename
              login
              ... on Organization {{
                name
                login
              }}
            }}
            defaultBranchRef {{
              name
              target {{
                ... on Commit {{
                  history({history_params}) {{
                    edges {{
                      node {{
                        authoredDate
                        author {{
                          user {{
                            login
                            company
                          }}
                          email
                        }}
                      }}
                    }}
                    totalCount
                  }}
                  checkSuites(last: 1) {{
                    nodes {{
                      conclusion
                      status
                    }}
                  }}
                }}
              }}
            }}
            pullRequests(first: {limits["merged_prs"]}, states: MERGED, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
              edges {{
                node {{
                  mergedAt
                  createdAt
                  mergedBy {{
                    login
                  }}
                  reviews(first: {limits["reviews"]}) {{
                    totalCount
                    edges {{
                      node {{
                        createdAt
                      }}
                    }}
                  }}
                }}
              }}
            }}
            closedPullRequests: pullRequests(first: {limits["closed_prs"]}, states: CLOSED, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
              totalCount
              edges {{
                node {{
                  closedAt
                  createdAt
                  merged
                  reviews(first: 1) {{
                    edges {{
                      node {{
                        createdAt
                      }}
                    }}
                  }}
                }}
              }}
            }}
            mergedPullRequestsCount: pullRequests(states: MERGED) {{
              totalCount
            }}
            releases(first: {limits["releases"]}, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
              edges {{
                node {{
                  publishedAt
                  tagName
                }}
              }}
            }}
            issues(first: {limits["open_issues"]}, states: OPEN, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
              totalCount
              edges {{
                node {{
                  createdAt
                  comments(first: 1) {{
                    edges {{
                      node {{
                        createdAt
                      }}
                    }}
                  }}
                }}
              }}
            }}
            closedIssues: issues(first: {limits["closed_issues"]}, states: CLOSED, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
              totalCount
              edges {{
                node {{
                  createdAt
                  closedAt
                  updatedAt
                  timelineItems(first: 1, itemTypes: CLOSED_EVENT) {{
                    edges {{
                      node {{
                        ... on ClosedEvent {{
                          actor {{
                            login
                          }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            vulnerabilityAlerts(first: {limits["vulnerability_alerts"]}) {{
              edges {{
                node {{
                  securityVulnerability {{
                    severity
                  }}
                  dismissedAt
                }}
              }}
            }}
            isSecurityPolicyEnabled
            fundingLinks {{
              platform
              url
            }}
            hasWikiEnabled
            hasIssuesEnabled
            hasDiscussionsEnabled
            codeOfConduct {{
              name
              url
            }}
            licenseInfo {{
              name
              spdxId
              url
            }}
            primaryLanguage {{
              name
            }}
            repositoryTopics(first: 20) {{
              nodes {{
                topic {{
                  name
                }}
              }}
            }}
            stargazerCount
            forkCount
            watchers {{
              totalCount
            }}
            forks(first: {limits["forks"]}, orderBy: {{field: PUSHED_AT, direction: DESC}}) {{
              edges {{
                node {{
                  createdAt
                  pushedAt
                  defaultBranchRef {{
                    target {{
                      ... on Commit {{
                        history(first: 1) {{
                          edges {{
                            node {{
                              committedDate
                            }}
                          }}
                        }}
                      }}
                    }}
                  }}
                  owner {{
                    login
                  }}
                }}
              }}
            }}
            readmeUpperCase: object(expression: "HEAD:README.md") {{
              ... on Blob {{
                byteSize
                text
              }}
            }}
            readmeLowerCase: object(expression: "HEAD:readme.md") {{
              ... on Blob {{
                byteSize
                text
              }}
            }}
            readmeAllCaps: object(expression: "HEAD:README") {{
              ... on Blob {{
                byteSize
                text
              }}
            }}
            contributingFile: object(expression: "HEAD:CONTRIBUTING.md") {{
              ... on Blob {{
                byteSize
              }}
            }}
            description
            homepageUrl
          }}
        }}
        """

    def _filter_data_by_time_window(
        self, repo_info: dict[str, Any], since_date: str, until_date: str
    ) -> dict[str, Any]:
        """
        Filter repository data to include only items within the time window.

        GitHub API doesn't support proper time window filtering, so we filter client-side.

        Args:
            repo_info: Raw GitHub repository data
            since_date: ISO timestamp string for start of time window
            until_date: ISO timestamp string for end of time window

        Returns:
            Filtered repository data dictionary
        """
        from datetime import datetime

        # Parse dates
        since_dt = datetime.fromisoformat(since_date.replace("Z", "+00:00"))
        until_dt = datetime.fromisoformat(until_date.replace("Z", "+00:00"))

        # Create a deep copy to avoid modifying original
        import copy

        filtered = copy.deepcopy(repo_info)

        # Filter commits
        default_branch = filtered.get("defaultBranchRef")
        if default_branch and default_branch.get("target"):
            history = default_branch["target"].get("history", {})
            edges = history.get("edges", [])
            filtered_edges = [
                edge
                for edge in edges
                if edge["node"].get("authoredDate")
                and since_dt
                <= datetime.fromisoformat(
                    edge["node"]["authoredDate"].replace("Z", "+00:00")
                )
                <= until_dt
            ]
            history["edges"] = filtered_edges
            if "totalCount" in history:
                history["totalCount"] = len(filtered_edges)

        # Filter merged PRs
        pr_data = filtered.get("pullRequests", {})
        if pr_data:
            edges = pr_data.get("edges", [])
            filtered_edges = [
                edge
                for edge in edges
                if edge["node"].get("mergedAt")
                and since_dt
                <= datetime.fromisoformat(
                    edge["node"]["mergedAt"].replace("Z", "+00:00")
                )
                <= until_dt
            ]
            pr_data["edges"] = filtered_edges

        # Filter closed PRs
        closed_pr_data = filtered.get("closedPullRequests", {})
        if closed_pr_data:
            edges = closed_pr_data.get("edges", [])
            filtered_edges = [
                edge
                for edge in edges
                if edge["node"].get("closedAt")
                and since_dt
                <= datetime.fromisoformat(
                    edge["node"]["closedAt"].replace("Z", "+00:00")
                )
                <= until_dt
            ]
            closed_pr_data["edges"] = filtered_edges
            if "totalCount" in closed_pr_data:
                closed_pr_data["totalCount"] = len(filtered_edges)

        # Filter releases
        releases_data = filtered.get("releases", {})
        if releases_data:
            edges = releases_data.get("edges", [])
            filtered_edges = [
                edge
                for edge in edges
                if edge["node"].get("publishedAt")
                and since_dt
                <= datetime.fromisoformat(
                    edge["node"]["publishedAt"].replace("Z", "+00:00")
                )
                <= until_dt
            ]
            releases_data["edges"] = filtered_edges

        # Filter open issues (by creation date)
        issues_data = filtered.get("issues", {})
        if issues_data:
            edges = issues_data.get("edges", [])
            filtered_edges = [
                edge
                for edge in edges
                if edge["node"].get("createdAt")
                and since_dt
                <= datetime.fromisoformat(
                    edge["node"]["createdAt"].replace("Z", "+00:00")
                )
                <= until_dt
            ]
            issues_data["edges"] = filtered_edges
            if "totalCount" in issues_data:
                issues_data["totalCount"] = len(filtered_edges)

        # Filter closed issues
        closed_issues_data = filtered.get("closedIssues", {})
        if closed_issues_data:
            edges = closed_issues_data.get("edges", [])
            filtered_edges = [
                edge
                for edge in edges
                if edge["node"].get("closedAt")
                and since_dt
                <= datetime.fromisoformat(
                    edge["node"]["closedAt"].replace("Z", "+00:00")
                )
                <= until_dt
            ]
            closed_issues_data["edges"] = filtered_edges
            if "totalCount" in closed_issues_data:
                closed_issues_data["totalCount"] = len(filtered_edges)

        return filtered

    def _normalize_github_data(self, repo_info: dict[str, Any]) -> VCSRepositoryData:
        """
        Normalize GitHub GraphQL response to VCSRepositoryData format.

        Args:
            repo_info: GitHub repository data from GraphQL response

        Returns:
            Normalized VCSRepositoryData structure
        """
        from datetime import datetime

        # Since we're using API-level filtering with 'since' parameter,
        # we no longer need client-side filtering
        cutoff_date = None

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
            all_commits = [edge["node"] for edge in history.get("edges", [])]
            total_commits = history.get("totalCount", len(all_commits))

            # Apply time filter if specified
            if cutoff_date:
                commits = [
                    c
                    for c in all_commits
                    if c.get("authoredDate")
                    and datetime.fromisoformat(c["authoredDate"].replace("Z", "+00:00"))
                    >= cutoff_date
                ]
            else:
                commits = all_commits

        # Extract pull requests
        merged_prs_data = repo_info.get("pullRequests", {})
        all_merged_prs = [edge["node"] for edge in merged_prs_data.get("edges", [])]

        # Apply time filter if specified
        if cutoff_date:
            merged_prs = [
                pr
                for pr in all_merged_prs
                if pr.get("mergedAt")
                and datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00"))
                >= cutoff_date
            ]
        else:
            merged_prs = all_merged_prs

        closed_prs_data = repo_info.get("closedPullRequests", {})
        all_closed_prs = [
            edge["node"]
            for edge in closed_prs_data.get("edges", [])
            if not edge["node"].get("merged", False)
        ]

        # Apply time filter if specified
        if cutoff_date:
            closed_prs = [
                pr
                for pr in all_closed_prs
                if pr.get("closedAt")
                and datetime.fromisoformat(pr["closedAt"].replace("Z", "+00:00"))
                >= cutoff_date
            ]
        else:
            closed_prs = all_closed_prs

        total_merged_prs = repo_info.get("mergedPullRequestsCount", {}).get(
            "totalCount", len(all_merged_prs)
        )

        # Extract releases
        releases_data = repo_info.get("releases", {})
        all_releases = [edge["node"] for edge in releases_data.get("edges", [])]

        # Apply time filter if specified
        if cutoff_date:
            releases = [
                r
                for r in all_releases
                if r.get("publishedAt")
                and datetime.fromisoformat(r["publishedAt"].replace("Z", "+00:00"))
                >= cutoff_date
            ]
        else:
            releases = all_releases

        # Extract issues
        open_issues_data = repo_info.get("issues", {})
        all_open_issues = [edge["node"] for edge in open_issues_data.get("edges", [])]
        open_issues_count = open_issues_data.get("totalCount", len(all_open_issues))

        # Apply time filter if specified
        if cutoff_date:
            open_issues = [
                i
                for i in all_open_issues
                if i.get("createdAt")
                and datetime.fromisoformat(i["createdAt"].replace("Z", "+00:00"))
                >= cutoff_date
            ]
        else:
            open_issues = all_open_issues

        closed_issues_data = repo_info.get("closedIssues", {})
        all_closed_issues = [
            edge["node"] for edge in closed_issues_data.get("edges", [])
        ]
        total_closed_issues = closed_issues_data.get(
            "totalCount", len(all_closed_issues)
        )

        # Apply time filter if specified
        if cutoff_date:
            closed_issues = [
                i
                for i in all_closed_issues
                if i.get("closedAt")
                and datetime.fromisoformat(i["closedAt"].replace("Z", "+00:00"))
                >= cutoff_date
            ]
        else:
            closed_issues = all_closed_issues

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
