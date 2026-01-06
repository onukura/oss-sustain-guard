"""Loaders for templates and demo data."""

import json
from importlib import resources

from oss_sustain_guard.core import AnalysisResult

from .constants import project_root
from .helpers import _analysis_result_from_payload


def _load_report_template() -> str:
    """Load the HTML report template from package data or docs fallback."""
    try:
        package_template = resources.files("oss_sustain_guard").joinpath(
            "assets/report_template.html"
        )
        if package_template.is_file():
            return package_template.read_text(encoding="utf-8")
    except (AttributeError, FileNotFoundError, ModuleNotFoundError):
        pass

    template_path = project_root / "docs" / "assets" / "report_template.html"
    if not template_path.exists():
        raise FileNotFoundError(
            "HTML report template not found in package data or docs/assets."
        )
    return template_path.read_text(encoding="utf-8")


def _load_demo_payload() -> dict:
    """Load demo data from package assets or examples directory."""
    candidates = []
    try:
        candidates.append(
            resources.files("oss_sustain_guard").joinpath(
                "assets/demo/demo_results.json"
            )
        )
    except (AttributeError, FileNotFoundError, ModuleNotFoundError):
        pass
    candidates.append(project_root / "examples" / "demo" / "demo_results.json")

    for candidate in candidates:
        try:
            if candidate.is_file():
                return json.loads(candidate.read_text(encoding="utf-8"))
        except OSError:
            continue

    raise FileNotFoundError(
        "Demo data not found. Expected assets/demo/demo_results.json."
    )


def _load_demo_results() -> tuple[list[AnalysisResult], str]:
    """Load and parse demo results."""
    payload = _load_demo_payload()
    if isinstance(payload, dict):
        profile = str(payload.get("profile", "balanced"))
        results_payload = payload.get("results", [])
    else:
        profile = "balanced"
        results_payload = payload

    if not isinstance(results_payload, list):
        raise ValueError("Demo data format is invalid.")

    results = [
        _analysis_result_from_payload(item)
        for item in results_payload
        if isinstance(item, dict)
    ]

    if not results:
        raise ValueError("Demo data is empty.")

    return results, profile
