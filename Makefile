# PRD/Figma test-case generator
#
# The previous Makefile targeted src/presentation/api/main.py and a set of npm
# scripts, none of which exist here. Every one of those targets failed, and the
# deploy/docs/monitor targets printed a status line and exited 0 without doing
# anything. This one matches the layout that is actually in the repository.
.PHONY: help install install-dev setup-env serve cli test test-cov lint format \
        type-check verify frontend-install frontend-dev frontend-build \
        frontend-lint index-rag clean

.DEFAULT_GOAL := help

VENV        ?= venv
PY          := $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
NPM         := npm
FRONTEND_DIR := frontend
HOST        ?= 0.0.0.0
PORT        ?= 8000

help: ## Show this help
	@echo "PRD/Figma test-case generator"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36mmake %-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables: VENV HOST PORT"

install: ## Create a venv and install runtime dependencies
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

install-dev: install ## Install development tools as well
	$(VENV)/bin/pip install ruff mypy pytest pytest-cov

setup-env: ## Create .env from the example, if it is not already there
	@if [ -f .env ]; then \
		echo ".env already exists; leaving it alone."; \
	elif [ -f .env.example ]; then \
		cp .env.example .env && echo "Created .env from .env.example — fill it in."; \
	else \
		echo "No .env.example in this repository." >&2; exit 1; \
	fi
	@if [ -f $(FRONTEND_DIR)/.env.example ]; then \
		cp -n $(FRONTEND_DIR)/.env.example $(FRONTEND_DIR)/.env && \
		echo "Created $(FRONTEND_DIR)/.env"; \
	fi

serve: ## Run the API with reload
	$(PY) -m uvicorn app:app --reload --host $(HOST) --port $(PORT)

cli: ## Show the CLI's own help
	$(PY) cli.py --help

test: ## Run the test suite
	$(PY) -m pytest

test-cov: ## Run the test suite with coverage
	$(PY) -m pytest --cov=framework --cov=routes --cov-report=term-missing

lint: ## Lint the Python sources
	$(PY) -m ruff check framework/ routes/ rag/ scripts/ tests/ *.py

format: ## Format the Python sources
	$(PY) -m ruff format framework/ routes/ rag/ scripts/ tests/ *.py

type-check: ## Type-check the framework package
	$(PY) -m mypy framework/

verify: lint test ## Lint and test — what CI should run

frontend-install: ## Install frontend dependencies
	cd $(FRONTEND_DIR) && $(NPM) install

frontend-dev: ## Run the frontend dev server
	cd $(FRONTEND_DIR) && $(NPM) run dev

frontend-build: ## Build the frontend
	cd $(FRONTEND_DIR) && $(NPM) run build

frontend-lint: ## Lint the frontend
	cd $(FRONTEND_DIR) && $(NPM) run lint

index-rag: ## Index the configuration guide into the vector store
	$(PY) scripts/index_zk_config.py

clean: ## Remove caches and build artefacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	cd $(FRONTEND_DIR) && rm -rf dist/ node_modules/.cache/ 2>/dev/null || true
