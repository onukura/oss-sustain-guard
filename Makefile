.PHONY: lint doc-serve test test-check test-manifests

lint:
	uv run prek run --all-files

doc-serve:
	uv run mkdocs serve --livereload

doc-build:
	uv run mkdocs build --strict

test:
	uv run pytest tests/ -v --cov=oss_sustain_guard --cov-report=xml --cov-report=term --cov-report=html -m "not slow" -vvv

test-check:
	uv run os4g check requests -v

test-self-check:
	uv run os4g check -r ./ --insecure --include-lock

test-all-fixtures:
	uv run os4g check -r ./tests/fixtures/ --insecure --recursive --include-lock

test-csharp:
	uv run os4g check -r ./tests/fixtures/csharp --insecure --include-lock --recursive

test-dart:
	uv run os4g check -r ./tests/fixtures/dart --insecure --include-lock --recursive

test-elixir:
	uv run os4g check -r ./tests/fixtures/elixir --insecure --include-lock --recursive

test-go:
	uv run os4g check -r ./tests/fixtures/go --insecure --include-lock --recursive

test-haskell:
	uv run os4g check -r ./tests/fixtures/haskell --insecure --include-lock --recursive

test-java:
	uv run os4g check -r ./tests/fixtures/java --insecure --include-lock --recursive

test-javascript:
	uv run os4g check -r ./tests/fixtures/javascript --insecure --include-lock --recursive

test-kotlin:
	uv run os4g check -r ./tests/fixtures/kotlin --insecure --include-lock --recursive

test-perl:
	uv run os4g check -r ./tests/fixtures/perl --insecure --include-lock --recursive

test-php:
	uv run os4g check -r ./tests/fixtures/php --insecure --include-lock --recursive

test-python:
	uv run os4g check -r ./tests/fixtures/python --insecure --include-lock --recursive

test-r:
	uv run os4g check -r ./tests/fixtures/r --insecure --include-lock --recursive

test-ruby:
	uv run os4g check -r ./tests/fixtures/ruby --insecure --include-lock --recursive

test-ruby:
	uv run os4g check -r ./tests/fixtures/ruby --insecure --include-lock --recursive

test-rust:
	uv run os4g check -r ./tests/fixtures/rust --insecure --include-lock --recursive

test-scala:
	uv run os4g check -r ./tests/fixtures/scala --insecure --include-lock --recursive

test-swift:
	uv run os4g check -r ./tests/fixtures/swift --insecure --include-lock --recursive

test-all-commands:
	./scripts/test_all_commands.sh