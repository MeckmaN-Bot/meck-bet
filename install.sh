#!/usr/bin/env bash
# =============================================================================
# Meck-Bet Linux Installer
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$INSTALL_DIR/backend"
FRONTEND_DIR="$INSTALL_DIR/frontend"

print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}║      🏀  MECK-BET  —  NBA Value Analyzer         ║${NC}"
    echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
}

ok()   { echo -e "  ${GREEN}✓${NC}  $1"; }
info() { echo -e "  ${CYAN}→${NC}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
fail() { echo -e "  ${RED}✗${NC}  $1"; }
step() { echo -e "\n${BOLD}${BLUE}▸ $1${NC}"; }

# ── Helper: read a value from backend/.env ────────────────────────────────────
env_val() {
    grep -m1 "^${1}=" "$BACKEND_DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo "${2:-}"
}

# ── Dependency checks ─────────────────────────────────────────────────────────
check_deps() {
    step "Checking system dependencies"
    local missing=0

    # Python 3.10+
    if command -v python3 &>/dev/null; then
        PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PY_MAJ=$(echo "$PY_VER" | cut -d. -f1)
        PY_MIN=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$PY_MAJ" -ge 3 ] && [ "$PY_MIN" -ge 10 ]; then
            ok "Python $PY_VER"
        else
            fail "Python $PY_VER found — 3.10+ required"
            echo "      sudo apt install python3.11 python3.11-venv"
            missing=1
        fi
    else
        fail "Python 3 not found"
        echo "      sudo apt install python3.11 python3.11-venv python3.11-pip"
        missing=1
    fi

    # python3-venv
    if python3 -c "import venv" &>/dev/null; then
        ok "python3-venv"
    else
        fail "python3-venv not found"
        echo "      sudo apt install python3.11-venv"
        missing=1
    fi

    # Node.js 18+
    if command -v node &>/dev/null; then
        NODE_VER=$(node --version | sed 's/v//')
        NODE_MAJ=$(echo "$NODE_VER" | cut -d. -f1)
        if [ "$NODE_MAJ" -ge 18 ]; then
            ok "Node.js v$NODE_VER"
        else
            fail "Node.js v$NODE_VER found — 18+ required"
            echo "      curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
            echo "      sudo apt install nodejs"
            missing=1
        fi
    else
        fail "Node.js not found"
        echo "      curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
        echo "      sudo apt install nodejs"
        missing=1
    fi

    # npm
    if command -v npm &>/dev/null; then
        ok "npm $(npm --version)"
    else
        fail "npm not found (comes with Node.js)"
        missing=1
    fi

    # screen (for background process management)
    if command -v screen &>/dev/null; then
        ok "screen $(screen --version | head -1 | awk '{print $3}')"
    else
        warn "screen not found — install for background mode"
        echo "      sudo apt install screen"
        # Non-fatal: systemd is an alternative
    fi

    # lsof (for port checks)
    if ! command -v lsof &>/dev/null; then
        warn "lsof not found — port conflict detection disabled"
        echo "      sudo apt install lsof"
    fi

    if [ "$missing" -ne 0 ]; then
        echo ""
        echo -e "${RED}  Missing required dependencies. Install them and re-run.${NC}"
        exit 1
    fi
}

# ── Python venv + deps ────────────────────────────────────────────────────────
setup_python() {
    step "Setting up Python backend"
    cd "$BACKEND_DIR"

    if [ ! -d ".venv" ]; then
        info "Creating virtual environment …"
        python3 -m venv .venv
    fi
    ok "Virtual environment ready"

    info "Installing Python dependencies …"
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
    ok "Python dependencies installed"

    cd "$INSTALL_DIR"
}

# ── Onboarding wizard ─────────────────────────────────────────────────────────
run_onboarding() {
    step "Configuration wizard"

    if [ -f "$BACKEND_DIR/.env" ]; then
        echo ""
        echo -e "  ${YELLOW}A backend/.env already exists.${NC}"
        read -r -p "  Re-run the setup wizard? [y/N] " RERUN
        if [[ ! "$RERUN" =~ ^[Yy]$ ]]; then
            ok "Keeping existing configuration"
            return
        fi
    fi

    "$BACKEND_DIR/.venv/bin/python3" "$INSTALL_DIR/setup.py"
}

# ── Frontend build ────────────────────────────────────────────────────────────
setup_frontend() {
    step "Building frontend"
    cd "$FRONTEND_DIR"

    info "Installing Node.js dependencies …"
    npm install --silent
    ok "Node dependencies installed"

    info "Building production bundle …"
    npm run build
    ok "Frontend built → frontend/dist/"

    cd "$INSTALL_DIR"
}

# ── Systemd service (optional, requires sudo) ─────────────────────────────────
install_service() {
    step "Systemd service (optional)"

    echo ""
    echo -e "  Install Meck-Bet as a systemd service?"
    echo -e "  ${CYAN}→${NC} Starts automatically on boot, managed with systemctl."
    read -r -p "  Install service? [y/N] " DO_SVC
    [[ ! "$DO_SVC" =~ ^[Yy]$ ]] && { info "Skipping systemd setup"; return; }

    # Read port from .env (default 8000)
    PORT=$(env_val PORT 8000)
    SVC_USER="${SUDO_USER:-$(whoami)}"
    SVC_FILE="/etc/systemd/system/meck-bet.service"

    sudo tee "$SVC_FILE" > /dev/null <<EOF
[Unit]
Description=Meck-Bet NBA Value Betting Analyzer
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SVC_USER
WorkingDirectory=$BACKEND_DIR
ExecStart=$BACKEND_DIR/.venv/bin/uvicorn main:app \\
    --host 0.0.0.0 --port $PORT --workers 1
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=meck-bet
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable meck-bet
    sudo systemctl start meck-bet

    sleep 2
    if sudo systemctl is-active --quiet meck-bet; then
        ok "Systemd service running on port $PORT"
        info "Manage: sudo systemctl {start|stop|restart|status} meck-bet"
        info "Logs:   sudo journalctl -u meck-bet -f"
    else
        warn "Service installed but not yet active"
        info "Check:  sudo journalctl -u meck-bet -n 50"
    fi
}

# ── nginx config ──────────────────────────────────────────────────────────────
install_nginx() {
    # Only offer if nginx is installed and we have sudo
    command -v nginx &>/dev/null || return
    sudo -n true 2>/dev/null || return

    # setup.py already wrote nginx-meck-bet.conf — offer to install it
    NGINX_CONF="$INSTALL_DIR/nginx-meck-bet.conf"
    [ -f "$NGINX_CONF" ] || return

    step "nginx configuration"
    echo ""
    echo -e "  nginx detected. Install the generated config?"
    echo -e "  ${CYAN}→${NC} $NGINX_CONF"
    read -r -p "  Install nginx config? [y/N] " DO_NGINX
    [[ ! "$DO_NGINX" =~ ^[Yy]$ ]] && { info "Skipping nginx setup"; return; }

    sudo cp "$NGINX_CONF" /etc/nginx/sites-available/meck-bet
    sudo ln -sf /etc/nginx/sites-available/meck-bet /etc/nginx/sites-enabled/meck-bet

    if sudo nginx -t 2>/dev/null; then
        sudo systemctl reload nginx
        ok "nginx configured and reloaded"

        PUBLIC_URL=$(env_val PUBLIC_URL "")
        if [[ "$PUBLIC_URL" == https://* ]]; then
            DOMAIN=$(echo "$PUBLIC_URL" | sed 's|https://||' | cut -d/ -f1)
            echo ""
            echo -e "  ${YELLOW}To enable HTTPS (free via Let's Encrypt):${NC}"
            echo -e "    sudo apt install certbot python3-certbot-nginx"
            echo -e "    sudo certbot --nginx -d $DOMAIN"
        fi
    else
        warn "nginx config test failed — check $NGINX_CONF manually"
        sudo rm -f /etc/nginx/sites-enabled/meck-bet
    fi
}

# ── Summary ───────────────────────────────────────────────────────────────────
print_summary() {
    PORT=$(env_val PORT 8000)
    PUBLIC_URL=$(env_val PUBLIC_URL "http://localhost:$PORT")

    echo ""
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║           Installation complete! 🎉              ║${NC}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    if systemctl is-active --quiet meck-bet 2>/dev/null; then
        ok "Systemd service is running"
    fi

    echo -e "  ${BOLD}Start / stop:${NC}"
    echo -e "    ${CYAN}make start${NC}         Background (screen, port $PORT)"
    echo -e "    ${CYAN}make stop${NC}          Stop"
    echo -e "    ${CYAN}make status${NC}        Status + port check"
    echo -e "    ${CYAN}make logs${NC}          Live log tail"
    echo -e "    ${CYAN}make dev${NC}           Foreground with auto-reload"
    echo ""
    echo -e "  ${BOLD}Dashboard:${NC}  $PUBLIC_URL"
    echo -e "  ${BOLD}API Docs:${NC}   ${PUBLIC_URL%/}/api/docs"
    echo ""
    echo -e "  ${BOLD}Useful:${NC}"
    echo -e "    ${CYAN}make demo-data${NC}     Inject 30 days of sample data"
    echo -e "    ${CYAN}make setup${NC}         Re-run this wizard"
    echo -e "    ${CYAN}make update${NC}        Pull latest + rebuild"
    echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    print_header
    check_deps
    setup_python
    run_onboarding         # writes .env + nginx-meck-bet.conf
    setup_frontend         # npm install + npm run build (reads VITE_BASE_PATH from .env.production)

    if [ "$EUID" -eq 0 ] || sudo -n true 2>/dev/null; then
        install_service
        install_nginx
    else
        echo ""
        warn "Not running as root — skipping systemd/nginx setup."
        info "Re-run with sudo to install as a system service."
    fi

    print_summary
}

main "$@"
