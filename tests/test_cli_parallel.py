"""
Tests for parallel package analysis in the CLI.
"""

from unittest.mock import patch

from oss_sustain_guard.cli_utils.constants import ANALYSIS_VERSION
from oss_sustain_guard.commands.check import analyze_packages_parallel
from oss_sustain_guard.core import AnalysisResult, Metric
from oss_sustain_guard.repository import RepositoryReference


class FakeResolver:
    """Resolver stub that returns predefined repository references."""

    def __init__(self, mapping):
        self._mapping = mapping

    async def resolve_repository(self, package_name):
        return self._mapping.get(package_name)


async def test_analyze_packages_parallel_empty():
    """Empty inputs return an empty result list."""
    results, _ = await analyze_packages_parallel([], {})
    assert results == []


async def test_analyze_packages_parallel_single_uses_analyze_package():
    """Single package analysis avoids parallel execution."""
    result = AnalysisResult(
        repo_url="https://github.com/example/project",
        total_score=88,
        metrics=[Metric("Metric", 9, 10, "Observation", "Low")],
    )

    resolver = FakeResolver(
        {
            "project": RepositoryReference(
                provider="github",
                host="github.com",
                path="example/project",
                owner="example",
                name="project",
            ),
        }
    )

    with (
        patch(
            "oss_sustain_guard.commands.check.get_resolver",
            return_value=resolver,
        ),
        patch(
            "oss_sustain_guard.commands.check.analyze_package", return_value=result
        ) as mock_analyze,
    ):
        results, _ = await analyze_packages_parallel(
            [("python", "project")],
            {},
            profile="balanced",
            verbose=True,
            use_local_cache=False,
        )

    assert results == [result]
    mock_analyze.assert_called_once_with(
        package_name="project",
        ecosystem="python",
        db={},
        profile="balanced",
        verbose=True,
        use_local_cache=False,
        log_buffer={},
    )


async def test_analyze_packages_parallel_mixed_results():
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

    cached_result = AnalysisResult(
        repo_url="https://github.com/example/cached",
        total_score=100,  # Recalculated from metrics
        metrics=[Metric("Custom Metric", 10, 10, "Ok", "None")],
        ecosystem="python",
    )

    batch_result = AnalysisResult(
        repo_url="https://github.com/example/live",
        total_score=77,
        metrics=[Metric("Metric", 7, 10, "Observation", "Low")],
        ecosystem="python",
    )

    def analyze_side_effect(**kwargs):
        pkg_name = kwargs.get("package_name")
        if pkg_name == "cached":
            return cached_result
        elif pkg_name == "live":
            return batch_result
        else:
            return None

    with (
        patch(
            "oss_sustain_guard.commands.check.get_resolver",
            side_effect=lambda eco: resolver if eco == "python" else None,
        ),
        patch(
            "oss_sustain_guard.commands.check.analyze_package",
            side_effect=analyze_side_effect,
        ) as mock_analyze,
    ):
        results, _ = await analyze_packages_parallel(
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
        package_name="live",
        ecosystem="python",
        db=cached_db,
        profile="balanced",
        verbose=False,
        use_local_cache=True,
        log_buffer={},
    )


async def test_analyze_packages_parallel_non_batch_handles_exceptions():
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
        patch(
            "oss_sustain_guard.commands.check.get_resolver",
            return_value=resolver,
        ),
        patch(
            "oss_sustain_guard.commands.check.analyze_package",
            side_effect=analyze_side_effect,
        ),
    ):
        results, _ = await analyze_packages_parallel(
            [("python", "pkg1"), ("python", "pkg2")],
            {},
        )

    assert results[0] == result
    assert results[1] is None
