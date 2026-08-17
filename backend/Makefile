.PHONY: up down build test lint install seed

install:
	pip install -e ".[dev]"

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

test:
	pytest -q

lint:
	ruff check src tests

# Needs S3_* for problems with private/generated tests; otherwise ERR … S3 is not configured.
seed:
	python -m ksi.scripts.seed_dataset --dir ../dataset/problems
