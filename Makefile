.PHONY: install run test lint format migrate seed close worker beat up down

install:
	pip install -r requirements-dev.txt

run:  ## Daphne-backed dev server (HTTP + WebSockets)
	python manage.py runserver

migrate:
	python manage.py migrate

seed:
	python manage.py seed_demo

test:
	pytest --cov --cov-report=term-missing:skip-covered

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

worker:
	celery -A config worker --loglevel=info

beat:
	celery -A config beat --loglevel=info

up:
	docker compose up --build

down:
	docker compose down

close:
	python manage.py close_auctions
