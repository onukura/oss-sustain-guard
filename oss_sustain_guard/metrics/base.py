"""
Shared metric types and context helpers.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, NamedTuple

from oss_sustain_guard.vcs.base import VCSRepositoryData


class Metric(NamedTuple):
    """A single sustainability metric."""

    name: str
    score: int
    max_score: int
    message: str
    risk: str  # "Critical", "High", "Medium", "Low", "None"


class MetricContext(NamedTuple):
    """Context provided to metric checks."""

    owner: str
    name: str
    repo_url: str
    platform: str | None = None
    package_name: str | None = None


class MetricChecker(ABC):
    """VCS-agnostic metric checker base class."""

    @abstractmethod
    def check(
        self, vcs_data: VCSRepositoryData, context: MetricContext
    ) -> Metric | None:
        """Check metric using normalized VCS data."""
        pass

    def check_legacy(
        self, repo_info: dict[str, Any], context: MetricContext
    ) -> Metric | None:
        """Check metric using legacy repo_info format."""
        vcs_data = self._legacy_to_vcs_data(repo_info)
        return self.check(vcs_data, context)

    def _legacy_to_vcs_data(self, repo_info: dict[str, Any]) -> VCSRepositoryData:
        """Convert legacy repo_info (GitHub GraphQL shape) to VCSRepositoryData."""
        owner_data = repo_info.get("owner", {})
        owner_type = owner_data.get("__typename", "User")
        owner_login = owner_data.get("login", "")
        owner_name = owner_data.get("name")

        default_branch_ref = repo_info.get("defaultBranchRef")
        default_branch = default_branch_ref.get("name") if default_branch_ref else None

        commits: list[dict[str, Any]] = []
        total_commits = 0
        ci_status = None
        if default_branch_ref and default_branch_ref.get("target"):
            history = default_branch_ref["target"].get("history", {})
            commits = [edge.get("node", {}) for edge in history.get("edges", [])]
            total_commits = history.get("totalCount", len(commits))
            check_suites = default_branch_ref["target"].get("checkSuites", {})
            nodes = check_suites.get("nodes", [])
            if nodes:
                latest_suite = nodes[0]
                ci_status = {
                    "conclusion": latest_suite.get("conclusion", ""),
                    "status": latest_suite.get("status", ""),
                }

        merged_prs_data = repo_info.get("pullRequests", {})
        merged_prs = [edge.get("node", {}) for edge in merged_prs_data.get("edges", [])]

        closed_prs_data = repo_info.get("closedPullRequests", {})
        closed_prs = []
        for edge in closed_prs_data.get("edges", []):
            node = edge.get("node", {})
            if node.get("merged"):
                continue
            closed_prs.append(node)

        total_merged_prs = repo_info.get("mergedPullRequestsCount", {}).get(
            "totalCount", len(merged_prs)
        )

        releases_data = repo_info.get("releases", {})
        releases = [edge.get("node", {}) for edge in releases_data.get("edges", [])]

        open_issues_data = repo_info.get("issues", {})
        open_issues = [
            edge.get("node", {}) for edge in open_issues_data.get("edges", [])
        ]
        open_issues_count = open_issues_data.get("totalCount", len(open_issues))

        closed_issues_data = repo_info.get("closedIssues", {})
        closed_issues = [
            edge.get("node", {}) for edge in closed_issues_data.get("edges", [])
        ]
        total_closed_issues = closed_issues_data.get("totalCount", len(closed_issues))

        vuln_data = repo_info.get("vulnerabilityAlerts")
        vulnerability_alerts = None
        if vuln_data:
            vulnerability_alerts = [
                edge.get("node", {}) for edge in vuln_data.get("edges", [])
            ]

        coc = repo_info.get("codeOfConduct")
        code_of_conduct = (
            {"name": coc.get("name", ""), "url": coc.get("url", "")} if coc else None
        )

        license_data = repo_info.get("licenseInfo")
        license_info = (
            {
                "name": license_data.get("name", ""),
                "spdxId": license_data.get("spdxId", ""),
                "url": license_data.get("url", ""),
            }
            if license_data
            else None
        )

        funding_links = repo_info.get("fundingLinks", [])

        forks_data = repo_info.get("forks", {})
        forks = [edge.get("node", {}) for edge in forks_data.get("edges", [])]
        total_forks = repo_info.get("forkCount", len(forks))

        stargazer_count = repo_info.get("stargazerCount", 0)
        watchers_count = repo_info.get("watchers", {}).get("totalCount", 0)
        description = repo_info.get("description")
        homepage_url = repo_info.get("homepageUrl")

        topics_data = repo_info.get("repositoryTopics", {}) or {}
        topic_nodes = topics_data.get("nodes")
        if topic_nodes is None:
            topic_nodes = [edge.get("node") for edge in topics_data.get("edges", [])]
        topics = []
        for node in topic_nodes or []:
            if not node:
                continue
            topic = node.get("topic", {})
            name = topic.get("name") if isinstance(topic, dict) else None
            if name:
                topics.append(name)

        readme_size = None
        for candidate_key in ("readmeUpperCase", "readmeLowerCase", "readmeAllCaps"):
            candidate = repo_info.get(candidate_key)
            if candidate is None:
                continue
            if "byteSize" in candidate:
                readme_size = candidate.get("byteSize")
                break

        contributing_file = repo_info.get("contributingFile")
        contributing_file_size = (
            contributing_file.get("byteSize") if contributing_file else None
        )

        language_data = repo_info.get("primaryLanguage")
        language = language_data.get("name") if language_data else None

        sample_counts = repo_info.get("sample_counts", {})

        return VCSRepositoryData(
            is_archived=repo_info.get("isArchived", False),
            pushed_at=repo_info.get("pushedAt"),
            owner_type=owner_type,
            owner_login=owner_login,
            owner_name=owner_name,
            star_count=stargazer_count,
            description=description,
            homepage_url=homepage_url,
            topics=topics,
            readme_size=readme_size,
            contributing_file_size=contributing_file_size,
            default_branch=default_branch,
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
            raw_data=repo_info,
        )


class MetricSpec(NamedTuple):
    """Specification for a metric check."""

    name: str
    checker: Callable[[dict[str, Any], MetricContext], Metric | None] | MetricChecker
    on_error: Callable[[Exception], Metric] | None = None
    error_log: str | None = None
