"""Security signals metric."""

from oss_sustain_guard.metrics.base import (
    Metric,
    MetricChecker,
    MetricContext,
    MetricSpec,
)
from oss_sustain_guard.vcs.base import VCSRepositoryData

_LEGACY_CONTEXT = MetricContext(owner="unknown", name="unknown", repo_url="")


class SecurityPostureChecker(MetricChecker):
    """Evaluate security posture using normalized VCS data."""

    def check(self, vcs_data: VCSRepositoryData, _context: MetricContext) -> Metric:
        """
        Evaluates the security posture of the repository.

        Considers:
        - Presence of security policy (SECURITY.md)
        - Unresolved vulnerability alerts (critical/high severity)
        - Overall security awareness

        Scoring (0-10 scale):
        - Critical alerts unresolved: 0/10 (Critical)
        - High alerts unresolved (3+): 3/10 (High)
        - High alerts unresolved (1-2): 5/10 (Medium)
        - Security policy + no alerts: 10/10 (Excellent)
        - No alerts: 8/10 (Good)
        - No security infrastructure: 5/10 (Moderate)
        """
        max_score = 10

        has_security_policy = vcs_data.has_security_policy
        vulnerability_alerts = vcs_data.vulnerability_alerts or []

        # Count unresolved alerts by severity
        critical_count = 0
        high_count = 0

        for node in vulnerability_alerts:
            if not isinstance(node, dict):
                continue
            dismissed_at = node.get("dismissedAt")
            if dismissed_at:
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
                f"Attention needed: {critical_count} unresolved critical-severity vulnerability alert(s). "
                f"Review and action recommended."
            )
        elif high_count >= 3:
            score = 3  # 5/15 → 3/10
            risk = "High"
            message = (
                f"Needs attention: {high_count} unresolved high-severity vulnerability alert(s). "
                f"Review and patch recommended."
            )
        elif high_count > 0:
            score = 5  # 8/15 → 5/10
            risk = "Medium"
            message = (
                f"Monitor: {high_count} unresolved high-severity vulnerability alert(s). "
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
            message = (
                "Moderate: No security policy detected. Consider adding SECURITY.md."
            )

        return Metric("Security Signals", score, max_score, message, risk)


_CHECKER = SecurityPostureChecker()


def check_security_posture(repo_data: VCSRepositoryData) -> Metric:
    return _CHECKER.check(repo_data, _LEGACY_CONTEXT)


def _on_error(error: Exception) -> Metric:
    return Metric(
        "Security Signals",
        0,
        10,
        f"Note: Analysis incomplete - {error}",
        "High",
    )


METRIC = MetricSpec(
    name="Security Signals",
    checker=_CHECKER,
    on_error=_on_error,
)
