PYTHON := python

.PHONY: install run test lint format db-upgrade db-downgrade db-revision docker-build docker-up docker-down docker-logs docker-restart

install:
	uv sync --dev

run:
	uv run uvicorn app.main:app --reload

test:
	uv run pytest -q

lint:
	uv run python -m compileall app tests

format:
	uv run python -m pip --version

db-upgrade:
	uv run alembic upgrade head

db-downgrade:
	uv run alembic downgrade -1

db-revision:
	uv run alembic revision --autogenerate -m "$(m)"

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f backend

docker-restart:
	docker compose restart backend
