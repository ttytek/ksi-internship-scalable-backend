.PHONY: up down build test lint install

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
