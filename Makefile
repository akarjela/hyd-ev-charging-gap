.PHONY: setup fetch build test serve up clean lint

setup:
	uv sync

fetch:
	@test -n "$$OCM_API_KEY" || (echo "OCM_API_KEY is not set (free key: https://openchargemap.org/site/profile/applications)"; exit 1)
	uv run hydgap fetch

build:
	uv run hydgap build

test:
	uv run pytest -q

lint:
	uv run ruff check src tests

serve:
	uv run hydgap serve

up: setup build serve

clean:
	rm -rf data/processed
