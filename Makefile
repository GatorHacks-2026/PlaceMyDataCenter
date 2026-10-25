.DEFAULT_GOAL := help

PYTHON ?= python3
VENV_PYTHON := backend/.venv/bin/python

.PHONY: help setup dev backend frontend check test build

help:
	@echo "Data Center Lens commands (run from the repository root):"
	@echo "  make setup     Install frontend and backend dependencies"
	@echo "  make dev       Start the API and frontend together (Ctrl+C stops both)"
	@echo "  make backend   Start only the API on http://127.0.0.1:8000"
	@echo "  make frontend  Start only the website on http://127.0.0.1:5173"
	@echo "  make check     Run frontend tests, build, and backend tests"
	@echo "  make build     Build the frontend for production"

setup:
	$(PYTHON) -m venv backend/.venv
	cd backend && .venv/bin/python -m pip install -r requirements-dev.txt
	npm ci

dev:
	@set -e; \
	PYTHONPATH=backend $(VENV_PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 & \
	api_pid=$$!; \
	trap 'kill $$api_pid 2>/dev/null || true' EXIT INT TERM; \
	npm run dev -- --host 127.0.0.1

backend:
	PYTHONPATH=backend $(VENV_PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	npm run dev -- --host 127.0.0.1

test:
	npm test
	PYTHONPATH=backend $(VENV_PYTHON) -m pytest scripts/tests backend/tests -q

build:
	npm run build

check: test build
