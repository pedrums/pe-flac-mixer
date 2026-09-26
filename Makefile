SETUP ?= probe_Matscher
RECORDS ?= /mnt/e/data2/HiDrive/Schlappseil/Musik/Proben/2026
SOURCE ?= Probe_2026-09-15

.DEFAULT_GOAL := help

.PHONY: help install dev mix bulk cut analyze create-setup test lint format check clean doc doc-serve build

help: # Show available targets and descriptions
	@awk 'BEGIN {FS = ":.*?# "} /^[a-zA-Z_-]+:.*?# / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: # Install dependencies using uv
	uv sync

dev: # Install development dependencies
	uv sync --dev

mix: # Render rough mix (args: INPUT=<path> [SETUP=<name>] [CUT=<seconds>])
	uv run pe-flac-mixer mix "$(INPUT)" --setup "$(SETUP)" $(if $(CUT),--cut "$(CUT)",)

bulk: # Render bulk mix for all subdirectories (args: RECORDS=<path> or RECORD=<path>, SOURCE=<name> [SETUP=<name>] [OUTPUT=<path>] [CUT=<seconds>])
	uv run pe-flac-mixer mix "$(or $(RECORDS),$(RECORD))/$(SOURCE)" --bulk --setup "$(SETUP)" $(if $(OUTPUT),--output "$(OUTPUT)",) $(if $(CUT),--cut "$(CUT)",)

cut: # Cut X seconds from the beginning of an MP3 file (args: INPUT=<path> SEC=<seconds>)
	uv run pe-flac-mixer cut "$(INPUT)" --sec $(SEC)

analyze: # Analyze audio tracks (args: INPUT=<path> [SETUP=<name>])
	uv run pe-flac-mixer analyze "$(INPUT)" --setup "$(SETUP)"

create-setup: # Generate setup YAML by guessing tracks from directory (args: SOURCE=<path> [NAME=<name>])
	uv run pe-flac-mixer create-setup --source "$(SOURCE)" $(if $(NAME),--name "$(NAME)",)

test: # Run tests via pytest
	uv run python -m pytest

lint: # Run ruff linter
	uv run ruff check .

format: # Format code with ruff
	uv run ruff format .

check: # Check linting and formatting
	uv run ruff check .
	uv run ruff format --check .

clean: # Remove cache, build artifacts, and __pycache__
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info site
	find . -type d -name "__pycache__" -exec rm -rf {} +

doc: # Build documentation with mkdocs
	uv run mkdocs build

doc-serve: # Serve documentation locally with mkdocs
	uv run mkdocs serve

build: # Build python package distributions (wheel & sdist) using hatchling / uv
	uv build
