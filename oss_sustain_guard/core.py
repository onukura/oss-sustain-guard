"""
Core analysis logic for OSS Sustain Guard.
"""

import copy
from typing import Any, NamedTuple

import httpx
from dotenv import load_dotenv
from rich.console import Console

from oss_sustain_guard.librariesio import query_librariesio_api
from oss_sustain_guard.metrics import load_metric_specs
from oss_sustain_guard.metrics.attraction import check_attraction  # noqa: F401
from oss_sustain_guard.metrics.base import Metric, MetricContext
from oss_sustain_guard.metrics.bus_factor import check_bus_factor  # noqa: F401
from oss_sustain_guard.metrics.ci_status import check_ci_status  # noqa: F401
from oss_sustain_guard.metrics.code_of_conduct import (  # noqa: F401
    check_code_of_conduct,
)
from oss_sustain_guard.metrics.community_health import (  # noqa: F401
    check_community_health,  # noqa: F401
)
from oss_sustain_guard.metrics.dependents_count import (  # noqa: F401
    check_dependents_count,  # noqa: F401
)
from oss_sustain_guard.metrics.documentation_presence import (  # noqa: F401
    check_documentation_presence,  # noqa: F401
)
from oss_sustain_guard.metrics.fork_activity import check_fork_activity  # noqa: F401
from oss_sustain_guard.metrics.funding import (  # noqa: F401
    check_funding,  # noqa: F401
    is_corporate_backed,  # noqa: F401
)
from oss_sustain_guard.metrics.issue_resolution_duration import (  # noqa: F401
    check_issue_resolution_duration,  # noqa: F401
)
from oss_sustain_guard.metrics.license_clarity import (  # noqa: F401
    check_license_clarity,
)
from oss_sustain_guard.metrics.maintainer_drain import (  # noqa: F401
    check_maintainer_drain,
)
from oss_sustain_guard.metrics.merge_velocity import check_merge_velocity  # noqa: F401
from oss_sustain_guard.metrics.organizational_diversity import (  # noqa: F401
    check_organizational_diversity,  # noqa: F401
)
from oss_sustain_guard.metrics.pr_acceptance_ratio import (  # noqa: F401
    check_pr_acceptance_ratio,  # noqa: F401
)
from oss_sustain_guard.metrics.pr_merge_speed import check_pr_merge_speed  # noqa: F401
from oss_sustain_guard.metrics.pr_responsiveness import (  # noqa: F401
    check_pr_responsiveness,  # noqa: F401
)
from oss_sustain_guard.metrics.project_popularity import (  # noqa: F401
    check_project_popularity,  # noqa: F401
)
from oss_sustain_guard.metrics.release_cadence import (  # noqa: F401
    check_release_cadence,
)
from oss_sustain_guard.metrics.retention import check_retention  # noqa: F401
from oss_sustain_guard.metrics.review_health import check_review_health  # noqa: F401
from oss_sustain_guard.metrics.security_posture import (  # noqa: F401
    check_security_posture,
)
from oss_sustain_guard.metrics.single_maintainer_load import (  # noqa: F401
    check_single_maintainer_load,  # noqa: F401
)
from oss_sustain_guard.metrics.stale_issue_ratio import (  # noqa: F401
    check_stale_issue_ratio,
)
from oss_sustain_guard.metrics.zombie_status import check_zombie_status  # noqa: F401
from oss_sustain_guard.vcs import get_vcs_provider
from oss_sustain_guard.vcs.base import VCSRepositoryData

# Load environment variables from .env file
load_dotenv()
console = Console()


# --- Data Structures ---


class MetricModel(NamedTuple):
    """A computed metric model (collection of metrics for specific purpose)."""

    name: str
    score: int
    max_score: int
    observation: str  # Supportive observation instead of "message"


class AnalysisResult(NamedTuple):
    """The result of a repository analysis."""

    repo_url: str
    total_score: int
    metrics: list[Metric]
    funding_links: list[dict[str, str]] | None = None  # {"platform": str, "url": str}
    is_community_driven: bool = False  # True if project is community-driven
    models: list[MetricModel] | None = None  # Optional metric models (CHAOSS-aligned)
    signals: dict[str, Any] | None = None  # Optional raw signals for transparency
    dependency_scores: dict[str, int] | None = None
    ecosystem: str = ""  # Ecosystem name (python, javascript, rust, etc.)
    sample_counts: dict[str, int] | None = None  # Sample counts from GraphQL query
    skipped_metrics: list[str] | None = (
        None  # Metrics that were skipped (e.g., no API key)
    )


# --- Helper Functions ---


def analysis_result_to_dict(result: AnalysisResult) -> dict[str, Any]:
    """Serialize an AnalysisResult to a JSON-friendly dictionary."""
    metrics: list[dict[str, Any]] = []
    for metric in result.metrics:
        if isinstance(metric, dict):
            metrics.append(metric)
        elif hasattr(metric, "_asdict"):
            metrics.append(metric._asdict())
        else:
            metrics.append(
                {
                    "name": getattr(metric, "name", ""),
                    "score": getattr(metric, "score", 0),
                    "max_score": getattr(metric, "max_score", 0),
                    "message": getattr(metric, "message", ""),
                    "risk": getattr(metric, "risk", "None"),
                }
            )

    models: list[dict[str, Any]] = []
    for model in result.models or []:
        if isinstance(model, dict):
            models.append(model)
        elif hasattr(model, "_asdict"):
            models.append(model._asdict())
        else:
            models.append(
                {
                    "name": getattr(model, "name", ""),
                    "score": getattr(model, "score", 0),
                    "max_score": getattr(model, "max_score", 0),
                    "observation": getattr(model, "observation", ""),
                }
            )

    return {
        "repo_url": result.repo_url,
        "total_score": result.total_score,
        "metrics": metrics,
        "funding_links": list(result.funding_links or []),
        "is_community_driven": result.is_community_driven,
        "models": models,
        "signals": result.signals or {},
        "dependency_scores": result.dependency_scores or {},
        "ecosystem": result.ecosystem,
        "sample_counts": result.sample_counts or {},
        "skipped_metrics": list(result.skipped_metrics or []),
    }


def _query_librariesio_api(platform: str, package_name: str) -> dict[str, Any] | None:
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
    return query_librariesio_api(platform, package_name)


# --- Helper Functions for VCS Data Conversion ---


def _vcs_data_to_repo_info(vcs_data: VCSRepositoryData) -> dict[str, Any]:
    """
    Convert VCSRepositoryData to legacy repo_info format for metrics.

    This maintains compatibility with existing metric functions that expect
    the GitHub GraphQL response structure.

    Args:
        vcs_data: Normalized VCSRepositoryData from any VCS provider

    Returns:
        Dictionary matching the legacy GitHub GraphQL response format
    """
    # Use raw_data if available (for GitHub), otherwise reconstruct from normalized data
    if vcs_data.raw_data:
        repo_info = (
            vcs_data.raw_data.copy()
            if isinstance(vcs_data.raw_data, dict)
            else vcs_data.raw_data
        )
        # Ensure sample_counts is included
        if isinstance(repo_info, dict) and vcs_data.sample_counts:
            repo_info["sample_counts"] = vcs_data.sample_counts
        return repo_info

    # Reconstruct the structure that metrics expect
    # Handle case where commits or ci_status may be empty
    default_branch_data = None
    if vcs_data.commits or vcs_data.ci_status:
        default_branch_data = {
            "target": {
                "history": {
                    "edges": [{"node": commit} for commit in vcs_data.commits],
                    "totalCount": vcs_data.total_commits,
                },
                "checkSuites": {
                    "nodes": [vcs_data.ci_status] if vcs_data.ci_status else [],
                },
            }
        }

    return {
        "isArchived": vcs_data.is_archived,
        "pushedAt": vcs_data.pushed_at,
        "owner": {
            "__typename": vcs_data.owner_type,
            "login": vcs_data.owner_login,
            "name": vcs_data.owner_name,
        },
        "defaultBranchRef": default_branch_data,
        "pullRequests": {
            "edges": [{"node": pr} for pr in vcs_data.merged_prs],
        },
        "closedPullRequests": {
            "totalCount": len(vcs_data.closed_prs),
            "edges": [{"node": pr} for pr in vcs_data.closed_prs],
        },
        "mergedPullRequestsCount": {
            "totalCount": vcs_data.total_merged_prs,
        },
        "releases": {
            "edges": [{"node": release} for release in vcs_data.releases],
        },
        "issues": {
            "edges": [{"node": issue} for issue in vcs_data.open_issues],
        },
        "closedIssues": {
            "totalCount": vcs_data.total_closed_issues,
            "edges": [{"node": issue} for issue in vcs_data.closed_issues],
        },
        "vulnerabilityAlerts": {
            "edges": [
                {"node": alert} for alert in (vcs_data.vulnerability_alerts or [])
            ],
        }
        if vcs_data.vulnerability_alerts
        else None,
        "isSecurityPolicyEnabled": vcs_data.has_security_policy,
        "fundingLinks": vcs_data.funding_links,
        "hasWikiEnabled": vcs_data.has_wiki,
        "hasIssuesEnabled": vcs_data.has_issues,
        "hasDiscussionsEnabled": vcs_data.has_discussions,
        "codeOfConduct": vcs_data.code_of_conduct,
        "licenseInfo": vcs_data.license_info,
        "forks": {
            "edges": [{"node": fork} for fork in vcs_data.forks],
        },
        "forkCount": vcs_data.total_forks,
        # Include sample_counts from VCS data
        "sample_counts": vcs_data.sample_counts,
    }


# --- Scoring System ---

# Metric weight definitions for different profiles
# All metrics are scored on a 0-10 scale
# Weights are integers (1+) that determine relative importance
# Higher weight = more important to overall score
# Total score = Sum(metric_score × weight) / Sum(10 × weight) × 100

# Scoring profiles for different use cases
# Each profile adjusts metric weights based on specific priorities
DEFAULT_SCORING_PROFILES = {
    "balanced": {
        "name": "Balanced",
        "description": "Balanced view across all sustainability dimensions",
        "weights": {
            # Maintainer Health (25% emphasis)
            "Contributor Redundancy": 3,
            "Maintainer Retention": 2,
            "Contributor Attraction": 2,
            "Contributor Retention": 2,
            "Organizational Diversity": 2,
            "Maintainer Load Distribution": 2,
            # Development Activity (20% emphasis)
            "Recent Activity": 3,
            "Release Rhythm": 2,
            "Build Health": 2,
            "Change Request Resolution": 2,
            # Community Engagement (25% emphasis)
            "Community Health": 2,
            "PR Acceptance Ratio": 2,
            "Review Health": 2,
            "Issue Resolution Duration": 2,
            "Stale Issue Ratio": 2,
            "PR Merge Speed": 2,
            # Project Maturity (15% emphasis)
            "Documentation Presence": 2,
            "Code of Conduct": 1,
            "License Clarity": 1,
            "Project Popularity": 2,
            "Fork Activity": 1,
            # Security & Funding (15% emphasis)
            "Security Signals": 2,
            "Funding Signals": 2,
            # PR Responsiveness
            "PR Responsiveness": 1,
        },
    },
    "security_first": {
        "name": "Security First",
        "description": "Prioritizes security and resilience",
        "weights": {
            # Maintainer Health (20% emphasis)
            "Contributor Redundancy": 2,
            "Maintainer Retention": 2,
            "Contributor Attraction": 1,
            "Contributor Retention": 1,
            "Organizational Diversity": 2,
            "Maintainer Load Distribution": 1,
            # Development Activity (15% emphasis)
            "Recent Activity": 2,
            "Release Rhythm": 2,
            "Build Health": 3,
            "Change Request Resolution": 1,
            # Community Engagement (20% emphasis)
            "Community Health": 2,
            "PR Acceptance Ratio": 1,
            "Review Health": 2,
            "Issue Resolution Duration": 1,
            "Stale Issue Ratio": 1,
            "PR Merge Speed": 2,
            # Project Maturity (15% emphasis)
            "Documentation Presence": 2,
            "Code of Conduct": 1,
            "License Clarity": 2,
            "Project Popularity": 1,
            "Fork Activity": 1,
            # Security & Funding (30% emphasis) - INCREASED
            "Security Signals": 4,
            "Funding Signals": 3,
            # PR Responsiveness
            "PR Responsiveness": 1,
        },
    },
    "contributor_experience": {
        "name": "Contributor Experience",
        "description": "Focuses on community engagement and contributor-friendliness",
        "weights": {
            # Maintainer Health (15% emphasis)
            "Contributor Redundancy": 1,
            "Maintainer Retention": 1,
            "Contributor Attraction": 2,
            "Contributor Retention": 2,
            "Organizational Diversity": 1,
            "Maintainer Load Distribution": 1,
            # Development Activity (15% emphasis)
            "Recent Activity": 2,
            "Release Rhythm": 1,
            "Build Health": 1,
            "Change Request Resolution": 2,
            # Community Engagement (45% emphasis) - DOUBLED
            "Community Health": 4,
            "PR Acceptance Ratio": 4,
            "Review Health": 3,
            "Issue Resolution Duration": 3,
            "Stale Issue Ratio": 2,
            "PR Merge Speed": 3,
            # Project Maturity (15% emphasis)
            "Documentation Presence": 2,
            "Code of Conduct": 2,
            "License Clarity": 1,
            "Project Popularity": 1,
            "Fork Activity": 1,
            # Security & Funding (10% emphasis)
            "Security Signals": 1,
            "Funding Signals": 1,
            # PR Responsiveness
            "PR Responsiveness": 3,
        },
    },
    "long_term_stability": {
        "name": "Long-term Stability",
        "description": "Emphasizes maintainer health and sustainable development",
        "weights": {
            # Maintainer Health (35% emphasis) - HIGHEST
            "Contributor Redundancy": 4,
            "Maintainer Retention": 3,
            "Contributor Attraction": 2,
            "Contributor Retention": 3,
            "Organizational Diversity": 3,
            "Maintainer Load Distribution": 3,
            # Development Activity (25% emphasis)
            "Recent Activity": 3,
            "Release Rhythm": 3,
            "Build Health": 2,
            "Change Request Resolution": 2,
            # Community Engagement (15% emphasis)
            "Community Health": 1,
            "PR Acceptance Ratio": 1,
            "Review Health": 2,
            "Issue Resolution Duration": 1,
            "Stale Issue Ratio": 1,
            "PR Merge Speed": 1,
            # Project Maturity (15% emphasis)
            "Documentation Presence": 2,
            "Code of Conduct": 1,
            "License Clarity": 1,
            "Project Popularity": 1,
            "Fork Activity": 1,
            # Security & Funding (10% emphasis)
            "Security Signals": 1,
            "Funding Signals": 2,
            # PR Responsiveness
            "PR Responsiveness": 1,
        },
    },
}

SCORING_PROFILES = copy.deepcopy(DEFAULT_SCORING_PROFILES)


def apply_profile_overrides(profile_overrides: dict[str, dict[str, object]]) -> None:
    """
    Apply external scoring profile overrides on top of defaults.

    Args:
        profile_overrides: Profile definitions loaded from config.

    Raises:
        ValueError: If profile definitions are missing metrics or include invalid values.
    """
    global SCORING_PROFILES
    if not profile_overrides:
        SCORING_PROFILES = copy.deepcopy(DEFAULT_SCORING_PROFILES)
        return

    required_metrics = set(DEFAULT_SCORING_PROFILES["balanced"]["weights"].keys())
    merged = copy.deepcopy(DEFAULT_SCORING_PROFILES)

    for profile_key, profile_data in profile_overrides.items():
        if not isinstance(profile_data, dict):
            raise ValueError(
                f"Profile '{profile_key}' should be a table with name, description, and weights."
            )

        weights = profile_data.get("weights")
        if weights is None:
            if profile_key not in merged:
                raise ValueError(
                    f"Profile '{profile_key}' needs a weights table to be defined."
                )
            weights = merged[profile_key]["weights"]
        else:
            if not isinstance(weights, dict):
                raise ValueError(
                    f"Profile '{profile_key}' weights should be a table of metric names to integers."
                )

            missing_metrics = required_metrics - weights.keys()
            if missing_metrics:
                missing_list = ", ".join(sorted(missing_metrics))
                raise ValueError(
                    f"Profile '{profile_key}' is missing metrics: {missing_list}."
                )

            unknown_metrics = set(weights.keys()) - required_metrics
            if unknown_metrics:
                unknown_list = ", ".join(sorted(unknown_metrics))
                raise ValueError(
                    f"Profile '{profile_key}' includes unknown metrics: {unknown_list}."
                )

            invalid_weights = {
                metric: value
                for metric, value in weights.items()
                if type(value) is not int or value < 1
            }
            if invalid_weights:
                invalid_list = ", ".join(
                    f"{metric}={value}" for metric, value in invalid_weights.items()
                )
                raise ValueError(
                    "Profile weights must be integers greater than or equal to 1. "
                    f"Invalid values: {invalid_list}."
                )

        profile_name = profile_data.get(
            "name", merged.get(profile_key, {}).get("name", profile_key)
        )
        profile_description = profile_data.get(
            "description", merged.get(profile_key, {}).get("description", "")
        )
        merged[profile_key] = {
            "name": profile_name,
            "description": profile_description,
            "weights": weights,
        }

    SCORING_PROFILES = merged


def compute_weighted_total_score(
    metrics: list[Metric], profile: str = "balanced"
) -> int:
    """
    Computes a weighted total score based on individual metric weights.

    New scoring system (v2.0):
    - All metrics are scored on a 0-10 scale
    - Each metric has a weight (integer ≥ 1) defined per profile
    - Total score = Sum(metric_score × weight) / Sum(10 × weight) × 100
    - Result is normalized to 0-100 scale

    This approach provides:
    - Transparency: Users see individual scores (0-10) and weights
    - Flexibility: Easy to add new metrics - just assign a score and weight
    - Consistency: No confusion about why max_score differs per metric

    Profiles:
    - balanced: Balanced view (default)
    - security_first: Prioritizes security
    - contributor_experience: Focuses on community
    - long_term_stability: Emphasizes maintainer health

    Args:
        metrics: List of computed Metric instances
        profile: Scoring profile name (default: "balanced")

    Returns:
        Total score on 0-100 scale

    Raises:
        ValueError: If profile is not recognized
    """
    if profile not in SCORING_PROFILES:
        raise ValueError(
            f"Unknown profile '{profile}'. Available: {', '.join(SCORING_PROFILES.keys())}"
        )

    profile_config = SCORING_PROFILES[profile]
    weights = profile_config["weights"]

    # Calculate weighted sum
    weighted_score_sum = 0.0
    weighted_max_sum = 0.0

    for m in metrics:
        metric_weight = weights.get(m.name, 1)  # Default weight = 1 if not specified
        weighted_score_sum += m.score * metric_weight
        weighted_max_sum += 10 * metric_weight  # All metrics are now 0-10 scale

    # Normalize to 0-100 scale
    if weighted_max_sum > 0:
        total_score = (weighted_score_sum / weighted_max_sum) * 100
    else:
        total_score = 0.0

    return int(round(total_score))


def compare_scoring_profiles(metrics: list[Metric]) -> dict[str, dict[str, Any]]:
    """
    Compares scores across all available scoring profiles.

    Useful for understanding how different priorities affect the total score
    and identifying which profile best matches your use case.

    Args:
        metrics: List of computed Metric instances

    Returns:
        Dictionary with profile names as keys, containing:
        - name: Profile display name
        - description: Profile description
        - total_score: Total score (0-100) for this profile
        - weights: Metric weights used in this profile
    """
    comparison: dict[str, dict[str, Any]] = {}

    # Calculate total score for each profile
    for profile_key, profile_config in SCORING_PROFILES.items():
        total_score = compute_weighted_total_score(metrics, profile_key)

        comparison[profile_key] = {
            "name": profile_config["name"],
            "description": profile_config["description"],
            "total_score": total_score,
            "weights": profile_config["weights"],
        }

    return comparison


def get_metric_weights(profile: str = "balanced") -> dict[str, int]:
    """
    Returns the metric weights for a given profile.

    Args:
        profile: Scoring profile name (default: "balanced")

    Returns:
        Dictionary mapping metric names to their weights

    Raises:
        ValueError: If profile is not recognized
    """
    if profile not in SCORING_PROFILES:
        raise ValueError(
            f"Unknown profile '{profile}'. Available: {', '.join(SCORING_PROFILES.keys())}"
        )

    return SCORING_PROFILES[profile]["weights"]


# --- Metric Model Calculation Functions ---


def compute_metric_models(metrics: list[Metric]) -> list[MetricModel]:
    """
    Computes CHAOSS-aligned metric models from individual metrics.

    Models provide aggregated views for specific use cases:
    - Stability Model: focuses on project stability and security
    - Sustainability Model: focuses on long-term viability
    - Community Engagement Model: focuses on responsiveness and activity

    Args:
        metrics: List of computed individual metrics

    Returns:
        List of MetricModel instances
    """
    # Create a lookup dict for easy metric access
    metric_dict = {m.name: m for m in metrics}

    models = []

    # Stability Model: weights Contributor Redundancy, Security Signals,
    # Change Request Resolution, Community Health
    risk_metrics = [
        ("Contributor Redundancy", 0.4),
        ("Security Signals", 0.3),
        ("Change Request Resolution", 0.2),
        ("Community Health", 0.1),
    ]
    risk_score = 0
    risk_max = 0
    risk_observations = []

    for metric_name, weight in risk_metrics:
        if metric_name in metric_dict:
            m = metric_dict[metric_name]
            risk_score += m.score * weight
            risk_max += m.max_score * weight
            if m.score < m.max_score * 0.7:  # Below 70%
                risk_observations.append(f"{metric_name} needs attention")

    if not risk_observations:
        risk_obs = "All stability indicators are healthy."
    else:
        risk_obs = "; ".join(risk_observations[:2]) + "."  # Limit to 2

    models.append(
        MetricModel(
            name="Stability Model",
            score=int(risk_score),
            max_score=int(risk_max),
            observation=risk_obs,
        )
    )

    # Sustainability Model: weights Funding Signals, Maintainer Retention,
    # Release Rhythm, Recent Activity
    sustainability_metrics = [
        ("Funding Signals", 0.3),
        ("Maintainer Retention", 0.25),
        ("Release Rhythm", 0.25),
        ("Recent Activity", 0.2),
    ]
    sus_score = 0
    sus_max = 0
    sus_observations = []

    for metric_name, weight in sustainability_metrics:
        if metric_name in metric_dict:
            m = metric_dict[metric_name]
            sus_score += m.score * weight
            sus_max += m.max_score * weight
            if m.score >= m.max_score * 0.8:  # Above 80%
                sus_observations.append(f"{metric_name} is strong")

    if not sus_observations:
        sus_obs = "Sustainability signals need monitoring."
    else:
        sus_obs = "; ".join(sus_observations[:2]) + "."

    models.append(
        MetricModel(
            name="Sustainability Model",
            score=int(sus_score),
            max_score=int(sus_max),
            observation=sus_obs,
        )
    )

    # Community Engagement Model: weights Contributor Attraction,
    # Contributor Retention, Review Health, Community Health
    engagement_metrics = [
        ("Contributor Attraction", 0.3),
        ("Contributor Retention", 0.3),
        ("Review Health", 0.25),
        ("Community Health", 0.15),
    ]
    eng_score = 0
    eng_max = 0
    eng_observations = []

    for metric_name, weight in engagement_metrics:
        if metric_name in metric_dict:
            m = metric_dict[metric_name]
            eng_score += m.score * weight
            eng_max += m.max_score * weight
            if m.score >= m.max_score * 0.8:  # Above 80%
                eng_observations.append(f"{metric_name} is strong")

    if eng_max > 0:  # Only add model if we have at least one engagement metric
        if not eng_observations:
            eng_obs = "Community engagement signals need monitoring."
        else:
            eng_obs = "; ".join(eng_observations[:2]) + "."

        models.append(
            MetricModel(
                name="Community Engagement Model",
                score=int(eng_score),
                max_score=int(eng_max),
                observation=eng_obs,
            )
        )

    # Project Maturity Model (new): Documentation, Governance, Adoption
    maturity_metrics = [
        ("Documentation Presence", 0.30),
        ("Code of Conduct", 0.15),
        ("License Clarity", 0.20),
        ("Project Popularity", 0.20),
        ("Fork Activity", 0.15),
    ]
    mat_score = 0
    mat_max = 0
    mat_observations = []

    for metric_name, weight in maturity_metrics:
        if metric_name in metric_dict:
            m = metric_dict[metric_name]
            mat_score += m.score * weight
            mat_max += m.max_score * weight
            if m.score >= m.max_score * 0.8:  # Above 80%
                mat_observations.append(f"{metric_name} is strong")

    if mat_max > 0:
        if not mat_observations:
            mat_obs = "Project maturity signals need attention."
        else:
            mat_obs = "; ".join(mat_observations[:2]) + "."

        models.append(
            MetricModel(
                name="Project Maturity Model",
                score=int(mat_score),
                max_score=int(mat_max),
                observation=mat_obs,
            )
        )

    # Contributor Experience Model (new): PR handling and responsiveness
    exp_metrics = [
        ("PR Acceptance Ratio", 0.30),
        ("PR Responsiveness", 0.25),
        ("Issue Resolution Duration", 0.25),
        ("Review Health", 0.20),
    ]
    exp_score = 0
    exp_max = 0
    exp_observations = []

    for metric_name, weight in exp_metrics:
        if metric_name in metric_dict:
            m = metric_dict[metric_name]
            exp_score += m.score * weight
            exp_max += m.max_score * weight
            if m.score >= m.max_score * 0.8:
                exp_observations.append(f"{metric_name} is excellent")

    if exp_max > 0:
        if not exp_observations:
            exp_obs = "Contributor experience could be improved."
        else:
            exp_obs = "; ".join(exp_observations[:2]) + "."

        models.append(
            MetricModel(
                name="Contributor Experience Model",
                score=int(exp_score),
                max_score=int(exp_max),
                observation=exp_obs,
            )
        )

    return models


def extract_signals(metrics: list[Metric], repo_data: dict[str, Any]) -> dict[str, Any]:
    """
    Extracts raw signal values for transparency and debugging.

    Args:
        metrics: List of computed metrics
        repo_data: Raw repository data from GitHub API

    Returns:
        Dictionary of signal key-value pairs
    """
    signals = {}

    # Extract some key signals (non-sensitive)
    metric_dict = {m.name: m for m in metrics}

    if "Funding Signals" in metric_dict:
        funding_links = repo_data.get("fundingLinks", [])
        signals["funding_link_count"] = len(funding_links)

    if "Recent Activity" in metric_dict:
        pushed_at = repo_data.get("pushedAt")
        if pushed_at:
            from datetime import datetime

            try:
                pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
                now = datetime.now(pushed.tzinfo)
                signals["last_activity_days"] = (now - pushed).days
            except (ValueError, AttributeError):
                pass

    # Add contributor count if available
    default_branch = repo_data.get("defaultBranchRef")
    if default_branch:
        target = default_branch.get("target")
        if target:
            history = target.get("history", {}).get("edges", [])

            # Bot patterns to exclude (same as check_bus_factor)
            bot_keywords = [
                "bot",
                "action",
                "dependabot",
                "renovate",
                "github-actions",
                "ci-",
                "autorelease",
                "release-bot",
                "copilot",
                "actions-user",
            ]

            def is_bot(login: str) -> bool:
                """Check if login appears to be a bot."""
                lower = login.lower()
                return any(keyword in lower for keyword in bot_keywords)

            author_counts = {}
            for edge in history:
                node = edge.get("node", {})
                author = node.get("author", {})
                user = author.get("user")
                if user:
                    login = user.get("login")
                    if login and not is_bot(login):  # Exclude bots
                        author_counts[login] = author_counts.get(login, 0) + 1
            if author_counts:
                signals["contributor_count"] = len(author_counts)

    # Add new contributor metrics (Phase 4)
    if "Contributor Attraction" in metric_dict:
        m = metric_dict["Contributor Attraction"]
        # Extract new contributor count from message if available
        if "new contributor" in m.message.lower():
            import re

            match = re.search(r"(\d+) new contributor", m.message)
            if match:
                signals["new_contributors_6mo"] = int(match.group(1))

    if "Contributor Retention" in metric_dict:
        m = metric_dict["Contributor Retention"]
        # Extract retention percentage from message
        if "%" in m.message:
            import re

            match = re.search(r"(\d+)%", m.message)
            if match:
                signals["contributor_retention_rate"] = int(match.group(1))

    if "Review Health" in metric_dict:
        m = metric_dict["Review Health"]
        # Extract average review time from message
        if "Avg time to first review" in m.message:
            import re

            match = re.search(r"(\d+\.?\d*)h", m.message)
            if match:
                signals["avg_review_time_hours"] = float(match.group(1))

    return signals


# --- Batch Analysis Functions ---


def _get_batch_repository_query(repo_list: list[tuple[str, str]]) -> str:
    """Generate a GraphQL query for multiple repositories using aliases.

    Args:
        repo_list: List of (owner, name) tuples.

    Returns:
        GraphQL query string with aliases for each repository.
    """
    query_parts = ["query GetMultipleRepositories {"]

    for idx, (owner, name) in enumerate(repo_list):
        alias = f"repo{idx}"
        # Use the same comprehensive query as single repository analysis
        query_parts.append(f"""
  {alias}: repository(owner: "{owner}", name: "{name}") {{
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
      target {{
        ... on Commit {{
          history(first: 100) {{
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
    pullRequests(first: 50, states: MERGED, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
      edges {{
        node {{
          mergedAt
          createdAt
          mergedBy {{
            login
          }}
          reviews(first: 10) {{
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
    closedPullRequests: pullRequests(first: 50, states: CLOSED, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
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
    releases(first: 10, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
      edges {{
        node {{
          publishedAt
          tagName
        }}
      }}
    }}
    issues(first: 20, states: OPEN, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
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
    closedIssues: issues(first: 50, states: CLOSED, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
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
    vulnerabilityAlerts(first: 10) {{
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
    stargazerCount
    forkCount
    watchers {{
      totalCount
    }}
    forks(first: 20, orderBy: {{field: PUSHED_AT, direction: DESC}}) {{
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
      }}
    }}
    readmeLowerCase: object(expression: "HEAD:readme.md") {{
      ... on Blob {{
        byteSize
      }}
    }}
    readmeAllCaps: object(expression: "HEAD:README") {{
      ... on Blob {{
        byteSize
      }}
    }}
    contributingFile: object(expression: "HEAD:CONTRIBUTING.md") {{
      ... on Blob {{
        byteSize
      }}
    }}
    description
    homepageUrl
  }}""")

    query_parts.append("}")
    return "\n".join(query_parts)


def analyze_repositories_batch(
    repo_list: list[tuple[str, str] | tuple[str, str, str | None, str | None]],
    platform: str | None = None,
    *,
    profile: str = "balanced",
) -> dict[tuple[str, str], AnalysisResult | None]:
    """Analyze multiple repositories (now using individual VCS provider calls).

    Note: With VCS abstraction layer, batch optimization is handled by
    individual providers. This function now calls analyze_repository for each item.

    Args:
        repo_list: List of (owner, name) or (owner, name, platform, package_name).
        platform: Optional package platform for 2-tuple items.
        profile: Scoring profile name.

    Returns:
        Dictionary mapping (owner, name) to AnalysisResult or None.
    """
    if not repo_list:
        return {}

    results: dict[tuple[str, str], AnalysisResult | None] = {}

    def _normalize_batch_item(
        item: tuple[str, str] | tuple[str, str, str | None, str | None],
    ) -> tuple[str, str, str | None, str | None]:
        if len(item) == 2:
            owner, name = item
            return owner, name, platform or None, None
        if len(item) == 4:
            owner, name, item_platform, package_name = item
            return owner, name, item_platform, package_name
        raise ValueError(
            "Batch items must be (owner, name) or (owner, name, platform, package_name)."
        )

    normalized = [_normalize_batch_item(item) for item in repo_list]

    # Analyze each repository individually using VCS provider
    for owner, name, item_platform, package_name in normalized:
        try:
            result = analyze_repository(
                owner,
                name,
                platform=item_platform,
                package_name=package_name,
                profile=profile,
            )
            results[(owner, name)] = result
        except Exception as e:
            console.print(
                f"  [yellow]⚠️  Analysis issue for {owner}/{name}: {e}[/yellow]"
            )
            results[(owner, name)] = None

    return results


def _extract_sample_counts(repo_info: dict[str, Any]) -> dict[str, int]:
    """Extract actual sample counts from repository data."""
    # If sample_counts already provided by VCS provider, use that
    if "sample_counts" in repo_info and repo_info["sample_counts"]:
        return repo_info["sample_counts"]

    # Otherwise, extract from GraphQL structure (for GitHub or legacy data)
    samples = {}

    # Commits
    try:
        default_branch = repo_info.get("defaultBranchRef")
        if default_branch and default_branch.get("target"):
            commits_history = (
                default_branch.get("target", {}).get("history", {}).get("edges", [])
            )
            samples["commits"] = len(commits_history)
        else:
            samples["commits"] = 0
    except (TypeError, KeyError, AttributeError):
        samples["commits"] = 0

    # Merged PRs
    try:
        merged_prs = repo_info.get("pullRequests", {}).get("edges", [])
        samples["merged_prs"] = len(merged_prs)
    except (TypeError, KeyError):
        samples["merged_prs"] = 0

    # Closed PRs
    try:
        closed_prs = repo_info.get("closedPullRequests", {}).get("edges", [])
        samples["closed_prs"] = len(closed_prs)
    except (TypeError, KeyError):
        samples["closed_prs"] = 0

    # Open Issues
    try:
        open_issues = repo_info.get("issues", {}).get("edges", [])
        samples["open_issues"] = len(open_issues)
    except (TypeError, KeyError):
        samples["open_issues"] = 0

    # Closed Issues
    try:
        closed_issues = repo_info.get("closedIssues", {}).get("edges", [])
        samples["closed_issues"] = len(closed_issues)
    except (TypeError, KeyError):
        samples["closed_issues"] = 0

    # Releases
    try:
        releases = repo_info.get("releases", {}).get("edges", [])
        samples["releases"] = len(releases)
    except (TypeError, KeyError):
        samples["releases"] = 0

    # Vulnerability alerts
    try:
        vuln_alerts = repo_info.get("vulnerabilityAlerts", {}).get("edges", [])
        samples["vulnerability_alerts"] = len(vuln_alerts)
    except (TypeError, KeyError):
        samples["vulnerability_alerts"] = 0

    # Forks
    try:
        forks = repo_info.get("forks", {}).get("edges", [])
        samples["forks"] = len(forks)
    except (TypeError, KeyError):
        samples["forks"] = 0

    return samples


def _get_user_friendly_error(exc: Exception) -> str:
    """Convert technical exceptions to user-friendly messages."""
    exc_str = str(exc).lower()

    # Permission/authorization errors
    if "permission" in exc_str or "unauthorized" in exc_str:
        return (
            "Note: Unable to access this data (may require elevated token permissions)"
        )

    # Rate limit errors
    if "rate" in exc_str or "too many" in exc_str or "429" in exc_str:
        return "Note: GitHub API rate limit reached (will use cached data if available)"

    # Network/timeout errors
    if "timeout" in exc_str or "connection" in exc_str or "network" in exc_str:
        return "Note: Network timeout (check your internet connection)"

    # Data format/parsing errors
    if "json" in exc_str or "decode" in exc_str or "parse" in exc_str:
        return "Note: Unable to parse response from GitHub API"

    # Field not found errors
    if "keyerror" in exc_str or "not found" in exc_str:
        return "Note: Required data field unavailable from GitHub API"

    # Generic fallback
    return f"Note: Analysis incomplete ({exc.__class__.__name__})"


def _analyze_repository_data(
    owner: str,
    name: str,
    repo_info: dict[str, Any],
    platform: str | None = None,
    package_name: str | None = None,
    profile: str = "balanced",
) -> AnalysisResult:
    """Analyze repository data (extracted from GraphQL response).

    This is the core analysis logic separated from the GraphQL query.
    """
    metrics: list[Metric] = []
    skipped_metrics: list[str] = []
    repo_url = f"https://github.com/{owner}/{name}"
    context = MetricContext(
        owner=owner,
        name=name,
        repo_url=repo_url,
        platform=platform,
        package_name=package_name,
    )

    for spec in load_metric_specs():
        try:
            metric = spec.checker(repo_info, context)
            if metric is None:
                # Track skipped metrics (e.g., optional metrics without required API keys)
                skipped_metrics.append(spec.name)
                continue
            metrics.append(metric)
        except Exception as exc:
            if spec.error_log:
                console.print(spec.error_log.format(error=exc))
            if spec.on_error:
                metrics.append(spec.on_error(exc))
            else:
                user_friendly_msg = _get_user_friendly_error(exc)
                metrics.append(
                    Metric(
                        spec.name,
                        0,
                        10,
                        user_friendly_msg,
                        "Medium",
                    )
                )

    # Calculate total score using category-weighted scoring system
    total_score = compute_weighted_total_score(metrics, profile=profile)

    # Extract funding information directly from repo data
    funding_links = repo_info.get("fundingLinks", [])

    # Determine if project is community-driven
    # Projects with funding links are considered community-driven (seeking support)
    # Projects owned by Users (not Organizations) are also community-driven
    has_funding = len(funding_links) > 0
    is_user_owned = repo_info.get("owner", {}).get("__typename", "") == "User"
    is_community = has_funding or is_user_owned

    # Generate CHAOSS metric models
    models: list[MetricModel] = compute_metric_models(metrics)

    # Extract raw signals for transparency
    signals = extract_signals(metrics, repo_info)

    # Extract sample counts for transparency
    sample_counts = _extract_sample_counts(repo_info)

    # Note: Progress display is handled by CLI layer, not here
    # Individual completion messages would interfere with progress bar

    return AnalysisResult(
        repo_url=repo_url,
        total_score=total_score,
        metrics=metrics,
        funding_links=funding_links if is_community else [],
        is_community_driven=is_community,
        models=models,
        signals=signals,
        sample_counts=sample_counts,
        skipped_metrics=skipped_metrics if skipped_metrics else None,
    )


# --- Main Analysis Function ---


def analyze_repository(
    owner: str,
    name: str,
    platform: str | None = None,
    package_name: str | None = None,
    profile: str = "balanced",
    vcs_platform: str = "github",
) -> AnalysisResult:
    """
    Performs a full sustainability analysis on a given repository.

    Uses VCS abstraction layer to fetch repository data from various platforms
    (GitHub, GitLab, etc.), then calculates sustainability scores.

    Args:
        owner: Repository owner (username or organization)
        name: Repository name
        platform: Optional package platform (e.g., 'Pypi', 'NPM', 'Cargo')
                  for dependents analysis via Libraries.io
        package_name: Optional package name on the registry for dependents analysis
        profile: Scoring profile name
        vcs_platform: VCS platform ('github', 'gitlab', etc.). Default: 'github'

    Returns:
        AnalysisResult containing repo_url, total_score, and list of metrics

    Raises:
        ValueError: If credentials not set or repository not found
        httpx.HTTPStatusError: If VCS API returns an error
    """

    console.print(f"Analyzing [bold cyan]{owner}/{name}[/bold cyan]...")

    try:
        # Get VCS provider instance
        vcs = get_vcs_provider(vcs_platform)

        # Fetch normalized repository data from VCS
        vcs_data = vcs.get_repository_data(owner, name)

        # Convert VCS data to legacy format for metrics compatibility
        repo_info = _vcs_data_to_repo_info(vcs_data)

        # Use the shared analysis logic
        result = _analyze_repository_data(
            owner,
            name,
            repo_info,
            platform=platform,
            package_name=package_name,
            profile=profile,
        )

        # Update repo_url with actual VCS platform URL
        result = result._replace(repo_url=vcs.get_repository_url(owner, name))

        return result

    except httpx.HTTPStatusError as e:
        console.print(
            f"[yellow]Note: Unable to reach {vcs_platform.upper()} API ({e}).[/yellow]"
        )
        raise
    except ValueError as e:
        console.print(f"[yellow]Note: Unable to complete analysis: {e}[/yellow]")
        raise
    except Exception as e:
        console.print(f"[yellow]Note: Unexpected issue during analysis: {e}[/yellow]")
        raise


def analyze_dependencies(
    dependency_graph,
    database: dict[str, Any],
) -> dict[str, int]:
    """
    Analyze dependency packages and retrieve their scores.

    Args:
        dependency_graph: DependencyGraph object from dependency_graph module.
        database: Cached package database keyed by "ecosystem:package_name".

    Returns:
        Dictionary mapping package names to their scores.
    """
    scores: dict[str, int] = {}
    ecosystem = dependency_graph.ecosystem

    # Analyze direct dependencies
    for dep in dependency_graph.direct_dependencies:
        db_key = f"{ecosystem}:{dep.name}"
        if db_key in database:
            try:
                pkg_data = database[db_key]
                score = pkg_data.get("total_score", 0)
                scores[dep.name] = score
            except (KeyError, TypeError):
                # Skip if data format is unexpected
                pass

    return scores


if __name__ == "__main__":
    # Example usage:
    # Ensure you have a GITHUB_TOKEN in your environment.
    # $ export GITHUB_TOKEN="your_github_pat"
    # $ python src/oss_guard/core.py
    try:
        result = analyze_repository("psf", "requests")
        console = Console()
        console.print(result)
    except (ValueError, httpx.HTTPStatusError) as e:
        console = Console()
        console.print(f"[yellow]Note:[/yellow] Unable to complete analysis: {e}")
