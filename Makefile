.PHONY: lint doc-serve test

lint:
	uv run prek run --all-files

doc-serve:
	uv run mkdocs serve --livereload

test:
	uv run pytest tests/ -v --cov=oss_sustain_guard --cov-report=xml --cov-report=term --cov-report=html

test-build-db:
	uv run python builder/build_db.py --ecosystems python --limit 5 --upload-to-cloudflare