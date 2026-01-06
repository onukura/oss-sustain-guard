"""
Core analysis logic for OSS Sustain Guard.
"""

import copy
from typing import Any, NamedTuple

import httpx
from dotenv import load_dotenv
from rich.console import Console

from oss_sustain_guard.metrics import load_metric_specs

# Import all metrics to ensure they are registered via entry points.
# Note: These imports are required for metric plugin registration via entry points
# defined in pyproject.toml, even though they appear unused.
from oss_sustain_guard.metrics.attraction import (
    check_attraction,  # noqa: F401
)
from oss_sustain_guard.metrics.base import Metric, MetricContext
from oss_sustain_guard.metrics.bus_factor import check_bus_factor  # noqa: F401
from oss_sustain_guard.metrics.ci_status import check_ci_status  # noqa: F401
from oss_sustain_guard.metrics.code_of_conduct import (
    check_code_of_conduct,  # noqa: F401
)
from oss_sustain_guard.metrics.community_health import (
    check_community_health,  # noqa: F401
)
from oss_sustain_guard.metrics.documentation_presence import (
    check_documentation_presence,  # noqa: F401
)
from oss_sustain_guard.metrics.fork_activity import check_fork_activity  # noqa: F401
from oss_sustain_guard.metrics.funding import (
    check_funding,  # noqa: F401
    is_corporate_backed,  # noqa: F401
)
from oss_sustain_guard.metrics.issue_resolution_duration import (
    check_issue_resolution_duration,  # noqa: F401
)
from oss_sustain_guard.metrics.license_clarity import (
    check_license_clarity,  # noqa: F401
)
from oss_sustain_guard.metrics.maintainer_drain import (
    check_maintainer_drain,  # noqa: F401
)
from oss_sustain_guard.metrics.merge_velocity import (
    check_merge_velocity,  # noqa: F401
)
from oss_sustain_guard.metrics.organizational_diversity import (
    check_organizational_diversity,  # noqa: F401
)
from oss_sustain_guard.metrics.pr_acceptance_ratio import (
    check_pr_acceptance_ratio,  # noqa: F401
)
from oss_sustain_guard.metrics.pr_merge_speed import (
    check_pr_merge_speed,  # noqa: F401
)
from oss_sustain_guard.metrics.pr_responsiveness import (
    check_pr_responsiveness,  # noqa: F401
)
from oss_sustain_guard.metrics.project_popularity import (
    check_project_popularity,  # noqa: F401
)
from oss_sustain_guard.metrics.release_cadence import (
    check_release_cadence,  # noqa: F401
)
from oss_sustain_guard.metrics.retention import (
    check_retention,  # noqa: F401
)
from oss_sustain_guard.metrics.review_health import check_review_health  # noqa: F401
from oss_sustain_guard.metrics.security_posture import (
    check_security_posture,  # noqa: F401
)
from oss_sustain_guard.metrics.single_maintainer_load import (
    check_single_maintainer_load,  # noqa: F401
)
from oss_sustain_guard.metrics.stale_issue_ratio import (
    check_stale_issue_ratio,  # noqa: F401
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

    balanced_weights = DEFAULT_SCORING_PROFILES["balanced"]["weights"]
    if not isinstance(balanced_weights, dict):
        raise ValueError("Default balanced profile weights should be a dictionary.")
    required_metrics = set(balanced_weights.keys())
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
            merged_weights = merged[profile_key]["weights"]
            if not isinstance(merged_weights, dict):
                raise ValueError(
                    f"Profile '{profile_key}' weights should be a dictionary."
                )
            weights = merged_weights
        else:
            if not isinstance(weights, dict):
                raise ValueError(
                    f"Profile '{profile_key}' weights should be a table of metric names to integers."
                )

            missing_metrics = required_metrics - set(weights.keys())
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

    # Type guard: ensure weights is a dictionary
    if not isinstance(weights, dict):
        raise ValueError(f"Profile '{profile}' weights must be a dictionary")

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

    weights = SCORING_PROFILES[profile]["weights"]
    if not isinstance(weights, dict):
        raise ValueError(f"Profile '{profile}' weights must be a dictionary")
    return weights


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


def extract_signals(
    metrics: list[Metric], vcs_data: VCSRepositoryData
) -> dict[str, Any]:
    """
    Extracts raw signal values for transparency and debugging.

    Args:
        metrics: List of computed metrics
        vcs_data: Normalized VCS repository data

    Returns:
        Dictionary of signal key-value pairs
    """
    signals = {}

    # Extract some key signals (non-sensitive)
    metric_dict = {m.name: m for m in metrics}

    if "Funding Signals" in metric_dict:
        funding_links = vcs_data.funding_links or []
        signals["funding_link_count"] = len(funding_links)

    if "Recent Activity" in metric_dict:
        pushed_at = vcs_data.pushed_at
        if pushed_at:
            from datetime import datetime

            try:
                pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
                now = datetime.now(pushed.tzinfo)
                signals["last_activity_days"] = (now - pushed).days
            except (ValueError, AttributeError):
                pass

    # Add contributor count if available from commits
    if vcs_data.commits:
        from oss_sustain_guard.bot_detection import extract_login, is_bot
        from oss_sustain_guard.config import get_excluded_users

        # Get excluded users
        excluded_users = get_excluded_users()

        author_counts = {}
        for commit in vcs_data.commits:
            login = extract_login(commit)
            author = commit.get("author", {})
            email = author.get("email") if isinstance(author, dict) else None
            name = author.get("name") if isinstance(author, dict) else None
            if login and not is_bot(
                login, email=email, name=name, excluded_users=excluded_users
            ):  # Exclude bots
                author_counts[login] = author_counts.get(login, 0) + 1
        if author_counts:
            signals["contributor_count"] = len(author_counts)

    # Add new contributor metrics (Phase 4) - use metadata instead of parsing messages
    if "Contributor Attraction" in metric_dict:
        m = metric_dict["Contributor Attraction"]
        if m.metadata and "new_contributors" in m.metadata:
            signals["new_contributors_6mo"] = m.metadata["new_contributors"]

    if "Contributor Retention" in metric_dict:
        m = metric_dict["Contributor Retention"]
        if m.metadata and "retention_rate" in m.metadata:
            signals["contributor_retention_rate"] = m.metadata["retention_rate"]

    if "Review Health" in metric_dict:
        m = metric_dict["Review Health"]
        if m.metadata and "avg_review_time_hours" in m.metadata:
            signals["avg_review_time_hours"] = m.metadata["avg_review_time_hours"]

    return signals


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
    vcs_data: VCSRepositoryData,
    platform: str | None = None,
    package_name: str | None = None,
    profile: str = "balanced",
) -> AnalysisResult:
    """Analyze repository data using normalized VCS data.

    This is the core analysis logic that works with VCS-agnostic repository data.
    """
    metrics: list[Metric] = []
    skipped_metrics: list[str] = []
    repo_url = f"https://github.com/{owner}/{name}"  # Will be replaced by caller
    context = MetricContext(
        owner=owner,
        name=name,
        repo_url=repo_url,
        platform=platform,
        package_name=package_name,
    )

    for spec in load_metric_specs():
        try:
            checker = spec.checker
            metric = checker.check(vcs_data, context)
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

    # Extract funding information directly from VCS data
    funding_links = vcs_data.funding_links or []

    # Determine if project is community-driven
    # Projects with funding links are considered community-driven (seeking support)
    # Projects owned by Users (not Organizations) are also community-driven
    has_funding = len(funding_links) > 0
    is_user_owned = vcs_data.owner_type == "User"
    is_community = has_funding or is_user_owned

    # Generate CHAOSS metric models
    models: list[MetricModel] = compute_metric_models(metrics)

    # Extract raw signals for transparency
    signals = extract_signals(metrics, vcs_data)

    # Extract sample counts for transparency
    sample_counts = vcs_data.sample_counts or {}

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


async def analyze_repository(
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
        platform: Optional package platform for registry-aware metrics.
        package_name: Optional package name for registry-aware metrics.
        profile: Scoring profile name
        vcs_platform: VCS platform ('github', 'gitlab', etc.). Default: 'github'

    Returns:
        AnalysisResult containing repo_url, total_score, and list of metrics

    Raises:
        ValueError: If credentials not set or repository not found
        httpx.HTTPStatusError: If VCS API returns an error
    """
    from oss_sustain_guard.config import get_days_lookback, get_scan_depth

    console.print(f"Analyzing [bold cyan]{owner}/{name}[/bold cyan]...")

    try:
        # Get VCS provider instance
        vcs = get_vcs_provider(vcs_platform)

        # Get scan configuration
        scan_depth = get_scan_depth()
        days_lookback = get_days_lookback()

        # Fetch normalized repository data from VCS with scan configuration
        vcs_data = await vcs.get_repository_data(
            owner, name, scan_depth=scan_depth, days_lookback=days_lookback
        )

        # Use the shared analysis logic with VCS data
        result = _analyze_repository_data(
            owner,
            name,
            vcs_data,
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
