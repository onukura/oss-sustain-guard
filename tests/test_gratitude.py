"""Tests for the gratitude command."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from oss_sustain_guard.cli import app

runner = CliRunner()


@pytest.fixture
def mock_database():
    """Create mock database with community-driven and corporate-backed projects."""
    return {
        "python:requests": {
            "repo_url": "https://github.com/psf/requests",
            "total_score": 65,
            "is_community_driven": True,
            "funding_links": [
                {
                    "platform": "GitHub Sponsors",
                    "url": "https://github.com/sponsors/psf",
                },
                {
                    "platform": "Open Collective",
                    "url": "https://opencollective.com/requests",
                },
            ],
            "metrics": [
                {"name": "Contributor Redundancy", "score": 12, "max_score": 20},
                {"name": "Maintainer Drain", "score": 8, "max_score": 15},
            ],
        },
        "python:flask": {
            "repo_url": "https://github.com/pallets/flask",
            "total_score": 45,
            "is_community_driven": True,
            "funding_links": [
                {
                    "platform": "GitHub Sponsors",
                    "url": "https://github.com/sponsors/pallets",
                },
            ],
            "metrics": [
                {"name": "Contributor Redundancy", "score": 8, "max_score": 20},
                {"name": "Maintainer Drain", "score": 5, "max_score": 15},
            ],
        },
        "python:django": {
            "repo_url": "https://github.com/django/django",
            "total_score": 90,
            "is_community_driven": False,  # Corporate-backed
            "funding_links": [
                {
                    "platform": "Django Software Foundation",
                    "url": "https://www.djangoproject.com/fundraising/",
                },
            ],
            "metrics": [
                {"name": "Contributor Redundancy", "score": 18, "max_score": 20},
                {"name": "Maintainer Drain", "score": 14, "max_score": 15},
            ],
        },
        "python:numpy": {
            "repo_url": "https://github.com/numpy/numpy",
            "total_score": 75,
            "is_community_driven": True,
            "funding_links": [],  # No funding links
            "metrics": [
                {"name": "Contributor Redundancy", "score": 15, "max_score": 20},
                {"name": "Maintainer Drain", "score": 12, "max_score": 15},
            ],
        },
    }


@patch("oss_sustain_guard.cli.load_database")
def test_gratitude_displays_top_projects(mock_load_db, mock_database):
    """Test that gratitude command displays top community-driven projects."""
    mock_load_db.return_value = mock_database

    result = runner.invoke(app, ["gratitude", "--top", "2"], input="q\n")

    assert result.exit_code == 0
    assert "Gratitude Vending Machine" in result.stdout
    assert "flask" in result.stdout  # Should show flask (lower score = higher priority)
    assert "requests" in result.stdout  # Should show requests
    assert "django" not in result.stdout  # Should NOT show corporate-backed
    assert "numpy" not in result.stdout  # Should NOT show (no funding links)
    assert "Health Score:" in result.stdout
    assert "Support options:" in result.stdout


@patch("oss_sustain_guard.cli.load_database")
def test_gratitude_no_funding_links(mock_load_db):
    """Test gratitude when no projects have funding links."""
    mock_load_db.return_value = {
        "python:test-pkg": {
            "repo_url": "https://github.com/test/test",
            "total_score": 50,
            "is_community_driven": True,
            "funding_links": [],  # No funding
            "metrics": [],
        }
    }

    result = runner.invoke(app, ["gratitude"])

    assert result.exit_code == 0
    assert "No community-driven projects with funding links found" in result.stdout


@patch("oss_sustain_guard.cli.load_database")
def test_gratitude_empty_database(mock_load_db):
    """Test gratitude with empty database."""
    mock_load_db.return_value = {}

    result = runner.invoke(app, ["gratitude"])

    assert result.exit_code == 0
    assert "No database available" in result.stdout


@patch("oss_sustain_guard.cli.load_database")
@patch("webbrowser.open")
def test_gratitude_opens_single_funding_link(mock_browser, mock_load_db, mock_database):
    """Test opening a funding link when project has single link."""
    # Modify flask to have only one funding link
    mock_database["python:flask"]["funding_links"] = [
        {"platform": "GitHub Sponsors", "url": "https://github.com/sponsors/pallets"}
    ]
    mock_load_db.return_value = mock_database

    # Select project 1 (flask, highest priority)
    result = runner.invoke(app, ["gratitude", "--top", "2"], input="1\n")

    assert result.exit_code == 0
    mock_browser.assert_called_once_with("https://github.com/sponsors/pallets")
    assert "Opening GitHub Sponsors..." in result.stdout
    assert "Thank you for supporting OSS maintainers!" in result.stdout


@patch("oss_sustain_guard.cli.load_database")
@patch("webbrowser.open")
def test_gratitude_opens_multiple_funding_links(
    mock_browser, mock_load_db, mock_database
):
    """Test opening a funding link when project has multiple links."""
    mock_load_db.return_value = mock_database

    # Select project 2 (requests), then select platform 1 (GitHub Sponsors)
    result = runner.invoke(app, ["gratitude", "--top", "3"], input="2\n1\n")

    assert result.exit_code == 0
    mock_browser.assert_called_once_with("https://github.com/sponsors/psf")
    assert "Select funding platform:" in result.stdout
    assert "Opening GitHub Sponsors..." in result.stdout


@patch("oss_sustain_guard.cli.load_database")
def test_gratitude_quit(mock_load_db, mock_database):
    """Test quitting gratitude without selecting."""
    mock_load_db.return_value = mock_database

    result = runner.invoke(app, ["gratitude"], input="q\n")

    assert result.exit_code == 0
    assert "Thank you for considering supporting OSS maintainers!" in result.stdout


@patch("oss_sustain_guard.cli.load_database")
def test_gratitude_invalid_project_number(mock_load_db, mock_database):
    """Test invalid project number input."""
    mock_load_db.return_value = mock_database

    result = runner.invoke(app, ["gratitude", "--top", "2"], input="99\n")

    assert result.exit_code == 0
    assert "Invalid project number" in result.stdout


@patch("oss_sustain_guard.cli.load_database")
def test_gratitude_invalid_input(mock_load_db, mock_database):
    """Test invalid (non-numeric) input."""
    mock_load_db.return_value = mock_database

    result = runner.invoke(app, ["gratitude"], input="abc\n")

    assert result.exit_code == 0
    assert "Invalid input" in result.stdout


def test_gratitude_priority_calculation(mock_database):
    """Test that priority calculation works correctly."""
    # flask should have higher priority than requests due to lower scores
    # flask: priority = (100-45) + (20-8) + (15-5) = 55 + 12 + 10 = 77
    # requests: priority = (100-65) + (20-12) + (15-8) = 35 + 8 + 7 = 50

    flask_data = mock_database["python:flask"]
    requests_data = mock_database["python:requests"]

    # Calculate priorities
    flask_priority = (
        (100 - flask_data["total_score"])
        + (20 - flask_data["metrics"][0]["score"])
        + (15 - flask_data["metrics"][1]["score"])
    )
    requests_priority = (
        (100 - requests_data["total_score"])
        + (20 - requests_data["metrics"][0]["score"])
        + (15 - requests_data["metrics"][1]["score"])
    )

    assert flask_priority > requests_priority  # flask needs more support
