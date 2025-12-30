.PHONY: lint doc-serve test test-check test-manifests

lint:
	uv run prek run --all-files

doc-serve:
	uv run mkdocs serve --livereload

test:
	uv run pytest tests/ -v --cov=oss_sustain_guard --cov-report=xml --cov-report=term --cov-report=html

test-check:
	uv run os4g check requests -v

test-manifests:
	uv run os4g check -r ./tests/fixtures/ --insecure --no-cache