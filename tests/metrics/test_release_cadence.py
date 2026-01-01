"""
Tests for the release_cadence metric.
"""

from datetime import datetime, timedelta

from oss_sustain_guard.metrics.release_cadence import check_release_cadence


class TestReleaseCadenceMetric:
    """Test the check_release_cadence metric function."""

    def test_release_cadence_archived(self):
        """Test when repository is archived."""
        repo_data = {"isArchived": True}
        result = check_release_cadence(repo_data)
        assert result.name == "Release Rhythm"
        assert result.score == 10
        assert result.max_score == 10
        assert "Archived repository" in result.message
        assert result.risk == "None"

    def test_release_cadence_no_releases(self):
        """Test when no releases are found."""
        repo_data = {"releases": {"edges": []}}
        result = check_release_cadence(repo_data)
        assert result.name == "Release Rhythm"
        assert result.score == 0
        assert result.max_score == 10
        assert "No releases found" in result.message
        assert result.risk == "High"

    def test_release_cadence_active(self):
        """Test with recent release (<3 months)."""
        recent_date = datetime.now() - timedelta(days=30)
        repo_data = {
            "releases": {
                "edges": [
                    {
                        "node": {
                            "publishedAt": recent_date.isoformat() + "Z",
                            "tagName": "v1.0.0",
                        }
                    }
                ]
            }
        }
        result = check_release_cadence(repo_data)
        assert result.name == "Release Rhythm"
        assert result.score == 10
        assert result.max_score == 10
        assert "Active: Last release" in result.message
        assert result.risk == "None"

    def test_release_cadence_moderate(self):
        """Test with moderate release (3-6 months)."""
        moderate_date = datetime.now() - timedelta(days=120)
        repo_data = {
            "releases": {
                "edges": [
                    {
                        "node": {
                            "publishedAt": moderate_date.isoformat() + "Z",
                            "tagName": "v1.0.0",
                        }
                    }
                ]
            }
        }
        result = check_release_cadence(repo_data)
        assert result.name == "Release Rhythm"
        assert result.score == 7
        assert result.max_score == 10
        assert "Moderate: Last release" in result.message
        assert result.risk == "Low"

    def test_release_cadence_slow(self):
        """Test with slow release (6-12 months)."""
        slow_date = datetime.now() - timedelta(days=240)
        repo_data = {
            "releases": {
                "edges": [
                    {
                        "node": {
                            "publishedAt": slow_date.isoformat() + "Z",
                            "tagName": "v1.0.0",
                        }
                    }
                ]
            }
        }
        result = check_release_cadence(repo_data)
        assert result.name == "Release Rhythm"
        assert result.score == 4
        assert result.max_score == 10
        assert "Slow: Last release" in result.message
        assert result.risk == "Medium"

    def test_release_cadence_abandoned(self):
        """Test with old release (>12 months)."""
        old_date = datetime.now() - timedelta(days=400)
        repo_data = {
            "releases": {
                "edges": [
                    {
                        "node": {
                            "publishedAt": old_date.isoformat() + "Z",
                            "tagName": "v1.0.0",
                        }
                    }
                ]
            }
        }
        result = check_release_cadence(repo_data)
        assert result.name == "Release Rhythm"
        assert result.score == 0
        assert result.max_score == 10
        assert "Observe: Last release" in result.message
        assert result.risk == "High"
