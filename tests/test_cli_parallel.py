"""
Tests for parallel package analysis in the CLI.
"""

from unittest.mock import patch

from oss_sustain_guard.cli import ANALYSIS_VERSION, analyze_packages_parallel
from oss_sustain_guard.core import AnalysisResult, Metric
from oss_sustain_guard.repository import RepositoryReference


class DummyProgress:
    """Minimal Progress replacement for tests."""

    def __init__(self, *args, **kwargs):
        self._tasks = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add_task(self, description, total):
        task_id = len(self._tasks) + 1
        self._tasks[task_id] = {"total": total, "advanced": 0}
        return task_id

    def advance(self, task_id):
        self._tasks[task_id]["advanced"] += 1


class FakeResolver:
    """Resolver stub that returns predefined repository references."""

    def __init__(self, mapping):
        self._mapping = mapping

    def resolve_repository(self, package_name):
        return self._mapping.get(package_name)


def test_analyze_packages_parallel_empty():
    """Empty inputs return an empty result list."""
    results = analyze_packages_parallel([], {})
    assert results == []


def test_analyze_packages_parallel_single_uses_analyze_package():
    """Single package analysis avoids parallel execution."""
    result = AnalysisResult(
        repo_url="https://github.com/example/project",
        total_score=88,
        metrics=[Metric("Metric", 9, 10, "Observation", "Low")],
    )

    with patch(
        "oss_sustain_guard.cli.analyze_package", return_value=result
    ) as mock_analyze:
        results = analyze_packages_parallel(
            [("python", "project")],
            {},
            profile="balanced",
            show_dependencies=True,
            lockfile_path="lockfile",
            verbose=True,
            use_local_cache=False,
        )

    assert results == [result]
    mock_analyze.assert_called_once_with(
        "project",
        "python",
        {},
        "balanced",
        True,
        "lockfile",
        True,
        False,
    )


def test_analyze_packages_parallel_mixed_results():
    """Parallel analysis respects cache, unsupported resolvers, and missing results."""
    cached_db = {
        "python:cached": {
            "github_url": "https://github.com/example/cached",
            "analysis_version": ANALYSIS_VERSION,
            "metrics": [
                {
                    "name": "Custom Metric",
                    "score": 10,
                    "max_score": 10,
                    "message": "Ok",
                    "risk": "None",
                }
            ],
            "funding_links": [],
            "is_community_driven": False,
            "models": [],
            "signals": {},
        }
    }

    resolver = FakeResolver(
        {
            "live": RepositoryReference(
                provider="github",
                host="github.com",
                path="example/live",
                owner="example",
                name="live",
            ),
            "nongh": RepositoryReference(
                provider="gitlab",
                host="gitlab.com",
                path="example/nongh",
                owner="example",
                name="nongh",
            ),
        }
    )

    batch_result = AnalysisResult(
        repo_url="https://github.com/example/live",
        total_score=77,
        metrics=[Metric("Metric", 7, 10, "Observation", "Low")],
        ecosystem="python",
    )

    with (
        patch("oss_sustain_guard.cli.Progress", DummyProgress),
        patch(
            "oss_sustain_guard.cli.get_resolver",
            side_effect=lambda eco: resolver if eco == "python" else None,
        ),
        patch(
            "oss_sustain_guard.cli.analyze_package",
            side_effect=lambda pkg, *_args, **_kwargs: batch_result
            if pkg == "live"
            else None,
        ) as mock_analyze,
    ):
        results = analyze_packages_parallel(
            [
                ("python", "cached"),
                ("python", "live"),
                ("python", "nongh"),
                ("unknown", "missing"),
            ],
            cached_db,
            profile="balanced",
        )

    assert len(results) == 4
    assert results[0] is not None
    assert results[0].repo_url == "https://github.com/example/cached"
    assert results[0].total_score == 100
    assert results[0].ecosystem == "python"

    assert results[1] is not None
    assert results[1].repo_url == "https://github.com/example/live"
    assert results[1].ecosystem == "python"

    assert results[2] is None
    assert results[3] is None

    mock_analyze.assert_any_call(
        "live",
        "python",
        cached_db,
        "balanced",
        False,
        None,
        False,
        True,
    )


def test_analyze_packages_parallel_non_batch_handles_exceptions():
    """Non-batch mode handles per-package errors."""
    resolver = FakeResolver(
        {
            "pkg1": RepositoryReference(
                provider="github",
                host="github.com",
                path="example/pkg1",
                owner="example",
                name="pkg1",
            ),
            "pkg2": RepositoryReference(
                provider="github",
                host="github.com",
                path="example/pkg2",
                owner="example",
                name="pkg2",
            ),
        }
    )

    result = AnalysisResult(
        repo_url="https://github.com/example/pkg1",
        total_score=70,
        metrics=[Metric("Metric", 7, 10, "Observation", "Low")],
    )

    def analyze_side_effect(package_name, *args, **kwargs):
        if package_name == "pkg1":
            return result
        raise Exception("failure")

    with (
        patch("oss_sustain_guard.cli.Progress", DummyProgress),
        patch(
            "oss_sustain_guard.cli.get_resolver",
            return_value=resolver,
        ),
        patch(
            "oss_sustain_guard.cli.analyze_package",
            side_effect=analyze_side_effect,
        ),
    ):
        results = analyze_packages_parallel(
            [("python", "pkg1"), ("python", "pkg2")],
            {},
        )

    assert results[0] == result
    assert results[1] is None
