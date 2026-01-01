.PHONY: lint doc-serve test test-check test-manifests

lint:
	uv run prek run --all-files

doc-serve:
	uv run mkdocs serve --livereload

test:
	uv run pytest tests/ -v --cov=oss_sustain_guard --cov-report=xml --cov-report=term --cov-report=html -m "not slow" -vvv

test-check:
	uv run os4g check requests -v

test-self-check:
	uv run os4g check -r ./ --insecure --no-cache

test-manifests:
	uv run os4g check -r ./tests/fixtures/ --insecure --no-cache