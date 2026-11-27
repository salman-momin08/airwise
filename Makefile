.PHONY: help setup up down logs ps lint typecheck test migrate seed clean

help: ## Display available development commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

setup: ## Copy unified root environment template if missing
	@test -f .env || cp .env.example .env
	@test -f frontend/.env.local || grep '^NEXT_PUBLIC_' .env.example > frontend/.env.local
	@echo "Environment files initialized from root .env.example (.env and frontend/.env.local)."

up: ## Build and start full local Docker Compose stack
	docker compose up --build -d

down: ## Stop local Docker Compose stack
	docker compose down

logs: ## Follow logs across all services
	docker compose logs -f

ps: ## Show status of local containers
	docker compose ps

migrate: ## Run Alembic database migrations inside backend container
	docker compose exec backend alembic upgrade head

seed: ## Seed reference AQI standards, emission factors, and labeled dev fixtures
	docker compose exec backend python -m scripts.seed_reference_data

lint: ## Run Ruff lint & format check (backend) and ESLint (frontend)
	cd backend && ruff check app scripts tests alembic ../api && ruff format --check app scripts tests alembic ../api
	cd frontend && npm run lint

typecheck: ## Run strict MyPy (backend) and TypeScript tsc --noEmit (frontend)
	cd backend && mypy app scripts tests ../api
	cd frontend && npm run typecheck

test: ## Run Pytest (backend) and Vitest (frontend)
	cd backend && pytest
	cd frontend && npm run test

clean: ## Stop containers and remove volumes (DESTRUCTIVE to local dev DB)
	docker compose down -v --remove-orphans
