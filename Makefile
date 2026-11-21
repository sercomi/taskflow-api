.PHONY: up down logs test lint format typecheck check

up:
	docker compose \
  -f compose.yml \
  -f compose.dev.yml \
  up -d --build

down:
	docker compose \
  -f compose.yml \
  -f compose.dev.yml \
	down

logs:
	docker compose \
  -f compose.yml \
  -f compose.dev.yml \
	logs -f api

test:
	pytest -v

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy app/

check: lint
	uv run ruff format --check .
	uv run mypy app/
	uv run pytest -v

