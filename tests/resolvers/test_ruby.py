"""
Tests for Ruby resolver.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oss_sustain_guard.resolvers.ruby import RubyResolver


@pytest.fixture
def ruby_resolver():
    """Create a RubyResolver instance."""
    return RubyResolver()


def test_ecosystem_name(ruby_resolver):
    """Test that ecosystem_name returns 'ruby'."""
    assert ruby_resolver.ecosystem_name == "ruby"


@patch("httpx.AsyncClient.get")
async def test_resolve_github_url_success(mock_get, ruby_resolver):
    """Test resolving a Ruby gem to GitHub URL."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "name": "rails",
        "version": "7.1.0",
        "source_code_uri": "https://github.com/rails/rails",
        "homepage_uri": "https://rubyonrails.org",
    }
    mock_get.return_value = mock_response

    result = await ruby_resolver.resolve_github_url("rails")

    assert result == ("rails", "rails")
    mock_get.assert_called_once()


@patch("httpx.AsyncClient.get")
async def test_resolve_github_url_with_git_suffix(mock_get, ruby_resolver):
    """Test resolving gem with .git suffix in URL."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "source_code_uri": "https://github.com/heartcombo/devise.git",
    }
    mock_get.return_value = mock_response

    result = await ruby_resolver.resolve_github_url("devise")

    assert result == ("heartcombo", "devise")


@patch("httpx.AsyncClient.get")
async def test_resolve_github_url_from_homepage(mock_get, ruby_resolver):
    """Test resolving from homepage_uri when source_code_uri is missing."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "homepage_uri": "https://github.com/rspec/rspec",
    }
    mock_get.return_value = mock_response

    result = await ruby_resolver.resolve_github_url("rspec")

    assert result == ("rspec", "rspec")


@patch("httpx.AsyncClient.get")
async def test_resolve_github_url_no_github(mock_get, ruby_resolver):
    """Test when gem has no GitHub URL."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "homepage_uri": "https://example.com",
    }
    mock_get.return_value = mock_response

    result = await ruby_resolver.resolve_github_url("some-gem")

    assert result is None


@patch("httpx.AsyncClient.get")
async def test_resolve_github_url_request_error(mock_get, ruby_resolver):
    """Test handling of request errors."""
    mock_get.side_effect = Exception("Network error")

    result = await ruby_resolver.resolve_github_url("nonexistent")

    assert result is None


async def test_parse_lockfile_gemfile_lock(tmp_path, ruby_resolver):
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

    packages = await ruby_resolver.parse_lockfile(lockfile)

    assert len(packages) == 3
    assert packages[0].name == "rails"
    assert packages[0].version == "7.1.0"
    assert packages[0].ecosystem == "ruby"
    assert packages[1].name == "devise"
    assert packages[1].version == "4.9.3"
    assert packages[2].name == "rspec"
    assert packages[2].version == "3.12.0"


async def test_parse_lockfile_not_found(ruby_resolver):
    """Test error when lockfile doesn't exist."""
    with pytest.raises(FileNotFoundError):
        await ruby_resolver.parse_lockfile("/nonexistent/Gemfile.lock")


async def test_parse_lockfile_invalid_format(tmp_path, ruby_resolver):
    """Test error with invalid lockfile format."""
    lockfile = tmp_path / "Gemfile.lock"
    lockfile.write_text("invalid content")

    packages = await ruby_resolver.parse_lockfile(lockfile)
    assert len(packages) == 0


@patch("aiofiles.open")
async def test_parse_lockfile_read_error(mock_aiofiles_open, tmp_path, ruby_resolver):
    """Test error reading Gemfile.lock."""
    lockfile = tmp_path / "Gemfile.lock"
    lockfile.write_text("GEM\n  specs:\n")

    mock_file = AsyncMock()
    mock_file.__aenter__.return_value = mock_file
    mock_file.__aexit__.return_value = None
    mock_file.read.side_effect = OSError("read error")

    mock_aiofiles_open.return_value = mock_file

    with pytest.raises(ValueError, match="Failed to parse Gemfile.lock"):
        await ruby_resolver.parse_lockfile(lockfile)


async def test_detect_lockfiles(tmp_path, ruby_resolver):
    """Test detecting Gemfile.lock."""
    gemfile_lock = tmp_path / "Gemfile.lock"
    gemfile_lock.touch()

    lockfiles = await ruby_resolver.detect_lockfiles(str(tmp_path))

    assert len(lockfiles) == 1
    assert lockfiles[0].name == "Gemfile.lock"


async def test_detect_lockfiles_none(tmp_path, ruby_resolver):
    """Test when no lockfiles exist."""
    lockfiles = await ruby_resolver.detect_lockfiles(str(tmp_path))

    assert len(lockfiles) == 0


async def test_get_manifest_files(ruby_resolver):
    """Test getting manifest file names."""
    manifests = await ruby_resolver.get_manifest_files()

    assert "Gemfile" in manifests
    assert "Gemfile.lock" in manifests


async def test_parse_manifest_gemfile(tmp_path, ruby_resolver):
    """Test parsing Gemfile."""
    manifest = tmp_path / "Gemfile"
    manifest.write_text(
        "source 'https://rubygems.org'\n"
        "\n"
        "gem 'rails', '~> 7.0.0'\n"
        'gem "devise"\n'
        "# comment\n"
        "group :development do\n"
        "  gem 'byebug'\n"
        "end\n"
    )

    packages = await ruby_resolver.parse_manifest(manifest)

    names = {pkg.name for pkg in packages}
    assert names == {"rails", "devise", "byebug"}


async def test_parse_manifest_not_found(ruby_resolver):
    """Test missing Gemfile."""
    with pytest.raises(FileNotFoundError):
        await ruby_resolver.parse_manifest("/missing/Gemfile")


async def test_parse_manifest_unknown(tmp_path, ruby_resolver):
    """Test unknown manifest type."""
    manifest = tmp_path / "Gemfile.lock"
    manifest.touch()

    with pytest.raises(ValueError, match="Unknown Ruby manifest file type"):
        await ruby_resolver.parse_manifest(manifest)


@patch("aiofiles.open")
async def test_parse_manifest_read_error(mock_aiofiles_open, tmp_path, ruby_resolver):
    """Test error reading Gemfile."""
    manifest = tmp_path / "Gemfile"
    manifest.write_text("gem 'rails'\n")

    mock_file = AsyncMock()
    mock_file.__aenter__.return_value = mock_file
    mock_file.__aexit__.return_value = None
    mock_file.read.side_effect = OSError("read error")

    mock_aiofiles_open.return_value = mock_file

    with pytest.raises(ValueError, match="Failed to parse Gemfile"):
        await ruby_resolver.parse_manifest(manifest)
