"""
Tests for the security_posture metric.
"""

from oss_sustain_guard.metrics.security_posture import check_security_posture
from oss_sustain_guard.vcs.base import VCSRepositoryData


def _vcs_data(**overrides) -> VCSRepositoryData:
    data = VCSRepositoryData(
        is_archived=False,
        pushed_at=None,
        owner_type="User",
        owner_login="owner",
        owner_name=None,
        star_count=0,
        description=None,
        homepage_url=None,
        topics=[],
        readme_size=None,
        contributing_file_size=None,
        default_branch="main",
        watchers_count=0,
        open_issues_count=0,
        language=None,
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
        funding_links=[],
        forks=[],
        total_forks=0,
        ci_status=None,
        sample_counts={},
        raw_data=None,
    )
    return data._replace(**overrides)


class TestSecurityPostureMetric:
    """Test the check_security_posture metric function."""

    def test_security_posture_critical_alerts(self):
        """Test with unresolved critical alerts."""
        alerts = [{"securityVulnerability": {"severity": "CRITICAL"}}]
        result = check_security_posture(_vcs_data(vulnerability_alerts=alerts))
        assert result.name == "Security Signals"
        assert result.score == 0
        assert result.max_score == 10
        assert (
            "Attention needed: 1 unresolved critical-severity vulnerability alert"
            in result.message
        )
        assert result.risk == "Critical"

    def test_security_posture_high_alerts_multiple(self):
        """Test with multiple unresolved high alerts."""
        alerts = [
            {"securityVulnerability": {"severity": "HIGH"}},
            {"securityVulnerability": {"severity": "HIGH"}},
            {"securityVulnerability": {"severity": "HIGH"}},
        ]
        result = check_security_posture(_vcs_data(vulnerability_alerts=alerts))
        assert result.name == "Security Signals"
        assert result.score == 3
        assert result.max_score == 10
        assert (
            "Needs attention: 3 unresolved high-severity vulnerability alert"
            in result.message
        )
        assert result.risk == "High"

    def test_security_posture_high_alerts_few(self):
        """Test with few unresolved high alerts."""
        alerts = [{"securityVulnerability": {"severity": "HIGH"}}]
        result = check_security_posture(_vcs_data(vulnerability_alerts=alerts))
        assert result.name == "Security Signals"
        assert result.score == 5
        assert result.max_score == 10
        assert (
            "Monitor: 1 unresolved high-severity vulnerability alert" in result.message
        )
        assert result.risk == "Medium"

    def test_security_posture_excellent(self):
        """Test with security policy and no alerts."""
        vcs_data = _vcs_data(has_security_policy=True, vulnerability_alerts=[])
        result = check_security_posture(vcs_data)
        assert result.name == "Security Signals"
        assert result.score == 10
        assert result.max_score == 10
        assert (
            "Excellent: Security policy enabled, no unresolved alerts" in result.message
        )
        assert result.risk == "None"

    def test_security_posture_good(self):
        """Test with no unresolved alerts."""
        vcs_data = _vcs_data(has_security_policy=True, vulnerability_alerts=[])
        result = check_security_posture(vcs_data)
        assert result.name == "Security Signals"
        assert result.score == 10
        assert result.max_score == 10
        assert (
            "Excellent: Security policy enabled, no unresolved alerts" in result.message
        )
        assert result.risk == "None"

    def test_security_posture_moderate(self):
        """Test with no security infrastructure."""
        vcs_data = _vcs_data()
        result = check_security_posture(vcs_data)
        assert result.name == "Security Signals"
        assert result.score == 5
        assert result.max_score == 10
        assert "Moderate: No security policy detected" in result.message
        assert result.risk == "None"
