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
PORT          := 8000
APP_NAME      := meck-bet
SCREEN_NAME   := meck-bet

.PHONY: help install setup dev start stop restart status logs build update \
        test-api demo-data reset-model clean

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  🏀  Meck-Bet — Available Commands"
	@echo "  ─────────────────────────────────────────────"
	@echo "  make install       Full installation (first time setup)"
	@echo "  make setup         Re-run setup wizard (reconfigure)"
	@echo ""
	@echo "  make start         Start in background (uses screen)"
	@echo "  make stop          Stop background process"
	@echo "  make restart       Restart"
	@echo "  make status        Check if running"
	@echo "  make logs          Tail live logs"
	@echo ""
	@echo "  make dev           Run in foreground (dev mode with reload)"
	@echo "  make build         Rebuild frontend only"
	@echo "  make update        Pull latest + rebuild + restart"
	@echo ""
	@echo "  make test-api      Test Odds API connection"
	@echo "  make demo-data     Inject 30 days of demo data"
	@echo "  make reset-model   Reset learning model to defaults"
	@echo "  make clean         Remove build artifacts and venv"
	@echo ""

# ── Installation ──────────────────────────────────────────────────────────────
install:
	@chmod +x install.sh
	@./install.sh

setup:
	@$(PYTHON) $(INSTALL_DIR)/setup.py

# ── Build ─────────────────────────────────────────────────────────────────────
build:
	@echo "→ Building frontend..."
	@cd $(FRONTEND_DIR) && npm run build
	@echo "✓ Frontend built"

# ── Run modes ─────────────────────────────────────────────────────────────────
dev:
	@echo "→ Starting in dev mode (Ctrl+C to stop)..."
	@cd $(BACKEND_DIR) && $(UVICORN) main:app --host 0.0.0.0 --port $(PORT) --reload

start:
	@if screen -list | grep -q "$(SCREEN_NAME)"; then \
		echo "⚠  Already running. Use 'make restart' to restart."; \
	else \
		screen -dmS $(SCREEN_NAME) bash -c \
			"cd $(BACKEND_DIR) && $(UVICORN) main:app --host 0.0.0.0 --port $(PORT) --workers 1 2>&1 | tee meck-bet.log"; \
		sleep 2; \
		if screen -list | grep -q "$(SCREEN_NAME)"; then \
			echo "✓ Meck-Bet started on http://0.0.0.0:$(PORT)"; \
			echo "  Dashboard: http://localhost:$(PORT)"; \
			echo "  Use 'make logs' to view output"; \
		else \
			echo "✗ Start failed. Run 'make dev' to see errors."; \
		fi \
	fi

stop:
	@if screen -list | grep -q "$(SCREEN_NAME)"; then \
		screen -S $(SCREEN_NAME) -X quit; \
		echo "✓ Meck-Bet stopped"; \
	else \
		echo "⚠  Not running"; \
	fi

restart: stop
	@sleep 1
	@$(MAKE) start

status:
	@if screen -list | grep -q "$(SCREEN_NAME)"; then \
		echo "✓ Running (screen session: $(SCREEN_NAME))"; \
		echo "  Dashboard: http://localhost:$(PORT)"; \
	elif systemctl is-active --quiet $(APP_NAME) 2>/dev/null; then \
		echo "✓ Running (systemd service)"; \
		systemctl status $(APP_NAME) --no-pager -l | head -20; \
	else \
		echo "✗ Not running"; \
	fi

logs:
	@if screen -list | grep -q "$(SCREEN_NAME)"; then \
		tail -f $(BACKEND_DIR)/meck-bet.log 2>/dev/null || \
		screen -S $(SCREEN_NAME) -x; \
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
	@$(PYTHON) -c "\
import asyncio, sys; sys.path.insert(0,'$(BACKEND_DIR)'); \
from core.odds_fetcher import odds_client; \
from config import settings; \
result = asyncio.run(odds_client.get_sports()); \
print(f'✓ API connected: {len(result)} sports available'); \
print(f'  Quota: {odds_client.quota_info()}') \
" 2>&1 | grep -v "^$$" || echo "✗ API test failed. Check your ODDS_API_KEY in backend/.env"

demo-data:
	@echo "→ Injecting 30 days of demo data..."
	@curl -s -X POST "http://localhost:$(PORT)/api/nba/demo/inject?days=30" | \
		python3 -c "import sys,json; d=json.load(sys.stdin); print(f'✓ Injected {d.get(\"injected_simulations\",0)} simulations, {d.get(\"injected_picks\",0)} picks')"

reset-model:
	@echo "→ Resetting learning model to defaults..."
	@curl -s -X POST "http://localhost:$(PORT)/api/nba/model/reset" | \
		python3 -c "import sys,json; d=json.load(sys.stdin); print(f'✓ Model reset: {d}')"

clean:
	@echo "→ Cleaning build artifacts..."
	@rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/node_modules
	@rm -rf $(BACKEND_DIR)/.venv $(BACKEND_DIR)/__pycache__
	@find $(BACKEND_DIR) -name "*.pyc" -delete
	@echo "✓ Clean complete. Run 'make install' to reinstall."
