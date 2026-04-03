##############################################################################
# Meck-Bet Makefile
# Usage: make <target>
##############################################################################

SHELL         := /bin/bash
INSTALL_DIR   := $(shell pwd)
BACKEND_DIR   := $(INSTALL_DIR)/backend
FRONTEND_DIR  := $(INSTALL_DIR)/frontend
PYTHON        := $(BACKEND_DIR)/.venv/bin/python3
UVICORN       := $(BACKEND_DIR)/.venv/bin/uvicorn
APP_NAME      := meck-bet

# Read PORT from backend/.env — fallback to 8000 if not set
PORT          := $(shell grep -m1 '^PORT=' $(BACKEND_DIR)/.env 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo 8000)
# Read PUBLIC_URL from .env for display — fallback to http://localhost:PORT
PUBLIC_URL    := $(shell grep -m1 '^PUBLIC_URL=' $(BACKEND_DIR)/.env 2>/dev/null | cut -d= -f2 | tr -d ' ')
ifeq ($(PUBLIC_URL),)
  PUBLIC_URL  := http://localhost:$(PORT)
endif

# Unique screen session name — includes port to avoid conflicts with other services
SCREEN_NAME   := meck-bet-$(PORT)

.PHONY: help install setup dev start stop restart status logs build update \
        test-api demo-data reset-model clean port-check

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  🏀  Meck-Bet — Available Commands"
	@echo "  ─────────────────────────────────────────────"
	@echo "  make install       Full installation (first time setup)"
	@echo "  make setup         Re-run setup wizard (reconfigure)"
	@echo ""
	@echo "  make start         Start in background (screen)"
	@echo "  make stop          Stop background process"
	@echo "  make restart       Restart"
	@echo "  make status        Check if running"
	@echo "  make logs          Tail live logs"
	@echo ""
	@echo "  make dev           Run in foreground (dev mode with reload)"
	@echo "  make build         Rebuild frontend"
	@echo "  make update        Pull latest + rebuild + restart"
	@echo ""
	@echo "  make port-check    Check if configured port is available"
	@echo "  make test-api      Test Odds API connection"
	@echo "  make demo-data     Inject 30 days of demo data"
	@echo "  make reset-model   Reset learning model to defaults"
	@echo "  make clean         Remove build artifacts and venv"
	@echo ""
	@echo "  Current config:"
	@echo "    PORT       = $(PORT)"
	@echo "    URL        = $(PUBLIC_URL)"
	@echo "    Screen     = $(SCREEN_NAME)"
	@echo ""

# ── Installation ──────────────────────────────────────────────────────────────
install:
	@chmod +x install.sh
	@./install.sh

setup:
	@$(PYTHON) $(INSTALL_DIR)/setup.py

# ── Port check ────────────────────────────────────────────────────────────────
port-check:
	@if lsof -i :$(PORT) -sTCP:LISTEN -t >/dev/null 2>&1; then \
		echo "⚠  Port $(PORT) is already in use:"; \
		lsof -i :$(PORT) -sTCP:LISTEN | tail -n +2; \
		echo "  Change PORT in backend/.env to a free port, then run 'make build && make start'"; \
	else \
		echo "✓ Port $(PORT) is free"; \
	fi

# ── Build ─────────────────────────────────────────────────────────────────────
build:
	@echo "→ Building frontend..."
	@cd $(FRONTEND_DIR) && npm run build
	@echo "✓ Frontend built → frontend/dist/"

# ── Run modes ─────────────────────────────────────────────────────────────────
dev:
	@echo "→ Starting in dev mode on port $(PORT) (Ctrl+C to stop)..."
	@cd $(BACKEND_DIR) && $(UVICORN) main:app \
		--host 0.0.0.0 --port $(PORT) --reload

start: port-check
	@if screen -list 2>/dev/null | grep -q "$(SCREEN_NAME)"; then \
		echo "⚠  Already running (screen: $(SCREEN_NAME)). Use 'make restart'."; \
	else \
		screen -dmS $(SCREEN_NAME) bash -c \
			"cd $(BACKEND_DIR) && $(UVICORN) main:app \
			--host 0.0.0.0 --port $(PORT) --workers 1 \
			2>&1 | tee meck-bet.log"; \
		sleep 2; \
		if screen -list 2>/dev/null | grep -q "$(SCREEN_NAME)"; then \
			echo "✓ Meck-Bet started"; \
			echo "  Dashboard : $(PUBLIC_URL)"; \
			echo "  API Docs  : $(PUBLIC_URL)/api/docs"; \
			echo "  Logs      : make logs"; \
		else \
			echo "✗ Failed to start. Run 'make dev' to see errors."; \
		fi \
	fi

stop:
	@if screen -list 2>/dev/null | grep -q "$(SCREEN_NAME)"; then \
		screen -S $(SCREEN_NAME) -X quit; \
		echo "✓ Meck-Bet stopped (was on port $(PORT))"; \
	elif systemctl is-active --quiet $(APP_NAME) 2>/dev/null; then \
		sudo systemctl stop $(APP_NAME); \
		echo "✓ Systemd service stopped"; \
	else \
		echo "⚠  Not running"; \
	fi

restart: stop
	@sleep 1
	@$(MAKE) start

status:
	@if screen -list 2>/dev/null | grep -q "$(SCREEN_NAME)"; then \
		echo "✓ Running  (screen: $(SCREEN_NAME))"; \
		echo "  Dashboard : $(PUBLIC_URL)"; \
	elif systemctl is-active --quiet $(APP_NAME) 2>/dev/null; then \
		echo "✓ Running  (systemd service)"; \
		systemctl status $(APP_NAME) --no-pager -l | head -15; \
	else \
		echo "✗ Not running"; \
	fi
	@echo ""
	@$(MAKE) --no-print-directory port-check

logs:
	@if screen -list 2>/dev/null | grep -q "$(SCREEN_NAME)"; then \
		echo "→ Tailing $(BACKEND_DIR)/meck-bet.log (Ctrl+C to stop)..."; \
		tail -f $(BACKEND_DIR)/meck-bet.log; \
	elif systemctl is-active --quiet $(APP_NAME) 2>/dev/null; then \
		sudo journalctl -u $(APP_NAME) -f --no-pager; \
	else \
		echo "⚠  Not running. Start with 'make start'"; \
	fi

# ── Update ────────────────────────────────────────────────────────────────────
update:
	@echo "→ Pulling latest changes..."
	@git pull
	@echo "→ Updating Python dependencies..."
	@$(BACKEND_DIR)/.venv/bin/pip install --quiet -r $(BACKEND_DIR)/requirements.txt
	@echo "→ Rebuilding frontend..."
	@cd $(FRONTEND_DIR) && npm install --silent && npm run build
	@echo "→ Restarting..."
	@$(MAKE) restart
	@echo "✓ Update complete"

# ── Utilities ─────────────────────────────────────────────────────────────────
test-api:
	@cd $(BACKEND_DIR) && $(PYTHON) -c "\
import asyncio, sys; sys.path.insert(0,'.'); \
from core.odds_fetcher import odds_client; \
async def run(): \
    result = await odds_client.get_sports(); \
    print(f'✓ API connected: {len(result)} sports available'); \
    print(f'  Quota: {odds_client.quota_info()}'); \
asyncio.run(run()) \
" 2>&1 || echo "✗ API test failed. Check ODDS_API_KEY in backend/.env"

demo-data:
	@echo "→ Injecting 30 days of demo data..."
	@curl -sf -X POST "http://localhost:$(PORT)/api/nba/demo/inject?days=30" \
		| python3 -c "import sys,json; d=json.load(sys.stdin); \
		  print(f'✓ Injected {d.get(\"injected_simulations\",0)} days, {d.get(\"injected_picks\",0)} picks')" \
		|| echo "✗ Failed — is the server running? (make status)"

reset-model:
	@echo "→ Resetting learning model to defaults..."
	@curl -sf -X POST "http://localhost:$(PORT)/api/nba/model/reset" \
		| python3 -c "import sys,json; d=json.load(sys.stdin); print(f'✓ Model reset to v{d.get(\"version\",1)}')" \
		|| echo "✗ Failed — is the server running? (make status)"

clean:
	@echo "→ Cleaning build artifacts..."
	@rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/node_modules
	@rm -rf $(BACKEND_DIR)/.venv $(BACKEND_DIR)/__pycache__
	@find $(BACKEND_DIR) -name "*.pyc" -delete 2>/dev/null; true
	@echo "✓ Clean. Run 'make install' to reinstall."
