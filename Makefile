.PHONY: help setup test clean run lint frontend backend

help:
	@echo "Phoenix Guardian — Makefile Commands"
	@echo ""
	@echo "  make setup     - Run one-command setup"
	@echo "  make backend   - Start backend API server"
	@echo "  make frontend  - Start frontend dev server"
	@echo "  make test      - Run test suite"
	@echo "  make lint      - Run code quality checks"
	@echo "  make clean     - Remove generated files"
	@echo "  make migrate   - Run database migrations"
	@echo "  make validate  - Validate installation"
	@echo ""

setup:
	@chmod +x setup.sh && ./setup.sh

backend:
	@source .venv/bin/activate && python -m uvicorn phoenix_guardian.api.main:app --reload --port 8000

frontend:
	@cd phoenix-ui && npm start

test:
	@source .venv/bin/activate && pytest tests/ -v

lint:
	@source .venv/bin/activate && black phoenix_guardian/ tests/ --check
	@source .venv/bin/activate && flake8 phoenix_guardian/ --max-line-length=100 --ignore=E501,W503

migrate:
	@source .venv/bin/activate && python scripts/migrate.py

validate:
	@source .venv/bin/activate && python scripts/validate_installation.py

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache htmlcov .coverage 2>/dev/null || true
	@echo "Cleaned up generated files"
