"""Project popularity metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_project_popularity(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates project popularity using GitHub signals.

    Considers:
    - Star count (primary indicator)
    - Watcher count
    - Fork count (as adoption signal)

    Note: Popularity doesn't guarantee sustainability,
    but indicates community interest and potential support.

    Scoring:
    - 1000+ stars: 10/10 (Very popular)
    - 500-999 stars: 8/10 (Popular)
    - 100-499 stars: 6/10 (Growing)
    - 50-99 stars: 4/10 (Emerging)
    - 10-49 stars: 2/10 (Early)
    - <10 stars: 0/10 (New/niche)
    """
    max_score = 10

    star_count = repo_data.get("stargazerCount", 0)
    watcher_count = repo_data.get("watchers", {}).get("totalCount", 0)

    # Primary scoring based on stars
    if star_count >= 1000:
        score = max_score
        risk = "None"
        message = (
            f"Excellent: ⭐ {star_count} stars, {watcher_count} watchers. Very popular."
        )
    elif star_count >= 500:
        score = 8
        risk = "None"
        message = f"Popular: ⭐ {star_count} stars, {watcher_count} watchers."
    elif star_count >= 100:
        score = 6
        risk = "None"
        message = f"Growing: ⭐ {star_count} stars, {watcher_count} watchers. Active interest."
    elif star_count >= 50:
        score = 4
        risk = "Low"
        message = f"Emerging: ⭐ {star_count} stars. Building community."
    elif star_count >= 10:
        score = 2
        risk = "Low"
        message = f"Early: ⭐ {star_count} stars. New or niche project."
    else:
        score = 0
        risk = "Low"
        message = f"Note: ⭐ {star_count} stars. Very new or specialized project."

    return Metric("Project Popularity", score, max_score, message, risk)


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_project_popularity(repo_data)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Project Popularity",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "Low",
    )


METRIC = MetricSpec(
    name="Project Popularity",
    checker=_check,
    on_error=_on_error,
)
