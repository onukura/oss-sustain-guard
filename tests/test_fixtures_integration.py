"""
Integration tests using real-world dependency files as fixtures.

These tests use actual package.json, requirements.txt, Cargo.toml, etc.
from popular open-source projects to validate multi-language support.
"""

import json
from pathlib import Path
from unittest.mock import patch

import tomli
from typer.testing import CliRunner

from oss_sustain_guard.cli import app
from oss_sustain_guard.core import AnalysisResult, Metric

# Fixture directory path
FIXTURES_DIR = Path(__file__).parent / "fixtures"

runner = CliRunner()


class TestJavaScriptFixtures:
    """Test with real JavaScript package.json files."""

    def test_parse_package_json(self):
        """Test parsing package.json fixture."""
        package_json_path = FIXTURES_DIR / "javascript" / "npm" / "package.json"
        assert package_json_path.exists(), "package.json fixture not found"

        with open(package_json_path) as f:
            data = json.load(f)

        # Verify expected packages are present
        assert "react" in data["dependencies"]
        assert "express" in data["dependencies"]
        assert "typescript" in data["devDependencies"]

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_npm_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking npm packages from package.json fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        package_json_path = FIXTURES_DIR / "javascript" / "npm" / "package.json"
        with open(package_json_path) as f:
            data = json.load(f)

        # Extract package names
        packages = list(data["dependencies"].keys())[:3]  # Test first 3

        for pkg in packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg}",
                    total_score=75,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=75,
                            max_score=100,
                            message=f"Package {pkg} analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"npm:{pkg}", "--insecure"])
                if result.exit_code != 0:
                    print(f"\n=== Error for {pkg} ===")
                    print(f"Exit code: {result.exit_code}")
                    print(f"Output: {result.output}")
                    if result.exception:
                        print(f"Exception: {result.exception}")
                        import traceback

                        traceback.print_exception(
                            type(result.exception),
                            result.exception,
                            result.exception.__traceback__,
                        )
                assert result.exit_code == 0


class TestPythonFixtures:
    """Test with real Python requirements.txt files."""

    def test_parse_requirements_txt(self):
        """Test parsing requirements.txt fixture."""
        requirements_path = FIXTURES_DIR / "python" / "pip" / "requirements.txt"
        assert requirements_path.exists(), "requirements.txt fixture not found"

        with open(requirements_path) as f:
            lines = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]

        # Verify expected packages
        package_names = [line.split("==")[0] for line in lines]
        assert "Django" in package_names
        assert "requests" in package_names
        assert "pytest" in package_names

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_python_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking Python packages from requirements.txt fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        requirements_path = FIXTURES_DIR / "python" / "pip" / "requirements.txt"
        with open(requirements_path) as f:
            lines = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]

        packages = [line.split("==")[0] for line in lines[:3]]  # Test first 3

        for pkg in packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg}",
                    total_score=80,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=80,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"python:{pkg}", "--insecure"])
                assert result.exit_code == 0

    def test_parse_poetry_toml(self):
        """Test parsing pyproject.toml fixture."""
        pyproject_path = FIXTURES_DIR / "python" / "poetry" / "pyproject.toml"
        if not pyproject_path.exists():
            return  # Skip if fixture doesn't exist yet

        # Simple check that file exists and is valid TOML
        with open(pyproject_path, "rb") as f:
            data = tomli.load(f)

        # Verify it has poetry dependencies
        assert "tool" in data
        assert "poetry" in data["tool"]
        assert "dependencies" in data["tool"]["poetry"]

    def test_parse_poetry_lock(self):
        """Test parsing pyproject.lock fixture."""
        pyproject_lock_path = FIXTURES_DIR / "python" / "poetry" / "pyproject.lock"
        if not pyproject_lock_path.exists():
            return  # Skip if fixture doesn't exist yet

        # Poetry lock is JSON format
        with open(pyproject_lock_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify structure
        assert "package" in data
        assert isinstance(data["package"], list)
        # Check for some expected packages
        package_names = [pkg["name"] for pkg in data["package"]]
        assert "django" in package_names
        assert "requests" in package_names

    def test_parse_pipfile(self):
        """Test parsing Pipfile fixture."""
        pipfile_path = FIXTURES_DIR / "python" / "pipenv" / "Pipfile"
        if not pipfile_path.exists():
            return  # Skip if fixture doesn't exist yet

        # Simple check that file exists and is valid TOML
        with open(pipfile_path, "rb") as f:
            data = tomli.load(f)

        # Verify it has packages section
        assert "packages" in data
        assert isinstance(data["packages"], dict)
        # Check for some expected packages
        assert "django" in data["packages"]

    def test_parse_pipfile_lock(self):
        """Test parsing Pipfile.lock fixture."""
        pipfile_lock_path = FIXTURES_DIR / "python" / "pipenv" / "Pipfile.lock"
        if not pipfile_lock_path.exists():
            return  # Skip if fixture doesn't exist yet

        # Pipfile.lock is JSON format
        with open(pipfile_lock_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify structure
        assert "_meta" in data
        assert "default" in data
        assert isinstance(data["default"], dict)
        # Check for some expected packages
        assert "django" in data["default"]
        assert "requests" in data["default"]

    def test_parse_uv_toml(self):
        """Test parsing uv.toml fixture."""
        uv_toml_path = FIXTURES_DIR / "python" / "uv" / "uv.toml"
        if not uv_toml_path.exists():
            return  # Skip if fixture doesn't exist yet

        # Simple check that file exists and is valid TOML
        with open(uv_toml_path, "rb") as f:
            data = tomli.load(f)

        # Verify it has dependencies section
        assert "dependencies" in data
        assert isinstance(data["dependencies"], dict)
        # Check for some expected packages
        assert "fastapi" in data["dependencies"]
        assert "uvicorn" in data["dependencies"]

    def test_parse_uv_lock(self):
        """Test parsing uv.lock fixture."""
        uv_lock_path = FIXTURES_DIR / "python" / "uv" / "uv.lock"
        if not uv_lock_path.exists():
            return  # Skip if fixture doesn't exist yet

        # uv.lock is JSON format
        with open(uv_lock_path, "rb") as f:
            data = tomli.load(f)

        # Verify structure
        assert "package" in data
        assert isinstance(data["package"], list)
        # Check for some expected packages
        package_names = [pkg["name"] for pkg in data["package"]]
        assert "fastapi" in package_names
        assert "numpy" in package_names


class TestRustFixtures:
    """Test with real Rust Cargo.toml files."""

    def test_parse_cargo_toml(self):
        """Test parsing Cargo.toml fixture."""
        cargo_path = FIXTURES_DIR / "rust" / "Cargo.toml"
        assert cargo_path.exists(), "Cargo.toml fixture not found"

        # Simple TOML parsing (no external dependency)
        with open(cargo_path) as f:
            content = f.read()

        # Verify expected packages
        assert "tokio" in content

    def test_parse_lock_toml(self):
        """Test parsing Cargo.lock fixture."""
        lock_path = FIXTURES_DIR / "rust" / "Cargo.lock"
        assert lock_path.exists(), "Cargo.lock fixture not found"

        # Simple TOML parsing (no external dependency)
        with open(lock_path) as f:
            content = f.read()

        # Verify expected packages
        assert "tokio" in content

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_rust_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking Rust packages from Cargo.toml fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_packages = ["tokio"]

        for pkg in test_packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg}",
                    total_score=85,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=85,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"rust:{pkg}", "--insecure"])
                assert result.exit_code == 0


class TestJavaFixtures:
    """Test with real Java pom.xml files."""

    def test_parse_pom_xml(self):
        """Test parsing pom.xml fixture."""
        pom_path = FIXTURES_DIR / "java" / "maven" / "pom.xml"
        assert pom_path.exists(), "pom.xml fixture not found"

        with open(pom_path) as f:
            content = f.read()

        # Verify expected packages
        assert "spring-boot-starter-web" in content
        assert "guava" in content
        assert "commons-lang3" in content

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_java_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking Java packages from pom.xml fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_packages = [
            "org.springframework.boot:spring-boot-starter-web",
            "com.google.guava:guava",
            "org.apache.commons:commons-lang3",
        ]

        for pkg in test_packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg.split(':')[-1]}",
                    total_score=82,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=82,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"maven:{pkg}", "--insecure"])
                assert result.exit_code == 0


class TestPHPFixtures:
    """Test with real PHP composer.json files."""

    def test_parse_composer_json(self):
        """Test parsing composer.json fixture."""
        composer_path = FIXTURES_DIR / "php" / "composer.json"
        assert composer_path.exists(), "composer.json fixture not found"

        with open(composer_path) as f:
            data = json.load(f)

        # Verify expected packages
        assert "laravel/framework" in data["require"]
        assert "guzzlehttp/guzzle" in data["require"]
        assert "monolog/monolog" in data["require"]

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_php_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking PHP packages from composer.json fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        composer_path = FIXTURES_DIR / "php" / "composer.json"
        with open(composer_path) as f:
            data = json.load(f)

        packages = list(data["require"].keys())[1:4]  # Skip php version

        for pkg in packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg.replace('/', '-')}",
                    total_score=78,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=78,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"php:{pkg}", "--insecure"])
                assert result.exit_code == 0


class TestRubyFixtures:
    """Test with real Ruby Gemfile files."""

    def test_parse_gemfile(self):
        """Test parsing Gemfile fixture."""
        gemfile_path = FIXTURES_DIR / "ruby" / "Gemfile"
        assert gemfile_path.exists(), "Gemfile fixture not found"

        with open(gemfile_path) as f:
            content = f.read()

        # Verify expected gems
        assert "rails" in content
        assert "puma" in content
        assert "sidekiq" in content

    def test_parse_gemfile_lock(self):
        """Test parsing Gemfile.lock fixture."""
        lock_path = FIXTURES_DIR / "ruby" / "Gemfile.lock"
        assert lock_path.exists(), "Gemfile.lock fixture not found"

        with open(lock_path) as f:
            content = f.read()

        # Verify expected gems
        assert "rails" in content
        assert "puma" in content
        assert "sidekiq" in content

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_ruby_gems_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking Ruby gems from Gemfile fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_gems = ["rails", "puma", "sidekiq", "devise"]

        for gem in test_gems:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{gem}",
                    total_score=83,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=83,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"ruby:{gem}", "--insecure"])
                assert result.exit_code == 0


class TestCSharpFixtures:
    """Test with real C# packages.config files."""

    def test_parse_packages_config(self):
        """Test parsing packages.config fixture."""
        packages_path = FIXTURES_DIR / "csharp" / "packages.config"
        assert packages_path.exists(), "packages.config fixture not found"

        with open(packages_path) as f:
            content = f.read()

        # Verify expected packages
        assert "Newtonsoft.Json" in content
        assert "EntityFramework" in content
        assert "Serilog" in content

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_csharp_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking C# packages from packages.config fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_packages = ["Newtonsoft.Json", "EntityFramework", "Serilog", "Dapper"]

        for pkg in test_packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg}",
                    total_score=87,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=87,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"nuget:{pkg}", "--insecure"])
                assert result.exit_code == 0


class TestGoFixtures:
    """Test with real Go go.mod files."""

    def test_parse_go_mod(self):
        """Test parsing go.mod fixture."""
        gomod_path = FIXTURES_DIR / "go" / "go.mod"
        assert gomod_path.exists(), "go.mod fixture not found"

        with open(gomod_path) as f:
            content = f.read()

        # Verify expected modules
        assert "github.com/gin-gonic/gin" in content

    def test_parse_go_sum(self):
        """Test parsing go.sum fixture."""
        go_sum_path = FIXTURES_DIR / "go" / "go.sum"
        assert go_sum_path.exists(), "go.sum fixture not found"

        with open(go_sum_path) as f:
            content = f.read()

        # Verify expected modules
        assert "github.com/gin-gonic/gin" in content

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_go_modules_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking Go modules from go.mod fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_modules = [
            "github.com/gin-gonic/gin",
            "gorm.io/gorm",
            "github.com/spf13/cobra",
        ]

        for module in test_modules:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://{module}",
                    total_score=84,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=84,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"go:{module}", "--insecure"])
                assert result.exit_code == 0


class TestDartFixtures:
    """Test with real Dart pubspec.yaml files."""

    def test_parse_pubspec_yaml(self):
        """Test parsing pubspec.yaml fixture."""
        pubspec_path = FIXTURES_DIR / "dart" / "pubspec.yaml"
        assert pubspec_path.exists(), "pubspec.yaml fixture not found"

        with open(pubspec_path) as f:
            content = f.read()

        # Verify expected packages
        assert "http:" in content
        assert "path:" in content
        assert "lints:" in content

    def test_parse_pubspec_lock(self):
        """Test parsing pubspec.lock fixture."""
        lock_path = FIXTURES_DIR / "dart" / "pubspec.lock"
        assert lock_path.exists(), "pubspec.lock fixture not found"

        with open(lock_path) as f:
            content = f.read()

        # Verify expected packages
        assert "http:" in content
        assert "collection:" in content
        assert "lints:" in content

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_dart_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking Dart packages from pubspec.yaml fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_packages = ["http", "path", "lints", "test"]

        for pkg in test_packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg}",
                    total_score=81,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=81,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"dart:{pkg}", "--insecure"])
                assert result.exit_code == 0


class TestElixirFixtures:
    """Test with real Elixir mix.exs files."""

    def test_parse_mix_exs(self):
        """Test parsing mix.exs fixture."""
        mix_path = FIXTURES_DIR / "elixir" / "mix.exs"
        assert mix_path.exists(), "mix.exs fixture not found"

        with open(mix_path) as f:
            content = f.read()

        # Verify expected packages
        assert "phoenix" in content
        assert "ecto_sql" in content

    def test_parse_mix_lock(self):
        """Test parsing mix.lock fixture."""
        lock_path = FIXTURES_DIR / "elixir" / "mix.lock"
        assert lock_path.exists(), "mix.lock fixture not found"

        with open(lock_path) as f:
            content = f.read()

        # Verify expected packages
        assert "phoenix" in content
        assert "ecto_sql" in content

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_elixir_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking Elixir packages from mix.exs fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_packages = ["phoenix", "ecto_sql"]

        for pkg in test_packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg}",
                    total_score=79,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=79,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"elixir:{pkg}", "--insecure"])
                assert result.exit_code == 0


class TestHaskellFixtures:
    """Test with real Haskell cabal/stack files."""

    def test_parse_cabal_project(self):
        """Test parsing cabal.project fixture."""
        cabal_path = FIXTURES_DIR / "haskell" / "cabal" / "cabal.project"
        assert cabal_path.exists(), "cabal.project fixture not found"

        with open(cabal_path) as f:
            content = f.read()

        # Verify expected packages
        assert "text" in content
        assert "bytestring" in content

    def test_parse_stack_yaml(self):
        """Test parsing stack.yaml fixture."""
        stack_path = FIXTURES_DIR / "haskell" / "stack" / "stack.yaml"
        assert stack_path.exists(), "stack.yaml fixture not found"

        with open(stack_path) as f:
            content = f.read()

        # Verify expected packages
        assert "text-1.2.5.0" in content

    def test_parse_cabal_project_freeze(self):
        """Test parsing cabal.project.freeze fixture."""
        freeze_path = FIXTURES_DIR / "haskell" / "cabal" / "cabal.project.freeze"
        assert freeze_path.exists(), "cabal.project.freeze fixture not found"

        with open(freeze_path) as f:
            content = f.read()

        # Verify expected packages
        assert "text" in content
        assert "bytestring" in content

    def test_parse_stack_yaml_lock(self):
        """Test parsing stack.yaml.lock fixture."""
        lock_path = FIXTURES_DIR / "haskell" / "stack" / "stack.yaml.lock"
        assert lock_path.exists(), "stack.yaml.lock fixture not found"

        with open(lock_path) as f:
            content = f.read()

        # Verify expected packages
        assert "text-1.2.5.0" in content

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_haskell_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking Haskell packages from cabal/stack fixtures."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_packages = ["text", "bytestring"]

        for pkg in test_packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg}",
                    total_score=76,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=76,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"haskell:{pkg}", "--insecure"])
                assert result.exit_code == 0


class TestKotlinFixtures:
    """Test with real Kotlin Gradle build files."""

    def test_parse_build_gradle_kts(self):
        """Test parsing build.gradle.kts fixture."""
        gradle_path = FIXTURES_DIR / "kotlin" / "gradle" / "build.gradle.kts"
        assert gradle_path.exists(), "build.gradle.kts fixture not found"

        with open(gradle_path) as f:
            content = f.read()

        # Verify expected packages
        assert "kotlin-stdlib" in content
        assert "ktor-server-core" in content
        assert "junit-jupiter" in content

    def test_parse_maven_pom_xml(self):
        """Test parsing pom.xml fixture for Kotlin Maven project."""
        pom_path = FIXTURES_DIR / "kotlin" / "maven" / "pom.xml"
        assert pom_path.exists(), "pom.xml fixture not found"

        with open(pom_path) as f:
            content = f.read()

        # Verify expected packages
        assert "kotlin-stdlib" in content
        assert "ktor-server-core" in content
        assert "junit-jupiter" in content

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_kotlin_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking Kotlin packages from build.gradle.kts fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_packages = [
            "org.jetbrains.kotlin:kotlin-stdlib",
            "io.ktor:ktor-server-core",
            "org.junit.jupiter:junit-jupiter",
        ]

        for pkg in test_packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg.split(':')[-1]}",
                    total_score=77,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=77,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"kotlin:{pkg}", "--insecure"])
                assert result.exit_code == 0


class TestPerlFixtures:
    """Test with real Perl cpanfile files."""

    def test_parse_cpanfile(self):
        """Test parsing cpanfile fixture."""
        cpan_path = FIXTURES_DIR / "perl" / "cpanfile"
        assert cpan_path.exists(), "cpanfile fixture not found"

        with open(cpan_path) as f:
            content = f.read()

        # Verify expected packages
        assert "Mojolicious" in content
        assert "DBI" in content

    def test_parse_cpanfile_snapshot(self):
        """Test parsing cpanfile.snapshot fixture."""
        snapshot_path = FIXTURES_DIR / "perl" / "cpanfile.snapshot"
        assert snapshot_path.exists(), "cpanfile.snapshot fixture not found"

        with open(snapshot_path) as f:
            content = f.read()

        # Verify expected packages
        assert "Mojolicious" in content
        assert "Test-Simple" in content

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_perl_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking Perl packages from cpanfile fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_packages = ["Mojolicious", "DBI"]

        for pkg in test_packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg}",
                    total_score=74,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=74,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"perl:{pkg}", "--insecure"])
                assert result.exit_code == 0


class TestRFixtures:
    """Test with real R DESCRIPTION files."""

    def test_parse_description(self):
        """Test parsing DESCRIPTION fixture."""
        description_path = FIXTURES_DIR / "r" / "DESCRIPTION"
        assert description_path.exists(), "DESCRIPTION fixture not found"

        with open(description_path) as f:
            content = f.read()

        # Verify expected packages
        assert "dplyr" in content
        assert "ggplot2" in content
        assert "testthat" in content

    def test_parse_renv_lock(self):
        """Test parsing renv.lock fixture."""
        lock_path = FIXTURES_DIR / "r" / "renv.lock"
        assert lock_path.exists(), "renv.lock fixture not found"

        with open(lock_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify expected packages
        assert "Packages" in data
        assert "dplyr" in data["Packages"]
        assert "ggplot2" in data["Packages"]

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_r_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking R packages from DESCRIPTION fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_packages = ["dplyr", "ggplot2", "testthat"]

        for pkg in test_packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/example/{pkg}",
                    total_score=73,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=73,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"r:{pkg}", "--insecure"])
                assert result.exit_code == 0


class TestSwiftFixtures:
    """Test with real Swift Package Manager files."""

    def test_parse_package_swift(self):
        """Test parsing Package.swift fixture."""
        package_path = FIXTURES_DIR / "swift" / "Package.swift"
        assert package_path.exists(), "Package.swift fixture not found"

        with open(package_path) as f:
            content = f.read()

        # Verify expected packages
        assert "swift-nio" in content
        assert "Alamofire" in content

    def test_parse_package_resolved(self):
        """Test parsing Package.resolved fixture."""
        resolved_path = FIXTURES_DIR / "swift" / "Package.resolved"
        assert resolved_path.exists(), "Package.resolved fixture not found"

        with open(resolved_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        pins = data.get("object", {}).get("pins", [])
        locations = [pin.get("location") for pin in pins if isinstance(pin, dict)]

        assert any(
            isinstance(location, str) and "swift-nio" in location
            for location in locations
        )
        assert any(
            isinstance(location, str) and "Alamofire" in location
            for location in locations
        )

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_check_swift_packages_from_fixture(self, mock_excluded, mock_load_cache):
        """Test checking Swift packages from Package.swift fixture."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        test_packages = ["apple/swift-nio", "Alamofire/Alamofire"]

        for pkg in test_packages:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url=f"https://github.com/{pkg}",
                    total_score=72,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=72,
                            max_score=100,
                            message="Package analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", f"swift:{pkg}", "--insecure"])
                assert result.exit_code == 0


class TestMultiLanguageFixtures:
    """Test cross-language fixture integration."""

    @patch("oss_sustain_guard.cache.load_cache")
    @patch("oss_sustain_guard.commands.check.is_package_excluded")
    def test_mixed_language_dependencies(self, mock_excluded, mock_load_cache):
        """Test analyzing packages from multiple language ecosystems."""
        mock_excluded.return_value = False
        mock_load_cache.return_value = None

        # Representative package from each ecosystem
        test_cases = [
            ("npm:react", "JavaScript"),
            ("python:Django", "Python"),
            ("rust:tokio", "Rust"),
            ("maven:com.google.guava:guava", "Java"),
            ("kotlin:org.jetbrains.kotlin:kotlin-stdlib", "Kotlin"),
            ("php:laravel/framework", "PHP"),
            ("ruby:rails", "Ruby"),
            ("nuget:Newtonsoft.Json", "C#"),
            ("go:github.com/gin-gonic/gin", "Go"),
            ("dart:http", "Dart"),
            ("elixir:phoenix", "Elixir"),
            ("haskell:text", "Haskell"),
            ("perl:Mojolicious", "Perl"),
            ("r:dplyr", "R"),
            ("swift:apple/swift-nio", "Swift"),
        ]

        for package_spec, lang in test_cases:
            with patch(
                "oss_sustain_guard.commands.check.analyze_package"
            ) as mock_analyze:
                mock_analyze.return_value = AnalysisResult(
                    repo_url="https://github.com/example/repo",
                    total_score=80,
                    metrics=[
                        Metric(
                            name="Test Metric",
                            score=80,
                            max_score=100,
                            message=f"Package from {lang} analyzed successfully",
                            risk="Low",
                        )
                    ],
                )
                result = runner.invoke(app, ["check", package_spec, "--insecure"])
                assert result.exit_code == 0, f"Failed for {lang}: {package_spec}"
