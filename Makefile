.PHONY: install dev mix analyze test lint format check clean

install:
	uv sync

dev:
	uv sync --dev

mix:
	uv run ai-mixer mix "$(INPUT)" --setup "$(SETUP)"

analyze:
	uv run ai-mixer analyze "$(INPUT)" --setup "$(SETUP)"

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

check:
	uv run ruff check .
	uv run ruff format --check .

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
