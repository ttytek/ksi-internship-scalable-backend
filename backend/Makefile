.PHONY: test lint install seed up down

COMPOSE = docker compose -f ../docker-compose.yml --project-directory ..

install:
	pip install -e ".[dev]"

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

test:
	pytest -q

lint:
	ruff check src tests

# Needs S3_* for problems with private/generated tests; otherwise ERR … S3 is not configured.
seed:
	python -m ksi.scripts.seed_dataset --dir ../dataset/problems
