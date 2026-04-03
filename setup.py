#!/usr/bin/env python3
"""
Meck-Bet Interactive Setup Wizard
===================================
Guides through all required configuration.
Creates backend/.env  +  frontend/.env.production (base path).

Usage:
    python3 setup.py
    # or called automatically by install.sh
"""

import os
import sys
import socket
import asyncio
import textwrap
import subprocess
from pathlib import Path

# ── Color helpers (zero deps) ─────────────────────────────────────────────────
def _c(code, text): return f"\033[{code}m{text}\033[0m"
def green(t):  return _c("32", t)
def yellow(t): return _c("33", t)
def red(t):    return _c("31", t)
def cyan(t):   return _c("36", t)
def bold(t):   return _c("1",  t)
def dim(t):    return _c("2",  t)

def ok(m):   print(f"  {green('✓')}  {m}")
def info(m): print(f"  {cyan('→')}  {m}")
def warn(m): print(f"  {yellow('⚠')}  {m}")
def err(m):  print(f"  {red('✗')}  {m}")

def ask(prompt, default=None):
    suffix = f" {dim('[' + str(default) + ']')}" if default is not None else ""
    val = input(f"  {bold('?')}  {prompt}{suffix}: ").strip()
    return val if val else (str(default) if default is not None else "")

def ask_yn(prompt, default=True):
    suffix = dim("[Y/n]") if default else dim("[y/N]")
    ans = input(f"  {bold('?')}  {prompt} {suffix}: ").strip().lower()
    return default if not ans else ans.startswith("y")

def section(title):
    print(f"\n{bold(cyan('▸ ' + title))}")

def hr():
    print(f"  {dim('─' * 54)}")


REPO_ROOT   = Path(__file__).parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
ENV_FILE    = BACKEND_DIR / ".env"


# ── Port helpers ──────────────────────────────────────────────────────────────

def port_is_free(port: int) -> bool:
    """Return True if the TCP port is not currently bound by any process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def who_uses_port(port: int) -> str:
    """Return a short description of what's using the port, or ''."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-n", "-P"],
            capture_output=True, text=True, timeout=3
        )
        lines = result.stdout.strip().splitlines()
        if len(lines) > 1:
            parts = lines[1].split()
            return f"{parts[0]} (PID {parts[1]})" if len(parts) >= 2 else lines[1]
    except Exception:
        pass
    return ""


# ── API key test ──────────────────────────────────────────────────────────────

async def _test_key(key: str):
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://api.the-odds-api.com/v4/sports",
                params={"apiKey": key}
            )
            if r.status_code == 200:
                remaining = r.headers.get("x-requests-remaining", "?")
                return True, f"{len(r.json())} sports available · {remaining} requests remaining"
            if r.status_code == 401:
                return False, "Invalid API key (401 Unauthorized)"
            return False, f"HTTP {r.status_code}"
    except ImportError:
        return True, "(httpx not available — will validate at runtime)"
    except Exception as e:
        return False, f"Network error: {e}"


# ── Section collectors ────────────────────────────────────────────────────────

def collect_api_key() -> str:
    section("The Odds API Key")
    print(textwrap.dedent(f"""
  Aggregates live odds from 40+ bookmakers including Pinnacle.
  {bold('Free tier')}: 500 requests/month — enough for daily NBA analysis.
  {bold('Sign up')}: https://the-odds-api.com
    """).rstrip())

    while True:
        key = ask("Paste your API key (Enter = demo mode)")
        if not key:
            warn("No key — running in DEMO MODE with simulated data.")
            warn("Add ODDS_API_KEY to backend/.env later to go live.")
            return "YOUR_ODDS_API_KEY"

        print()
        info("Testing key …")
        valid, msg = asyncio.run(_test_key(key))
        if valid:
            ok(f"Key valid — {msg}")
            return key
        err(f"Key test failed: {msg}")
        if not ask_yn("Try a different key?", default=True):
            warn("Proceeding with untested key.")
            return key


def collect_port() -> int:
    section("Port")
    print(textwrap.dedent(f"""
  Meck-Bet needs one free TCP port.
  If you run other services (e.g. another app on 8000), pick a different port.
    """).rstrip())

    suggestion = 8000
    # Auto-find a free port starting from 8000
    for candidate in [8000, 8001, 8080, 8088, 8888, 9000]:
        if port_is_free(candidate):
            suggestion = candidate
            break

    while True:
        val = ask("Port", default=suggestion)
        try:
            port = int(val)
        except ValueError:
            err("Enter a number between 1024 and 65535.")
            continue

        if not (1024 <= port <= 65535):
            err("Port must be between 1024 and 65535.")
            continue

        if port_is_free(port):
            ok(f"Port {port} is free.")
            return port
        else:
            who = who_uses_port(port)
            err(f"Port {port} is already in use" + (f" by {who}" if who else "."))
            # Suggest next free port
            for alt in range(port + 1, port + 20):
                if port_is_free(alt):
                    warn(f"Suggestion: port {alt} is free.")
                    break


def collect_access_mode(port: int) -> dict:
    """
    Ask how the app will be accessed:
      A) Direct  — http://IP:PORT  (no nginx needed)
      B) Subdomain — https://meck-bet.example.com  (nginx reverse proxy)
      C) Subpath — https://example.com/meck-bet/   (nginx + base path rewrite)
    """
    section("Access / URL setup")
    print(textwrap.dedent(f"""
  How will you access Meck-Bet?

    {bold('1')}  Direct IP/port    http://YOUR_SERVER_IP:{port}
         (no nginx required, simplest option)

    {bold('2')}  Subdomain          https://bet.example.com
         (nginx reverse proxy, recommended for production)

    {bold('3')}  Subpath            https://example.com/meck-bet/
         (nginx reverse proxy + URL prefix, for shared domains)
    """).rstrip())

    choice = ask("Choose (1/2/3)", default="1")

    if choice == "2":
        domain = ask("Subdomain (e.g. bet.example.com)")
        if not domain:
            warn("No domain entered — falling back to direct mode.")
            return {"mode": "direct", "public_url": f"http://localhost:{port}", "base_path": "/"}
        public_url = f"https://{domain}"
        ok(f"Will generate nginx config for {public_url}")
        return {"mode": "subdomain", "public_url": public_url, "base_path": "/", "domain": domain}

    if choice == "3":
        subpath = ask("Subpath (e.g. /meck-bet)", default="/meck-bet")
        if not subpath.startswith("/"):
            subpath = "/" + subpath
        subpath = subpath.rstrip("/") + "/"   # ensure trailing slash
        domain = ask("Domain (e.g. example.com or IP)")
        if not domain:
            warn("No domain entered — falling back to direct mode.")
            return {"mode": "direct", "public_url": f"http://localhost:{port}", "base_path": "/"}
        public_url = f"https://{domain}{subpath.rstrip('/')}"
        ok(f"Will configure subpath: {public_url}")
        return {"mode": "subpath", "public_url": public_url, "base_path": subpath, "domain": domain}

    # Direct
    server_ip = _get_server_ip()
    public_url = f"http://{server_ip}:{port}"
    ok(f"Direct access at {public_url}")
    return {"mode": "direct", "public_url": public_url, "base_path": "/"}


def _get_server_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "YOUR_SERVER_IP"


def collect_bankroll() -> float:
    section("Simulated Bankroll")
    print("  Used for Kelly criterion stake sizing (simulation only, no real money).")
    while True:
        val = ask("Bankroll (€)", default="1000")
        try:
            f = float(val.replace(",", "."))
            if f >= 10:
                ok(f"Bankroll: €{f:.2f}")
                return f
            err("Minimum bankroll is €10.")
        except ValueError:
            err("Enter a number, e.g. 1000")


def collect_daily_picks() -> int:
    section("Daily NBA Picks")
    print("  How many bets the bot selects per day (recommended: 3–7).")
    while True:
        val = ask("Picks per day", default="5")
        try:
            n = int(val)
            if 1 <= n <= 20:
                ok(f"{n} pick(s) per day")
                return n
            err("Choose between 1 and 20.")
        except ValueError:
            err("Enter a whole number.")


def collect_kelly() -> float:
    section("Kelly Fraction")
    options = [
        ("0.10", "Tenth Kelly   — Very conservative"),
        ("0.25", "Quarter Kelly — Conservative  ✓  (recommended)"),
        ("0.50", "Half Kelly    — Moderate"),
        ("1.00", "Full Kelly    — Aggressive, high variance"),
    ]
    print()
    for i, (v, desc) in enumerate(options, 1):
        print(f"    {bold(str(i))}  {desc}")
    print()
    choice = ask("Choose (1–4)", default="2")
    idx = max(0, min(3, int(choice) - 1)) if choice.isdigit() else 1
    val, desc = options[idx]
    ok(f"Kelly: {val}× ({desc.split('—')[0].strip()})")
    return float(val)


def collect_min_ev() -> float:
    section("Minimum EV Threshold")
    print("  Bets below this edge are ignored. Higher = fewer but stronger bets.")
    while True:
        val = ask("Minimum EV %", default="2")
        try:
            f = float(val.replace("%", "").replace(",", "."))
            if 0.1 <= f <= 20:
                ok(f"Min EV: {f:.1f}%")
                return f / 100.0
            err("Enter a value between 0.1 and 20.")
        except ValueError:
            err("Enter a number like 2 or 3.5")


def collect_poll_interval() -> int:
    section("Odds Refresh Interval")
    print(textwrap.dedent(f"""
  How often to refresh bookmaker odds.
  {dim('Free API tier: 500 req/month. At 10 min intervals ≈ 144 req/day.')}
    """).rstrip())
    while True:
        val = ask("Interval (minutes)", default="10")
        try:
            n = int(val)
            if 1 <= n <= 60:
                ok(f"Odds refresh every {n} minute(s)")
                return n
            err("Choose between 1 and 60.")
        except ValueError:
            err("Enter a whole number.")


# ── Write files ───────────────────────────────────────────────────────────────

def write_env(cfg: dict):
    """Write backend/.env"""
    cors = cfg["public_url"] if cfg["mode"] != "direct" else "*"

    lines = f"""\
# Meck-Bet Configuration — generated by setup.py
# Edit manually or re-run: python3 setup.py

# ── The Odds API ──────────────────────────────────────────────────────────────
ODDS_API_KEY={cfg['api_key']}

# ── Server ────────────────────────────────────────────────────────────────────
HOST=0.0.0.0
PORT={cfg['port']}
PUBLIC_URL={cfg['public_url']}

# ── CORS ─────────────────────────────────────────────────────────────────────
# "*" is fine when nginx proxies (nginx enforces origin at the edge).
# For direct access without nginx list exact URLs:
#   CORS_ORIGINS=http://192.168.1.10:8080,https://bet.example.com
CORS_ORIGINS={cors}

# ── Bankroll & Betting ────────────────────────────────────────────────────────
DEFAULT_BANKROLL={cfg['bankroll']}
KELLY_FRACTION={cfg['kelly']}
MIN_EV_THRESHOLD={cfg['min_ev']}

# ── NBA Simulation ────────────────────────────────────────────────────────────
DAILY_PICKS={cfg['daily_picks']}
MIN_MODEL_CONFIDENCE=0.40

# ── Polling ───────────────────────────────────────────────────────────────────
POLL_INTERVAL_MINUTES={cfg['poll_interval']}
"""
    ENV_FILE.write_text(lines)
    ok(f"Backend config → {ENV_FILE}")


def write_frontend_env(base_path: str):
    """Write frontend/.env.production so Vite uses the correct base URL."""
    path = FRONTEND_DIR / ".env.production"
    path.write_text(f"VITE_BASE_PATH={base_path}\n")
    ok(f"Frontend base path → {path}  ({base_path})")


def write_nginx_config(cfg: dict):
    """Generate an nginx site config and print instructions."""
    mode      = cfg["mode"]
    port      = cfg["port"]
    domain    = cfg.get("domain", "_")
    base_path = cfg.get("base_path", "/")
    out_file  = REPO_ROOT / "nginx-meck-bet.conf"

    if mode == "subdomain":
        conf = f"""\
# Meck-Bet nginx config — subdomain mode
# Place in /etc/nginx/sites-available/meck-bet, then:
#   sudo ln -s /etc/nginx/sites-available/meck-bet /etc/nginx/sites-enabled/
#   sudo nginx -t && sudo systemctl reload nginx

server {{
    listen 80;
    server_name {domain};

    # Redirect HTTP → HTTPS (uncomment after certbot setup)
    # return 301 https://$host$request_uri;

    location / {{
        proxy_pass         http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }}
}}

# HTTPS block (after: sudo certbot --nginx -d {domain})
# server {{
#     listen 443 ssl;
#     server_name {domain};
#     ssl_certificate     /etc/letsencrypt/live/{domain}/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
#     location / {{
#         proxy_pass http://127.0.0.1:{port};
#         proxy_http_version 1.1;
#         proxy_set_header Host $host;
#         proxy_set_header X-Real-IP $remote_addr;
#         proxy_set_header X-Forwarded-Proto https;
#         proxy_read_timeout 120s;
#     }}
# }}
"""
    elif mode == "subpath":
        # Strip trailing slash for nginx location match
        loc = base_path.rstrip("/") or "/"
        conf = f"""\
# Meck-Bet nginx config — subpath mode
# The app is accessible at https://{domain}{loc}/
# Place in /etc/nginx/sites-available/meck-bet (or add to your existing server block)

# Add this location block inside your existing server {{ }} for {domain}:
#
#   location {loc}/ {{
#       proxy_pass         http://127.0.0.1:{port}/;
#       proxy_http_version 1.1;
#       proxy_set_header   Host              $host;
#       proxy_set_header   X-Real-IP         $remote_addr;
#       proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
#       proxy_set_header   X-Forwarded-Proto $scheme;
#       proxy_read_timeout 120s;
#   }}
#
# Note: trailing slash on proxy_pass strips the prefix automatically.

# Standalone server block if you don't have an existing one:
server {{
    listen 80;
    server_name {domain};

    location {loc}/ {{
        proxy_pass         http://127.0.0.1:{port}/;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }}
}}
"""
    else:
        # Direct mode — no nginx needed, but provide a sample anyway
        conf = f"""\
# Meck-Bet — direct mode (no nginx required)
# App is accessible directly at http://YOUR_SERVER_IP:{port}
#
# If you want to add nginx later as a TLS terminator, use:
#
# server {{
#     listen 443 ssl;
#     server_name your-domain.com;
#     ssl_certificate     /path/to/cert.pem;
#     ssl_certificate_key /path/to/key.pem;
#     location / {{
#         proxy_pass http://127.0.0.1:{port};
#         proxy_http_version 1.1;
#         proxy_set_header Host $host;
#         proxy_set_header X-Real-IP $remote_addr;
#         proxy_read_timeout 120s;
#     }}
# }}
"""

    out_file.write_text(conf)
    ok(f"nginx config  → {out_file}")


# ── DB init ────────────────────────────────────────────────────────────────────

def init_database():
    section("Database")
    venv_py = BACKEND_DIR / ".venv" / "bin" / "python3"
    if not venv_py.exists():
        warn("venv not found — skipping DB init (install.sh will handle it).")
        return
    info("Initializing SQLite database …")
    result = subprocess.run(
        [str(venv_py), "-c",
         "import asyncio, sys; sys.path.insert(0, '.'); "
         "from models.database import init_db; asyncio.run(init_db()); print('OK')"],
        capture_output=True, text=True, cwd=str(BACKEND_DIR)
    )
    if result.returncode == 0:
        ok("Database ready  (meck_bet.db)")
    else:
        warn(f"DB init warning: {result.stderr[:200]}")


# ── Rebuild frontend if base_path changed ─────────────────────────────────────

def rebuild_frontend(base_path: str):
    """If not subpath '/', the frontend must be rebuilt with the correct base."""
    if base_path in ("/", ""):
        return
    node = FRONTEND_DIR / "node_modules"
    if not node.exists():
        warn("node_modules not installed — skipping frontend rebuild (install.sh will build).")
        return
    info(f"Rebuilding frontend with base path '{base_path}' …")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(FRONTEND_DIR),
        capture_output=True, text=True
    )
    if result.returncode == 0:
        ok("Frontend rebuilt.")
    else:
        warn(f"Build warning: {result.stderr[-300:]}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print()
    print(bold(cyan("╔══════════════════════════════════════════════════╗")))
    print(bold(cyan("║       🏀  MECK-BET  SETUP WIZARD                ║")))
    print(bold(cyan("╚══════════════════════════════════════════════════╝")))
    print()
    print(f"  Config will be saved to: {dim(str(ENV_FILE))}")
    print("  Press Enter to accept the default shown in [brackets].")

    api_key      = collect_api_key()
    port         = collect_port()
    access       = collect_access_mode(port)
    bankroll     = collect_bankroll()
    daily_picks  = collect_daily_picks()
    kelly        = collect_kelly()
    min_ev       = collect_min_ev()
    poll_interval = collect_poll_interval()

    # ── Summary ───────────────────────────────────────────────────────────────
    section("Summary")
    hr()
    print(f"  {'API Key':<22} {green('✓ set') if api_key != 'YOUR_ODDS_API_KEY' else yellow('demo mode')}")
    print(f"  {'Port':<22} {port}")
    print(f"  {'Public URL':<22} {access['public_url']}")
    print(f"  {'Access mode':<22} {access['mode']}")
    if access['base_path'] != '/':
        print(f"  {'Base path':<22} {access['base_path']}")
    print(f"  {'Bankroll':<22} €{bankroll:.2f}")
    print(f"  {'Daily picks':<22} {daily_picks}")
    print(f"  {'Kelly fraction':<22} {kelly}×")
    print(f"  {'Min EV':<22} {min_ev*100:.1f}%")
    print(f"  {'Poll interval':<22} {poll_interval} min")
    hr()

    print()
    if not ask_yn("Save and apply this configuration?", default=True):
        print("  Setup cancelled.")
        sys.exit(0)

    cfg = {
        "api_key":      api_key,
        "port":         port,
        "public_url":   access["public_url"],
        "mode":         access["mode"],
        "base_path":    access["base_path"],
        "bankroll":     bankroll,
        "daily_picks":  daily_picks,
        "kelly":        kelly,
        "min_ev":       min_ev,
        "poll_interval": poll_interval,
    }

    write_env(cfg)
    write_frontend_env(access["base_path"])
    write_nginx_config(cfg)
    rebuild_frontend(access["base_path"])
    init_database()

    # ── Done ──────────────────────────────────────────────────────────────────
    print()
    print(bold(green("╔══════════════════════════════════════════════════╗")))
    print(bold(green("║              Setup complete! 🎉                  ║")))
    print(bold(green("╚══════════════════════════════════════════════════╝")))
    print()

    if access["mode"] != "direct":
        print(f"  {bold('nginx config saved to:')} nginx-meck-bet.conf")
        print(f"  Copy it to /etc/nginx/sites-available/meck-bet")
        print(f"  and run: {cyan('sudo nginx -t && sudo systemctl reload nginx')}")
        print()

    print(f"  {bold('Start the app:')}")
    print(f"    {cyan('make start')}   — background (port {port})")
    print(f"    {cyan('make dev')}     — foreground with live reload")
    print()
    print(f"  {bold('Dashboard:')}  {access['public_url']}")
    print(f"  {bold('API docs:')}   {access['public_url'].rstrip('/')}/api/docs")
    print()


if __name__ == "__main__":
    main()
