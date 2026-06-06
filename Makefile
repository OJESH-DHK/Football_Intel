.PHONY: help up down build logs shell migrate makemigrations createsuperuser test lint \
        prod-up prod-down prod-build prod-logs prod-shell prod-migrate

PROD = docker compose -f docker-compose.yml -f docker-compose.prod.yml

# ── Dev ───────────────────────────────────────────────────────────────────────

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

up: ## Start dev stack
	docker compose up

down: ## Stop dev stack
	docker compose down

build: ## Rebuild dev images
	docker compose build --no-cache

logs: ## Tail dev logs
	docker compose logs -f

shell: ## Django shell (dev)
	docker compose run --rm web python manage.py shell

migrate: ## Run migrations (dev)
	docker compose run --rm web python manage.py migrate

makemigrations: ## Make migrations (dev)
	docker compose run --rm web python manage.py makemigrations

createsuperuser: ## Create superuser (dev)
	docker compose run --rm web python manage.py createsuperuser

test: ## Run tests
	docker compose run --rm web pytest

lint: ## Run ruff linter
	docker compose run --rm web ruff check .

# ── Prod (run on VPS) ─────────────────────────────────────────────────────────

prod-up: ## Start prod stack
	$(PROD) up -d

prod-down: ## Stop prod stack
	$(PROD) down

prod-build: ## Rebuild prod images
	$(PROD) build --no-cache

prod-logs: ## Tail prod logs
	$(PROD) logs -f

prod-shell: ## Django shell (prod)
	$(PROD) run --rm web python manage.py shell

prod-migrate: ## Run migrations (prod)
	$(PROD) run --rm web python manage.py migrate --noinput

prod-collectstatic: ## Collect static files (prod)
	$(PROD) run --rm web python manage.py collectstatic --noinput
