"""
Tests for the security_posture metric.
"""

from oss_sustain_guard.metrics.security_posture import check_security_posture


class TestSecurityPostureMetric:
    """Test the check_security_posture metric function."""

    def test_security_posture_critical_alerts(self):
        """Test with unresolved critical alerts."""
        repo_data = {
            "vulnerabilityAlerts": {
                "edges": [{"node": {"securityVulnerability": {"severity": "CRITICAL"}}}]
            }
        }
        result = check_security_posture(repo_data)
        assert result.name == "Security Signals"
        assert result.score == 0
        assert result.max_score == 10
        assert (
            "Attention needed: 1 unresolved CRITICAL vulnerability alert"
            in result.message
        )
        assert result.risk == "Critical"

    def test_security_posture_high_alerts_multiple(self):
        """Test with multiple unresolved high alerts."""
        repo_data = {
            "vulnerabilityAlerts": {
                "edges": [
                    {"node": {"securityVulnerability": {"severity": "HIGH"}}},
                    {"node": {"securityVulnerability": {"severity": "HIGH"}}},
                    {"node": {"securityVulnerability": {"severity": "HIGH"}}},
                ]
            }
        }
        result = check_security_posture(repo_data)
        assert result.name == "Security Signals"
        assert result.score == 3
        assert result.max_score == 10
        assert "High: 3 unresolved HIGH vulnerability alert" in result.message
        assert result.risk == "High"

    def test_security_posture_high_alerts_few(self):
        """Test with few unresolved high alerts."""
        repo_data = {
            "vulnerabilityAlerts": {
                "edges": [
                    {"node": {"securityVulnerability": {"severity": "HIGH"}}},
                ]
            }
        }
        result = check_security_posture(repo_data)
        assert result.name == "Security Signals"
        assert result.score == 5
        assert result.max_score == 10
        assert "Medium: 1 unresolved HIGH vulnerability alert" in result.message
        assert result.risk == "Medium"

    def test_security_posture_excellent(self):
        """Test with security policy and no alerts."""
        repo_data = {
            "isSecurityPolicyEnabled": True,
            "vulnerabilityAlerts": {"edges": []},
        }
        result = check_security_posture(repo_data)
        assert result.name == "Security Signals"
        assert result.score == 10
        assert result.max_score == 10
        assert (
            "Excellent: Security policy enabled, no unresolved alerts" in result.message
        )
        assert result.risk == "None"

    def test_security_posture_good(self):
        """Test with no unresolved alerts."""
        repo_data = {
            "isSecurityPolicyEnabled": True,
            "vulnerabilityAlerts": {"edges": []},
        }
        result = check_security_posture(repo_data)
        assert result.name == "Security Signals"
        assert result.score == 10
        assert result.max_score == 10
        assert (
            "Excellent: Security policy enabled, no unresolved alerts" in result.message
        )
        assert result.risk == "None"

    def test_security_posture_moderate(self):
        """Test with no security infrastructure."""
        repo_data = {}
        result = check_security_posture(repo_data)
        assert result.name == "Security Signals"
        assert result.score == 5
        assert result.max_score == 10
        assert "Moderate: No security policy detected" in result.message
        assert result.risk == "None"
