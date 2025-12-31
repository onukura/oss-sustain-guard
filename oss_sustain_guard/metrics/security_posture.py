"""Security signals metric."""

from typing import Any

from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


def check_security_posture(repo_data: dict[str, Any]) -> Metric:
    """
    Evaluates the security posture of the repository.

    Considers:
    - Presence of security policy (SECURITY.md)
    - Unresolved vulnerability alerts (Critical/High)
    - Overall security awareness

    Scoring (0-10 scale):
    - Critical alerts unresolved: 0/10 (Critical)
    - High alerts unresolved (3+): 3/10 (High risk)
    - High alerts unresolved (1-2): 5/10 (Medium risk)
    - Security policy + no alerts: 10/10 (Excellent)
    - No alerts: 8/10 (Good)
    - No security infrastructure: 5/10 (Moderate)
    """
    max_score = 10

    has_security_policy = repo_data.get("isSecurityPolicyEnabled", False)
    vulnerability_alerts = repo_data.get("vulnerabilityAlerts", {}).get("edges", [])

    # Count unresolved alerts by severity
    critical_count = 0
    high_count = 0

    for edge in vulnerability_alerts:
        node = edge.get("node", {})
        dismissed_at = node.get("dismissedAt")
        if dismissed_at:
            # Alert was dismissed/resolved
            continue

        severity = node.get("securityVulnerability", {}).get("severity", "").upper()
        if severity == "CRITICAL":
            critical_count += 1
        elif severity == "HIGH":
            high_count += 1

    # Scoring logic (0-10 scale)
    if critical_count > 0:
        score = 0
        risk = "Critical"
        message = (
            f"Attention needed: {critical_count} unresolved CRITICAL vulnerability alert(s). "
            f"Review and action recommended."
        )
    elif high_count >= 3:
        score = 3  # 5/15 → 3/10
        risk = "High"
        message = (
            f"High: {high_count} unresolved HIGH vulnerability alert(s). "
            f"Review and patch recommended."
        )
    elif high_count > 0:
        score = 5  # 8/15 → 5/10
        risk = "Medium"
        message = (
            f"Medium: {high_count} unresolved HIGH vulnerability alert(s). "
            f"Monitor and address."
        )
    elif has_security_policy:
        score = max_score
        risk = "None"
        message = "Excellent: Security policy enabled, no unresolved alerts."
    elif vulnerability_alerts:
        # Has alerts infrastructure but all resolved
        score = 8  # 12/15 → 8/10
        risk = "None"
        message = "Good: No unresolved vulnerabilities detected."
    else:
        # No security policy, no alerts (may not be using Dependabot)
        score = 5  # 8/15 → 5/10
        risk = "None"
        message = "Moderate: No security policy detected. Consider adding SECURITY.md."

    return Metric("Security Signals", score, max_score, message, risk)


def _check(repo_data: dict[str, Any], _context: MetricContext) -> Metric:
    return check_security_posture(repo_data)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Security Signals",
        0,
        15,
        f"Note: Analysis incomplete - {error}",
        "High",
    )


METRIC = MetricSpec(
    name="Security Signals",
    checker=_check,
    on_error=_on_error,
)
