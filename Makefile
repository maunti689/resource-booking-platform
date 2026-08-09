.PHONY: install check migrate migrations-check seed test test-postgres up down logs

install:
	python -m pip install -e ".[dev]"

check:
	ruff format --check .
	ruff check .
	python manage.py check

migrate:
	python manage.py migrate

migrations-check:
	python manage.py makemigrations --check --dry-run

seed:
	python scripts/seed_demo.py

test:
	pytest --cov --cov-report=term-missing

test-postgres:
	TEST_DATABASE_URL=postgresql://booking:local-only-booking@localhost:5432/booking pytest -m postgresql

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api worker beat
