"""Project popularity metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class ProjectPopularityChecker(MetricChecker):
    """Evaluate project popularity using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates project popularity using VCS signals.

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

        star_count = vcs_data.star_count
        watcher_count = vcs_data.watchers_count

        # Primary scoring based on stars
        if star_count >= 1000:
            score = max_score
            risk = "None"
            message = f"Excellent: ⭐ {star_count} stars, {watcher_count} watchers. Very popular."
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


_CHECKER = ProjectPopularityChecker()


def check_project_popularity(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


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
    checker=_CHECKER,
    on_error=_on_error,
)
