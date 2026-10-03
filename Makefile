.PHONY: install lint format test run docker-up docker-down

PYTHON ?= python3
VENV ?= .venv
BIN = $(VENV)/bin

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -r requirements-dev.txt

lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

test:
	$(BIN)/pytest

run:
	$(BIN)/python -m bot

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
