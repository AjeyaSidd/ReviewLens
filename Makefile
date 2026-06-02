.DEFAULT_GOAL := help

# ── Paths ──────────────────────────────────────────────
BACKEND  := backend
FRONTEND := frontend

# ── Help ───────────────────────────────────────────────
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Install ────────────────────────────────────────────
.PHONY: install install-backend install-frontend

install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install backend (Python) dependencies
	cd $(BACKEND) && pip install -r requirements.txt

install-frontend: ## Install frontend (Node) dependencies
	cd $(FRONTEND) && npm install

# ── Build ──────────────────────────────────────────────
.PHONY: build
build: ## Build frontend production bundle
	cd $(FRONTEND) && npm run build

# ── Test ───────────────────────────────────────────────
.PHONY: test test-backend test-frontend

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend pytest
	cd $(BACKEND) && python -m pytest tests/ -v

test-frontend: ## Run frontend tests
	cd $(FRONTEND) && npm test

# ── Lint ───────────────────────────────────────────────
.PHONY: lint
lint: ## Lint backend (ruff) + frontend (eslint)
	cd $(BACKEND) && ruff check app/ tests/
	cd $(FRONTEND) && npx eslint . --ext .ts,.tsx

# ── Run ────────────────────────────────────────────────
.PHONY: run-api run-web

run-api: ## Start FastAPI dev server
	cd $(BACKEND) && uvicorn app.main:app --reload --port 8000

run-web: ## Start Next.js dev server
	cd $(FRONTEND) && npm run dev

# ── Docker ─────────────────────────────────────────────
.PHONY: docker-build
docker-build: ## Build backend Docker image
	docker build -t app-review-api $(BACKEND)

# ── Clean ──────────────────────────────────────────────
.PHONY: clean
clean: ## Remove caches and build artifacts
	find $(BACKEND) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.mypy_cache $(BACKEND)/.ruff_cache
	rm -rf $(FRONTEND)/.next $(FRONTEND)/out $(FRONTEND)/node_modules/.cache
