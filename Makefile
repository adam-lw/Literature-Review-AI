.DEFAULT_GOAL := help

FRONTEND_URL := http://localhost:5173/
API_HEALTH_URL := http://localhost:8000/api/health

.PHONY: help up start down stop build restart-api restart-frontend logs ps clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up: ## Start postgres + backend api + frontend dev server, then print the UI address
	@docker compose up -d --build
	@echo "Waiting for the API to come up..."
	@i=0; \
	while ! curl -sf $(API_HEALTH_URL) >/dev/null 2>&1; do \
		i=$$((i+1)); \
		if [ $$i -ge 90 ]; then \
			echo "API did not become healthy after 7.5 minutes — check: make logs"; \
			exit 1; \
		fi; \
		sleep 5; \
	done
	@echo ""
	@echo "Literature AI is running:"
	@echo "  UI  ->  $(FRONTEND_URL)"
	@echo "  API ->  http://localhost:8000/api"
	@echo ""

start: up ## Alias for `make up`

down: ## Stop all services (Postgres data in ./data/postgres is untouched)
	docker compose down

stop: down ## Alias for `make down`

build: ## Rebuild the api/frontend images without starting them
	docker compose build

restart-api: ## Restart the backend to pick up code changes
	docker compose restart api

restart-frontend: ## Restart the frontend dev server
	docker compose restart frontend

logs: ## Tail logs from all services
	docker compose logs -f

ps: ## Show status of running services
	docker compose ps

clean: ## Stop services and remove the venv/node_modules caches (Postgres data is untouched)
	docker compose down -v
