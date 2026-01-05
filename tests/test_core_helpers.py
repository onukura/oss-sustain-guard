"""
Additional tests for core helpers and error handling.
"""

from __future__ import annotations

import copy
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import oss_sustain_guard.core as core
from oss_sustain_guard.core import (
    AnalysisResult,
    Metric,
    MetricModel,
    analysis_result_to_dict,
    analyze_dependencies,
    analyze_repository,
    apply_profile_overrides,
    compare_scoring_profiles,
    compute_metric_models,
    compute_weighted_total_score,
    extract_signals,
    get_metric_weights,
)
from oss_sustain_guard.metrics.base import MetricSpec


@pytest.fixture(autouse=True)
def reset_scoring_profiles():
    """Restore scoring profiles after each test."""
    original = copy.deepcopy(core.SCORING_PROFILES)
    yield
    core.SCORING_PROFILES = original


class _LegacyMetric:
    def __init__(self) -> None:
        self.name = "Legacy Metric"
        self.score = 4
        self.max_score = 10
        self.message = "Legacy message"
        self.risk = "Low"


class _LegacyModel:
    def __init__(self) -> None:
        self.name = "Legacy Model"
        self.score = 6
        self.max_score = 10
        self.observation = "Legacy observation"


def test_analysis_result_to_dict_handles_mixed_metrics_and_models():
    result = AnalysisResult(
        repo_url="https://github.com/example/repo",
        total_score=88,
        metrics=[
            Metric("Metric A", 7, 10, "Message A", "Low"),
            Metric("Metric B", 4, 10, "B", "Medium"),
            Metric("Legacy Metric", 4, 10, "Legacy message", "Low"),
        ],
        funding_links=[{"platform": "GitHub", "url": "https://github.com/sponsors/x"}],
        is_community_driven=True,
        models=[
            MetricModel("Model A", 6, 10, "Observation A"),
            MetricModel("Model B", 3, 10, "B"),
            MetricModel("Legacy Model", 6, 10, "Legacy observation"),
        ],
        signals={"signal": 1},
        dependency_scores={"dep": 80},
        ecosystem="python",
    )

    data = analysis_result_to_dict(result)

    assert data["repo_url"] == "https://github.com/example/repo"
    assert data["metrics"][0]["name"] == "Metric A"
    assert data["metrics"][1]["message"] == "B"
    assert data["metrics"][2]["risk"] == "Low"
    assert data["models"][0]["observation"] == "Observation A"
    assert data["models"][2]["name"] == "Legacy Model"
    assert data["dependency_scores"] == {"dep": 80}


def test_apply_profile_overrides_resets_defaults():
    core.SCORING_PROFILES = {
        "custom": {"name": "Custom", "description": "", "weights": {}}
    }
    apply_profile_overrides({})
    assert core.SCORING_PROFILES == core.DEFAULT_SCORING_PROFILES


def test_apply_profile_overrides_rejects_non_dict_profile():
    with pytest.raises(ValueError, match="needs a weights table"):
        apply_profile_overrides({"bad": {}})


def test_apply_profile_overrides_requires_weights_for_new_profile():
    with pytest.raises(ValueError, match="needs a weights table"):
        apply_profile_overrides({"new_profile": {"name": "New"}})


def test_apply_profile_overrides_rejects_missing_metrics():
    balanced_weights = core.DEFAULT_SCORING_PROFILES["balanced"]["weights"]
    assert isinstance(balanced_weights, dict)
    weights = dict(balanced_weights)
    weights.pop(next(iter(weights)))
    with pytest.raises(ValueError, match="missing metrics"):
        apply_profile_overrides({"balanced": {"weights": weights}})


def test_apply_profile_overrides_rejects_unknown_metrics():
    balanced_weights = core.DEFAULT_SCORING_PROFILES["balanced"]["weights"]
    assert isinstance(balanced_weights, dict)
    weights = dict(balanced_weights)
    weights["Unknown Metric"] = 2
    with pytest.raises(ValueError, match="includes unknown metrics"):
        apply_profile_overrides({"balanced": {"weights": weights}})


def test_apply_profile_overrides_rejects_invalid_weights():
    balanced_weights = core.DEFAULT_SCORING_PROFILES["balanced"]["weights"]
    assert isinstance(balanced_weights, dict)
    weights = dict(balanced_weights)
    weights["Contributor Redundancy"] = 0
    with pytest.raises(ValueError, match="Invalid values"):
        apply_profile_overrides({"balanced": {"weights": weights}})


def test_apply_profile_overrides_accepts_valid_override():
    balanced_weights = core.DEFAULT_SCORING_PROFILES["balanced"]["weights"]
    assert isinstance(balanced_weights, dict)
    weights = dict(balanced_weights)
    weights["Contributor Redundancy"] = 5
    apply_profile_overrides(
        {
            "balanced": {
                "name": "Balanced Updated",
                "description": "Custom description",
                "weights": weights,
            }
        }
    )
    assert core.SCORING_PROFILES["balanced"]["name"] == "Balanced Updated"
    balanced_weights = core.SCORING_PROFILES["balanced"]["weights"]
    assert isinstance(balanced_weights, dict)
    assert balanced_weights["Contributor Redundancy"] == 5


def test_compute_weighted_total_score_empty_metrics_returns_zero():
    assert compute_weighted_total_score([]) == 0


def test_compute_weighted_total_score_unknown_profile_raises():
    with pytest.raises(ValueError, match="Unknown profile"):
        compute_weighted_total_score(
            [Metric("Metric A", 5, 10, "msg", "Low")], "missing"
        )


def test_compare_scoring_profiles_returns_expected_structure():
    metrics = [Metric("Contributor Redundancy", 5, 10, "msg", "Low")]
    comparison = compare_scoring_profiles(metrics)
    assert "balanced" in comparison
    assert comparison["balanced"]["total_score"] >= 0
    assert "weights" in comparison["balanced"]


def test_get_metric_weights_unknown_profile_raises():
    with pytest.raises(ValueError, match="Unknown profile"):
        get_metric_weights("missing")


def test_compute_metric_models_with_observations():
    metrics = [
        Metric("Contributor Redundancy", 3, 10, "msg", "Low"),
        Metric("Security Signals", 2, 10, "msg", "Low"),
        Metric("Change Request Resolution", 1, 10, "msg", "Low"),
        Metric("Community Health", 1, 10, "msg", "Low"),
        Metric("Funding Signals", 10, 10, "msg", "Low"),
        Metric("Maintainer Retention", 9, 10, "msg", "Low"),
        Metric("Release Rhythm", 8, 10, "msg", "Low"),
        Metric("Recent Activity", 9, 10, "msg", "Low"),
        Metric("Contributor Attraction", 9, 10, "msg", "Low"),
        Metric("Contributor Retention", 9, 10, "msg", "Low"),
        Metric("Review Health", 9, 10, "msg", "Low"),
        Metric("Documentation Presence", 9, 10, "msg", "Low"),
        Metric("Code of Conduct", 9, 10, "msg", "Low"),
        Metric("License Clarity", 9, 10, "msg", "Low"),
        Metric("Project Popularity", 9, 10, "msg", "Low"),
        Metric("Fork Activity", 9, 10, "msg", "Low"),
        Metric("PR Acceptance Ratio", 9, 10, "msg", "Low"),
        Metric("PR Responsiveness", 9, 10, "msg", "Low"),
        Metric("Issue Resolution Duration", 9, 10, "msg", "Low"),
    ]

    models = compute_metric_models(metrics)
    model_names = {model.name for model in models}

    assert "Stability Model" in model_names
    assert "Sustainability Model" in model_names
    assert "Community Engagement Model" in model_names
    assert "Project Maturity Model" in model_names
    assert "Contributor Experience Model" in model_names
    assert any("needs attention" in model.observation for model in models)
    assert any("is strong" in model.observation for model in models)
    assert any("is excellent" in model.observation for model in models)


def test_compute_metric_models_with_monitoring_messages():
    metrics = [
        Metric("Contributor Redundancy", 9, 10, "msg", "Low"),
        Metric("Security Signals", 9, 10, "msg", "Low"),
        Metric("Change Request Resolution", 9, 10, "msg", "Low"),
        Metric("Funding Signals", 6, 10, "msg", "Low"),
        Metric("Maintainer Retention", 6, 10, "msg", "Low"),
        Metric("Release Rhythm", 6, 10, "msg", "Low"),
        Metric("Recent Activity", 6, 10, "msg", "Low"),
        Metric("Contributor Attraction", 6, 10, "msg", "Low"),
        Metric("Contributor Retention", 6, 10, "msg", "Low"),
        Metric("Review Health", 6, 10, "msg", "Low"),
        Metric("Documentation Presence", 6, 10, "msg", "Low"),
        Metric("Code of Conduct", 6, 10, "msg", "Low"),
        Metric("License Clarity", 6, 10, "msg", "Low"),
        Metric("Project Popularity", 6, 10, "msg", "Low"),
        Metric("Fork Activity", 6, 10, "msg", "Low"),
        Metric("PR Acceptance Ratio", 6, 10, "msg", "Low"),
        Metric("PR Responsiveness", 6, 10, "msg", "Low"),
        Metric("Issue Resolution Duration", 6, 10, "msg", "Low"),
    ]

    models = {model.name: model for model in compute_metric_models(metrics)}

    assert (
        models["Stability Model"].observation == "All stability indicators are healthy."
    )
    assert models["Sustainability Model"].observation == (
        "Sustainability signals need monitoring."
    )
    assert models["Community Engagement Model"].observation == (
        "Community engagement signals need monitoring."
    )
    assert models["Project Maturity Model"].observation == (
        "Project maturity signals need attention."
    )
    assert models["Contributor Experience Model"].observation == (
        "Contributor experience could be improved."
    )


def test_extract_signals_parses_repo_and_metric_messages():
    # Use metadata instead of parsing messages for structured data
    from oss_sustain_guard.vcs.base import VCSRepositoryData

    metrics = [
        Metric("Funding Signals", 5, 10, "msg", "Low", None),
        Metric("Recent Activity", 5, 10, "msg", "Low", None),
        Metric(
            "Contributor Attraction",
            5,
            10,
            "2 new contributors in 6 months",
            "Low",
            {"new_contributors": 2, "total_contributors": 10},
        ),
        Metric(
            "Contributor Retention",
            5,
            10,
            "Retention at 75%",
            "Low",
            {
                "retention_rate": 75,
                "retained_contributors": 3,
                "earlier_contributors": 4,
            },
        ),
        Metric(
            "Review Health",
            5,
            10,
            "Avg time to first review: 3.5h",
            "Low",
            {"avg_review_time_hours": 3.5, "avg_review_count": 2.1},
        ),
    ]

    vcs_data = VCSRepositoryData(
        is_archived=False,
        pushed_at="2024-01-01T00:00:00Z",
        owner_type="User",
        owner_login="testuser",
        owner_name="Test User",
        star_count=100,
        description="Test repo",
        homepage_url=None,
        topics=[],
        readme_size=None,
        contributing_file_size=None,
        default_branch="main",
        watchers_count=10,
        open_issues_count=5,
        language="Python",
        commits=[
            {"author": {"user": {"login": "alice"}}},
            {"author": {"user": {"login": "dependabot[bot]"}}},
            {"author": {"user": {"login": "bob"}}},
        ],
        total_commits=3,
        merged_prs=[],
        closed_prs=[],
        total_merged_prs=0,
        releases=[],
        open_issues=[],
        closed_issues=[],
        total_closed_issues=0,
        vulnerability_alerts=None,
        has_security_policy=False,
        code_of_conduct=None,
        license_info=None,
        has_wiki=False,
        has_issues=True,
        has_discussions=False,
        funding_links=[{"platform": "GitHub", "url": "https://github.com/sponsors/x"}],
        forks=[],
        total_forks=0,
        ci_status=None,
        sample_counts={},
        raw_data=None,
    )

    signals = extract_signals(metrics, vcs_data)

    assert signals["funding_link_count"] == 1
    assert isinstance(signals["last_activity_days"], int)
    assert signals["contributor_count"] == 2
    assert signals["new_contributors_6mo"] == 2
    assert signals["contributor_retention_rate"] == 75
    assert signals["avg_review_time_hours"] == 3.5


def test_analyze_repository_data_handles_metric_errors():
    from oss_sustain_guard.metrics.base import MetricChecker
    from oss_sustain_guard.vcs.base import VCSRepositoryData

    class FailingChecker(MetricChecker):
        def check(
            self, vcs_data: VCSRepositoryData, _context: core.MetricContext
        ) -> Metric:
            raise ValueError("broken")

    def on_error_metric(exc: Exception) -> Metric:
        return Metric("Recover", 1, 10, f"Recovered: {exc}", "Low")

    failing_checker = FailingChecker()
    specs = [
        MetricSpec(
            name="First",
            checker=failing_checker,
            on_error=on_error_metric,
            error_log="Note: {error}",
        ),
        MetricSpec(
            name="Second",
            checker=failing_checker,
            on_error=on_error_metric,
            error_log="",
        ),
    ]

    vcs_data = VCSRepositoryData(
        is_archived=False,
        pushed_at=None,
        owner_type="Organization",
        owner_login="testorg",
        owner_name="Test Org",
        star_count=100,
        description="Test repo",
        homepage_url=None,
        topics=[],
        readme_size=None,
        contributing_file_size=None,
        default_branch="main",
        watchers_count=10,
        open_issues_count=5,
        language="Python",
        commits=[],
        total_commits=0,
        merged_prs=[],
        closed_prs=[],
        total_merged_prs=0,
        releases=[],
        open_issues=[],
        closed_issues=[],
        total_closed_issues=0,
        vulnerability_alerts=None,
        has_security_policy=False,
        code_of_conduct=None,
        license_info=None,
        has_wiki=False,
        has_issues=True,
        has_discussions=False,
        funding_links=[{"platform": "GitHub", "url": "https://github.com/sponsors/x"}],
        forks=[],
        total_forks=0,
        ci_status=None,
        sample_counts={},
        raw_data=None,
    )

    with (
        patch("oss_sustain_guard.core.load_metric_specs", return_value=specs),
        patch("oss_sustain_guard.core.console.print") as mock_print,
    ):
        result = core._analyze_repository_data("owner", "repo", vcs_data)

    assert len(result.metrics) == 2
    assert result.is_community_driven is True
    assert result.funding_links == [
        {"platform": "GitHub", "url": "https://github.com/sponsors/x"}
    ]
    assert any("Note: " in call.args[0] for call in mock_print.call_args_list)


async def test_analyze_repository_handles_http_status_error():
    error = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("POST", "https://example.com"),
        response=httpx.Response(500),
    )
    with patch("oss_sustain_guard.core.get_vcs_provider") as mock_vcs:
        mock_provider = mock_vcs.return_value
        mock_provider.get_repository_data = AsyncMock(side_effect=error)
        with pytest.raises(httpx.HTTPStatusError):
            await analyze_repository("owner", "repo")


async def test_analyze_repository_handles_unexpected_error():
    with patch("oss_sustain_guard.core.get_vcs_provider") as mock_vcs:
        mock_provider = mock_vcs.return_value
        mock_provider.get_repository_data = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            await analyze_repository("owner", "repo")


def test_analyze_dependencies_handles_bad_data():
    class Dep:
        def __init__(self, name: str) -> None:
            self.name = name

    class DepGraph:
        def __init__(self) -> None:
            self.ecosystem = "python"
            self.direct_dependencies = [Dep("alpha"), Dep("beta"), Dep("gamma")]

    class BadData:
        def get(self, _key: str, _default: int = 0) -> int:
            raise TypeError("bad data")

    database = {
        "python:alpha": {"total_score": 80},
        "python:beta": BadData(),
    }

    scores = analyze_dependencies(DepGraph(), database)

    assert scores == {"alpha": 80}
