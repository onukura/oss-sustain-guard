"""
Tests for Ruby resolver.
"""

from unittest.mock import MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.ruby import RubyResolver


@pytest.fixture
def ruby_resolver():
    """Create a RubyResolver instance."""
    return RubyResolver()


def test_ecosystem_name(ruby_resolver):
    """Test that ecosystem_name returns 'ruby'."""
    assert ruby_resolver.ecosystem_name == "ruby"


@patch("httpx.Client.get")
def test_resolve_github_url_success(mock_get, ruby_resolver):
    """Test resolving a Ruby gem to GitHub URL."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "name": "rails",
        "version": "7.1.0",
        "source_code_uri": "https://github.com/rails/rails",
        "homepage_uri": "https://rubyonrails.org",
    }
    mock_get.return_value = mock_response

    result = ruby_resolver.resolve_github_url("rails")

    assert result == ("rails", "rails")
    mock_get.assert_called_once()


@patch("httpx.Client.get")
def test_resolve_github_url_with_git_suffix(mock_get, ruby_resolver):
    """Test resolving gem with .git suffix in URL."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "source_code_uri": "https://github.com/heartcombo/devise.git",
    }
    mock_get.return_value = mock_response

    result = ruby_resolver.resolve_github_url("devise")

    assert result == ("heartcombo", "devise")


@patch("httpx.Client.get")
def test_resolve_github_url_from_homepage(mock_get, ruby_resolver):
    """Test resolving from homepage_uri when source_code_uri is missing."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "homepage_uri": "https://github.com/rspec/rspec",
    }
    mock_get.return_value = mock_response

    result = ruby_resolver.resolve_github_url("rspec")

    assert result == ("rspec", "rspec")


@patch("httpx.Client.get")
def test_resolve_github_url_no_github(mock_get, ruby_resolver):
    """Test when gem has no GitHub URL."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "homepage_uri": "https://example.com",
    }
    mock_get.return_value = mock_response

    result = ruby_resolver.resolve_github_url("some-gem")

    assert result is None


@patch("httpx.Client.get")
def test_resolve_github_url_request_error(mock_get, ruby_resolver):
    """Test handling of request errors."""
    mock_get.side_effect = Exception("Network error")

    result = ruby_resolver.resolve_github_url("nonexistent")

    assert result is None


def test_parse_lockfile_gemfile_lock(tmp_path, ruby_resolver):
    """Test parsing Gemfile.lock."""
    lockfile = tmp_path / "Gemfile.lock"
    lockfile.write_text(
        """GEM
  remote: https://rubygems.org/
  specs:
    rails (7.1.0)
      actioncable (= 7.1.0)
      actionpack (= 7.1.0)
    devise (4.9.3)
      bcrypt (~> 3.0)
      orm_adapter (~> 0.1)
    rspec (3.12.0)
      rspec-core (~> 3.12.0)
      rspec-expectations (~> 3.12.0)

PLATFORMS
  ruby

DEPENDENCIES
  rails
  devise
  rspec
"""
    )

    packages = ruby_resolver.parse_lockfile(lockfile)

    assert len(packages) == 3
    assert packages[0].name == "rails"
    assert packages[0].version == "7.1.0"
    assert packages[0].ecosystem == "ruby"
    assert packages[1].name == "devise"
    assert packages[1].version == "4.9.3"
    assert packages[2].name == "rspec"
    assert packages[2].version == "3.12.0"


def test_parse_lockfile_not_found(ruby_resolver):
    """Test error when lockfile doesn't exist."""
    with pytest.raises(FileNotFoundError):
        ruby_resolver.parse_lockfile("/nonexistent/Gemfile.lock")


def test_parse_lockfile_invalid_format(tmp_path, ruby_resolver):
    """Test error with invalid lockfile format."""
    lockfile = tmp_path / "Gemfile.lock"
    lockfile.write_text("invalid content")

    # Should return empty list instead of raising error
    packages = ruby_resolver.parse_lockfile(lockfile)
    assert len(packages) == 0


def test_detect_lockfiles(tmp_path, ruby_resolver):
    """Test detecting Gemfile.lock."""
    gemfile_lock = tmp_path / "Gemfile.lock"
    gemfile_lock.touch()

    lockfiles = ruby_resolver.detect_lockfiles(str(tmp_path))

    assert len(lockfiles) == 1
    assert lockfiles[0].name == "Gemfile.lock"


def test_detect_lockfiles_none(tmp_path, ruby_resolver):
    """Test when no lockfiles exist."""
    lockfiles = ruby_resolver.detect_lockfiles(str(tmp_path))

    assert len(lockfiles) == 0


def test_get_manifest_files(ruby_resolver):
    """Test getting manifest file names."""
    manifests = ruby_resolver.get_manifest_files()

    assert "Gemfile" in manifests
    assert "Gemfile.lock" in manifests
