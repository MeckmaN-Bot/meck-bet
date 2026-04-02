#!/usr/bin/env bash
# =============================================================================
# Meck-Bet Linux Installer
# =============================================================================
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# ── Dependency checks ─────────────────────────────────────────────────────────
check_deps() {
    step "Checking system dependencies"

    local missing=0

    # Python 3.10+
    if command -v python3 &>/dev/null; then
        PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PYTHON_MAJOR=$(echo "$PYTHON_VER" | cut -d. -f1)
        PYTHON_MINOR=$(echo "$PYTHON_VER" | cut -d. -f2)
        if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
            ok "Python $PYTHON_VER"
        else
            fail "Python $PYTHON_VER found, but 3.10+ required"
            echo "    Install: sudo apt install python3.11 python3.11-venv"
            missing=1
        fi
    else
        fail "Python 3 not found"
        echo "    Install: sudo apt install python3.11 python3.11-venv python3.11-pip"
        missing=1
    fi

    # pip / venv
    if python3 -c "import venv" &>/dev/null; then
        ok "python3-venv"
    else
        fail "python3-venv not found"
        echo "    Install: sudo apt install python3.11-venv"
        missing=1
    fi

    # Node 18+
    if command -v node &>/dev/null; then
        NODE_VER=$(node --version | sed 's/v//')
        NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
        if [ "$NODE_MAJOR" -ge 18 ]; then
            ok "Node.js v$NODE_VER"
        else
            fail "Node.js v$NODE_VER found, but 18+ required"
            echo "    Install: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install nodejs"
            missing=1
        fi
    else
        fail "Node.js not found"
        echo "    Install: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install nodejs"
        missing=1
    fi

    # npm
    if command -v npm &>/dev/null; then
        ok "npm $(npm --version)"
    else
        fail "npm not found (usually comes with Node.js)"
        missing=1
    fi

    # git (for version info)
    if command -v git &>/dev/null; then
        ok "git $(git --version | awk '{print $3}')"
    else
        warn "git not found (optional)"
    fi

    if [ "$missing" -ne 0 ]; then
        echo ""
        echo -e "${RED}Missing dependencies. Install them and re-run this script.${NC}"
        exit 1
    fi
}

# ── Python virtual environment ────────────────────────────────────────────────
setup_python() {
    step "Setting up Python backend"

    cd "$INSTALL_DIR/backend"

    if [ ! -d ".venv" ]; then
        info "Creating virtual environment..."
        python3 -m venv .venv
        ok "Virtual environment created"
    else
        ok "Virtual environment already exists"
    fi

    info "Installing Python dependencies..."
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
    ok "Python dependencies installed"

    cd "$INSTALL_DIR"
}

# ── Frontend build ────────────────────────────────────────────────────────────
setup_frontend() {
    step "Building frontend"

    cd "$INSTALL_DIR/frontend"

    info "Installing Node.js dependencies..."
    npm install --silent
    ok "Node dependencies installed"

    info "Building production bundle..."
    npm run build
    ok "Frontend built → frontend/dist/"

    cd "$INSTALL_DIR"
}

# ── Onboarding wizard ─────────────────────────────────────────────────────────
run_onboarding() {
    step "Running setup wizard"

    cd "$INSTALL_DIR/backend"

    if [ -f ".env" ]; then
        echo ""
        echo -e "  ${YELLOW}A .env file already exists.${NC}"
        read -r -p "  Re-run setup wizard? [y/N] " RERUN
        if [[ ! "$RERUN" =~ ^[Yy]$ ]]; then
            ok "Keeping existing .env"
            cd "$INSTALL_DIR"
            return
        fi
    fi

    .venv/bin/python3 "$INSTALL_DIR/setup.py"

    cd "$INSTALL_DIR"
}

# ── Systemd service (optional) ────────────────────────────────────────────────
install_service() {
    step "Systemd service setup"

    echo ""
    echo -e "  Install Meck-Bet as a systemd service? (starts automatically on boot)"
    read -r -p "  Install service? [y/N] " INSTALL_SVC

    if [[ ! "$INSTALL_SVC" =~ ^[Yy]$ ]]; then
        info "Skipping systemd service setup"
        return
    fi

    SERVICE_USER="${SUDO_USER:-$(whoami)}"
    SERVICE_FILE="/etc/systemd/system/meck-bet.service"

    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Meck-Bet NBA Value Betting Analyzer
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR/backend
ExecStart=$INSTALL_DIR/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
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
        ok "Systemd service installed and started"
        ok "Service: sudo systemctl status meck-bet"
    else
        warn "Service installed but may not have started yet"
        info "Check: sudo journalctl -u meck-bet -n 50"
    fi
}

# ── Nginx config (optional) ───────────────────────────────────────────────────
setup_nginx() {
    if ! command -v nginx &>/dev/null; then
        return
    fi

    echo ""
    echo -e "  nginx detected. Configure reverse proxy? (recommended for production)"
    read -r -p "  Setup nginx? [y/N] " SETUP_NGINX

    if [[ ! "$SETUP_NGINX" =~ ^[Yy]$ ]]; then
        return
    fi

    read -r -p "  Domain name (e.g. meck-bet.example.com, or leave empty for IP): " DOMAIN
    DOMAIN="${DOMAIN:-_}"

    NGINX_CONF="/etc/nginx/sites-available/meck-bet"
    sudo tee "$NGINX_CONF" > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    # Proxy all requests to FastAPI (which serves both API and frontend)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }
}
EOF

    sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/meck-bet
    sudo nginx -t && sudo systemctl reload nginx
    ok "nginx configured for $DOMAIN"
}

# ── Final summary ─────────────────────────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║           Installation complete! 🎉              ║${NC}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    if systemctl is-active --quiet meck-bet 2>/dev/null; then
        echo -e "  ${GREEN}Service running.${NC} Dashboard: ${BOLD}http://$(hostname -I | awk '{print $1}'):8000${NC}"
    else
        echo -e "  ${BOLD}Start the app:${NC}"
        echo -e "    ${CYAN}make start${NC}          # Start in background (screen)"
        echo -e "    ${CYAN}make dev${NC}             # Start in foreground (dev mode)"
    fi

    echo ""
    echo -e "  ${BOLD}Useful commands:${NC}"
    echo -e "    ${CYAN}make status${NC}          # Check if running"
    echo -e "    ${CYAN}make logs${NC}            # View live logs"
    echo -e "    ${CYAN}make stop${NC}            # Stop the app"
    echo -e "    ${CYAN}make update${NC}          # Pull latest changes + rebuild"
    echo ""
    echo -e "  ${BOLD}API Docs:${NC}   http://localhost:8000/api/docs"
    echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    print_header
    check_deps
    setup_python
    setup_frontend
    run_onboarding

    # Only offer systemd/nginx if running as root or with sudo
    if [ "$EUID" -eq 0 ] || sudo -n true 2>/dev/null; then
        install_service
        setup_nginx
    else
        echo ""
        warn "Not running as root — skipping systemd/nginx setup"
        info "Re-run with sudo to install as a system service"
    fi

    print_summary
}

main "$@"
