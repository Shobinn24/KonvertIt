.PHONY: help install test lint format security docker-up docker-down docker-build docker-prod-up docker-prod-down docker-prod-build migrate run prelaunch-check clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	pip install -r requirements.txt
	pip install -e ".[dev]"
	playwright install chromium

test: ## Run all tests with coverage
	pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

test-unit: ## Run unit tests only
	pytest tests/unit/ -v --cov=app --cov-report=term-missing

lint: ## Run linter checks
	ruff check app/ tests/
	ruff format --check app/ tests/

format: ## Auto-format code
	ruff format app/ tests/
	ruff check --fix app/ tests/

security: ## Run security scans (bandit + safety)
	bandit -r app/ -x app/db/migrations
	safety check -r requirements.txt --output text || true

docker-up: ## Start all services with Docker Compose
	docker compose -f docker/docker-compose.yml up -d

docker-down: ## Stop all Docker services
	docker compose -f docker/docker-compose.yml down

docker-build: ## Build Docker images (dev)
	docker compose -f docker/docker-compose.yml build

docker-prod-up: ## Start production services
	docker compose -f docker/docker-compose.prod.yml up -d

docker-prod-down: ## Stop production services
	docker compose -f docker/docker-compose.prod.yml down

docker-prod-build: ## Build production Docker image
	docker compose -f docker/docker-compose.prod.yml build

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create msg="description")
	alembic revision --autogenerate -m "$(msg)"

run: ## Run the application locally
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

prelaunch-check: ## Run pre-launch checklist
	python scripts/prelaunch_check.py

clean: ## Clean up cache and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage dist/ build/ *.egg-info/
