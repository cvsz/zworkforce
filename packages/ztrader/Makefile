# ============================================================================
#  ztrader — ZeaZ Platform App
# ============================================================================

APP_NAME := ztrader
STACK    := auto
PORT     ?= 3190

PLATFORM_ROOT := $(shell git rev-parse --show-toplevel 2>/dev/null || echo ../..)

include $(PLATFORM_ROOT)/make/common.mk

# ── App-specific targets ──────────────────────────────────────────────────

.PHONY: install dev build test lint ta-analyze ta-server
.PHONY: docker-up docker-up-llm docker-up-full docker-down docker-logs status

# Auto-port: find next available port if the default is taken
PORT     ?= 3190
_port_check = $(shell ss -tlnp 2>/dev/null | grep -q ":$1 " && echo "inuse" || echo "free")
_next_port = $(shell p=$1; while ss -tlnp 2>/dev/null | grep -q ":$$p "; do p=$$((p + 1)); done; echo $$p)

install: ## Install ztrader + TradingAgents dependencies
	@echo "Checking port $(PORT)..."
	@if [ "$(call _port_check,$(PORT))" = "inuse" ]; then \
		NEW_PORT=$(call _next_port,$(PORT)); \
		echo "Port $(PORT) in use. Auto-selecting port $$NEW_PORT..."; \
		sed -i "s/^PORT\\s*?\\?=\\s*$(PORT)/PORT ?= $$NEW_PORT/" Makefile; \
		echo "Updated Makefile: PORT = $$NEW_PORT"; \
	fi
	@cd backend && pip install -r requirements.txt
	@cd backend && pip install tradingagents>=0.3.0
	@cd frontend && pnpm install
	@echo "ztrader + TradingAgents dependencies installed"

dev: ## Start ztrader development servers
	@echo "Starting ztrader backend + frontend..."
	@PORT=$(PORT); \
	if ss -tlnp 2>/dev/null | grep -q ":$$PORT "; then \
		while ss -tlnp 2>/dev/null | grep -q ":$$PORT "; do PORT=$$((PORT + 1)); done; \
		echo "Port $(PORT) in use. Using port $$PORT instead."; \
	fi; \
	cd backend && uvicorn ztrader.main:app --reload --host 0.0.0.0 --port $$PORT &
	@sleep 2 && cd frontend && pnpm dev &

build: ## Build ztrader for production
	@cd backend && pip install -r requirements.txt
	@cd frontend && pnpm build
	@echo "ztrader build complete"

test: ## Run ztrader tests
	@cd backend && python -m pytest tests/ -v --cov=src --cov-report=term-missing
	@cd frontend && pnpm test -- --run

lint: ## Lint ztrader code
	@cd backend && ruff check src/
	@cd frontend && pnpm lint

ta-analyze: ## Run TradingAgents analysis (usage: make ta-analyze SYMBOL=NVDA)
	@test -n "$(SYMBOL)" || (echo 'ERROR: Set SYMBOL=<ticker>' && exit 1)
	@cd backend && python -c "
from ztrader.tradingagents_integration.adapter import TradingAgentsStrategy
s = TradingAgentsStrategy(llm_provider=openai, debug=True)
r = s.analyze('$(SYMBOL)')
print(f'Signal: {r.signal} | Confidence: {r.confidence:.2f} | Risk: {r.risk_score:.2f}')
print(f'Reasoning: {r.reasoning}')
"

ta-server: ## Start TradingAgents API server
	@PORT=$(PORT); \
	if ss -tlnp 2>/dev/null | grep -q ":$$PORT "; then \
		while ss -tlnp 2>/dev/null | grep -q ":$$PORT "; do PORT=$$((PORT + 1)); done; \
		echo "Port $(PORT) in use. Using port $$PORT instead."; \
	fi; \
	echo "Starting TradingAgents API on port $$PORT..." && \
	cd backend && uvicorn ztrader.tradingagents_integration.api:router --reload --host 0.0.0.0 --port $$PORT

docker-up: ## Start ztrader services via Docker Compose
	@docker compose up -d --build

docker-up-llm: ## Start ztrader + TradingAgents LLM services
	@docker compose --profile llm up -d --build

docker-up-full: ## Start all ztrader services including LLM
	@docker compose --profile full up -d --build

docker-down: ## Stop ztrader services
	@docker compose down

docker-logs: ## View ztrader container logs
	@docker compose logs -f

status: ## Check ztrader service status
	@docker compose ps
