"""
Tests for CLI helper functions and report outputs.
"""

import json

import pytest

from oss_sustain_guard.cli_utils.cache_helpers import (
    cache_lockfile_dependencies,
    clear_lockfile_cache,
    get_cached_lockfile_dependencies,
)
from oss_sustain_guard.cli_utils.helpers import (
    _build_summary,
    _format_health_status,
    _summarize_observations,
)
from oss_sustain_guard.cli_utils.output import (
    _render_html_report,
    _write_html_results,
    _write_json_results,
)
from oss_sustain_guard.core import AnalysisResult, Metric


def test_lockfile_cache_round_trip(tmp_path):
    """Cache and retrieve lockfile dependencies."""
    lockfile_path = tmp_path / "uv.lock"
    package_deps = {"app": ["dep1", "dep2"]}

    clear_lockfile_cache()
    assert get_cached_lockfile_dependencies(lockfile_path, "app") is None

    cache_lockfile_dependencies(lockfile_path, package_deps)
    assert get_cached_lockfile_dependencies(lockfile_path, "app") == ["dep1", "dep2"]

    clear_lockfile_cache()
    assert get_cached_lockfile_dependencies(lockfile_path, "app") is None


def test_summarize_observations_truncates():
    """Summaries include only the first two high-priority observations."""
    metrics = [
        Metric("m1", 1, 10, "First", "High"),
        Metric("m2", 1, 10, "Second", "Critical"),
        Metric("m3", 1, 10, "Third", "High"),
        Metric("m4", 1, 10, "Low note", "Low"),
    ]

    summary = _summarize_observations(metrics)
    assert "First" in summary
    assert "Second" in summary
    assert "Third" not in summary
    assert "(+1 more)" in summary


def test_summarize_observations_no_concerns():
    """Summaries are supportive when no high-priority risks exist."""
    metrics = [Metric("m1", 8, 10, "All good", "Low")]
    assert _summarize_observations(metrics) == "No significant concerns detected"


def test_format_health_status_thresholds():
    """Health status thresholds map to the expected labels and colors."""
    assert _format_health_status(90) == ("Healthy", "green")
    assert _format_health_status(60) == ("Monitor", "yellow")
    assert _format_health_status(40) == ("Needs support", "red")


def test_build_summary_counts():
    """Summary statistics are computed from result totals."""
    results = [
        AnalysisResult(
            repo_url="https://github.com/example/healthy",
            total_score=80,
            metrics=[],
        ),
        AnalysisResult(
            repo_url="https://github.com/example/support",
            total_score=40,
            metrics=[],
        ),
    ]

    summary = _build_summary(results)
    assert summary["total_packages"] == 2
    assert summary["average_score"] == 60.0
    assert summary["healthy_count"] == 1
    assert summary["needs_attention_count"] == 0
    assert summary["needs_support_count"] == 1


def test_write_json_results_stdout(capsys):
    """JSON output is written to stdout when no file is provided."""
    results = [
        AnalysisResult(
            repo_url="https://github.com/example/project",
            total_score=75,
            metrics=[Metric("Metric", 7, 10, "Observation", "Low")],
        )
    ]

    _write_json_results(results, profile="balanced", output_file=None)

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert payload["profile"] == "balanced"
    assert payload["summary"]["total_packages"] == 1
    assert payload["results"][0]["repo_url"] == "https://github.com/example/project"


def test_write_json_results_file(tmp_path, capsys):
    """JSON output is written to a file when requested."""
    results = [
        AnalysisResult(
            repo_url="https://github.com/example/project",
            total_score=75,
            metrics=[Metric("Metric", 7, 10, "Observation", "Low")],
        )
    ]
    output_file = tmp_path / "report.json"

    _write_json_results(results, profile="balanced", output_file=output_file)

    assert output_file.exists()
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["profile"] == "balanced"
    assert payload["summary"]["total_packages"] == 1

    captured = capsys.readouterr()
    assert "JSON report saved to" in captured.out


def test_render_html_report_escapes_observations():
    """HTML report escapes observation text and renders table content."""
    metrics = [Metric("Metric", 3, 10, "Needs <attention>", "High")]
    results = [
        AnalysisResult(
            repo_url="https://github.com/example/project",
            total_score=45,
            metrics=metrics,
            ecosystem="python",
        )
    ]

    html = _render_html_report(results, profile="balanced")

    assert "OSS Sustain Guard Report" in html
    assert "example/project" in html
    assert "&lt;attention&gt;" in html


def test_write_html_results_file(tmp_path):
    """HTML report is written to the requested file."""
    results = [
        AnalysisResult(
            repo_url="https://github.com/example/project",
            total_score=75,
            metrics=[Metric("Metric", 7, 10, "Observation", "Low")],
        )
    ]
    output_file = tmp_path / "report.html"

    _write_html_results(results, profile="balanced", output_file=output_file)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "<html" in content
    assert "OSS Sustain Guard Report" in content


def test_write_html_results_directory_error(tmp_path):
    """HTML report refuses to overwrite a directory."""
    results = [
        AnalysisResult(
            repo_url="https://github.com/example/project",
            total_score=75,
            metrics=[Metric("Metric", 7, 10, "Observation", "Low")],
        )
    ]
    output_dir = tmp_path / "report_dir"
    output_dir.mkdir()

    with pytest.raises(IsADirectoryError):
        _write_html_results(results, profile="balanced", output_file=output_dir)
