"""Output formatting functions for JSON and HTML reports."""

import json
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from oss_sustain_guard.config import get_lfx_config
from oss_sustain_guard.core import (
    AnalysisResult,
    analysis_result_to_dict,
    get_metric_weights,
)
from oss_sustain_guard.integrations.lfx import get_lfx_info

from .constants import console
from .helpers import _build_summary, _format_health_status, _summarize_observations
from .loaders import _load_report_template


def _write_json_results(
    results: list[AnalysisResult],
    profile: str,
    output_file: Path | None,
    demo_notice: str | None = None,
) -> None:
    """Write results as JSON to stdout or a file."""
    weights = get_metric_weights(profile)

    # Load LFX configuration
    lfx_config = get_lfx_config()
    lfx_enabled = lfx_config.get("enabled", True)
    lfx_project_map = lfx_config.get("project_map", {})
    lfx_badge_types = lfx_config.get("badges", ["health-score", "active-contributors"])

    # Add LFX info to results
    results_with_lfx = []
    for result in results:
        result_dict = analysis_result_to_dict(result)

        if lfx_enabled:
            repo_name = result.repo_url.replace("https://github.com/", "")
            package_id = (
                f"{result.ecosystem}:{repo_name}" if result.ecosystem else repo_name
            )

            lfx_info = get_lfx_info(
                package_name=package_id,
                repo_url=result.repo_url,
                config_mapping=lfx_project_map,
                badge_types=lfx_badge_types,
            )

            if lfx_info:
                result_dict["lfx"] = {
                    "project_slug": lfx_info.project_slug,
                    "project_url": lfx_info.project_url,
                    "badges": lfx_info.badges,
                    "resolution": lfx_info.resolution,
                }

        results_with_lfx.append(result_dict)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "profile_metadata": {
            "name": profile,
            "metric_weights": weights,
        },
        "summary": _build_summary(results),
        "results": results_with_lfx,
    }
    if demo_notice:
        payload["demo"] = True
        payload["demo_notice"] = demo_notice
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json_text + "\n", encoding="utf-8")
        console.print(f"[green]✅ JSON report saved to {output_file}[/green]")
    else:
        sys.stdout.write(json_text + "\n")


def _render_html_report(
    results: list[AnalysisResult],
    profile: str,
    demo_notice: str | None = None,
) -> str:
    """Render HTML report from template and results."""

    summary = _build_summary(results)
    demo_notice_block = ""
    if demo_notice:
        demo_notice_block = f'<div class="notice">{escape(demo_notice)}</div>'
    summary_cards = [
        ("Packages analyzed", str(summary["total_packages"])),
        ("Average score", f"{summary['average_score']:.1f}"),
        ("Healthy", str(summary["healthy_count"])),
        ("Monitor", str(summary["needs_attention_count"])),
        ("Needs support", str(summary["needs_support_count"])),
    ]
    summary_cards_html = "\n".join(
        f'<div class="summary-card"><div class="label">{escape(label)}</div>'
        f'<div class="value">{escape(value)}</div></div>'
        for label, value in summary_cards
    )

    # Load LFX configuration
    lfx_config = get_lfx_config()
    lfx_enabled = lfx_config.get("enabled", True)
    lfx_project_map = lfx_config.get("project_map", {})
    lfx_badge_types = lfx_config.get("badges", ["health-score", "active-contributors"])

    rows_html = []
    for result in results:
        status_text, status_color = _format_health_status(result.total_score)
        repo_name = result.repo_url.replace("https://github.com/", "")

        # Generate LFX info
        lfx_html = '<td class="lfx-not-available">—</td>'
        if lfx_enabled:
            # Create package identifier for LFX mapping
            package_id = (
                f"{result.ecosystem}:{repo_name}" if result.ecosystem else repo_name
            )

            lfx_info = get_lfx_info(
                package_name=package_id,
                repo_url=result.repo_url,
                config_mapping=lfx_project_map,
                badge_types=lfx_badge_types,
            )

            if lfx_info:
                # Build LFX cell HTML with link and badges
                badge_imgs = " ".join(
                    f'<img src="{badge_url}" alt="{badge_type}" title="{badge_type}">'
                    for badge_type, badge_url in lfx_info.badges.items()
                )
                lfx_html = (
                    f'<td><div class="lfx-badges">'
                    f'<a href="{lfx_info.project_url}" class="lfx-link" target="_blank" rel="noopener">View</a>'
                    f"{badge_imgs}"
                    f"</div></td>"
                )

        rows_html.append(
            "<tr>"
            f"<td>{escape(repo_name)}</td>"
            f"<td>{escape(result.ecosystem or 'unknown')}</td>"
            f'<td class="score {status_color}">{result.total_score}/100</td>'
            f'<td class="status {status_color}">{escape(status_text)}</td>'
            f"<td>{escape(_summarize_observations(result.metrics))}</td>"
            f"{lfx_html}"
            "</tr>"
        )

    json_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "profile_metadata": {
            "name": profile,
            "metric_weights": get_metric_weights(profile),
        },
        "summary": summary,
        "results": [analysis_result_to_dict(result) for result in results],
    }
    json_payload = json.dumps(
        json_payload,
        ensure_ascii=False,
        indent=2,
    )
    json_payload = json_payload.replace("</", "<\\/")

    template = _load_report_template()
    return template.format(
        report_title="OSS Sustain Guard Report",
        generated_at=escape(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
        profile=escape(profile),
        demo_notice_block=demo_notice_block,
        summary_cards=summary_cards_html,
        results_table_rows="\n".join(rows_html),
        results_json=json_payload,
    )


def _write_html_results(
    results: list[AnalysisResult],
    profile: str,
    output_file: Path | None,
    demo_notice: str | None = None,
) -> None:
    """Write results as HTML to a file."""
    output_path = output_file or Path("oss-sustain-guard-report.html")
    output_path = output_path.expanduser()
    if output_path.exists() and output_path.is_dir():
        raise IsADirectoryError(f"Output path is a directory: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_text = _render_html_report(results, profile, demo_notice=demo_notice)
    output_path.write_text(html_text, encoding="utf-8")
    console.print(f"[green]✅ HTML report saved to {output_path}[/green]")
