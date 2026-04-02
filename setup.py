#!/usr/bin/env python3
"""
Meck-Bet Interactive Setup Wizard
===================================
Guides the user through all required configuration steps.
Runs from the repo root. Creates backend/.env

Usage:
    python3 setup.py
    # or called by install.sh automatically
"""

import os
import sys
import time
import asyncio
import textwrap
from pathlib import Path

# ── Minimal color helpers (no third-party deps) ───────────────────────────────
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"

def green(t):  return _c("32", t)
def yellow(t): return _c("33", t)
def red(t):    return _c("31", t)
def cyan(t):   return _c("36", t)
def bold(t):   return _c("1",  t)
def dim(t):    return _c("2",  t)

def ok(msg):   print(f"  {green('✓')}  {msg}")
def info(msg): print(f"  {cyan('→')}  {msg}")
def warn(msg): print(f"  {yellow('⚠')}  {msg}")
def err(msg):  print(f"  {red('✗')}  {msg}")
def ask(prompt, default=None):
    suffix = f" [{dim(default)}]" if default else ""
    return input(f"  {bold('?')}  {prompt}{suffix}: ").strip() or default or ""

def ask_yn(prompt, default=True):
    suffix = "[Y/n]" if default else "[y/N]"
    ans = input(f"  {bold('?')}  {prompt} {dim(suffix)}: ").strip().lower()
    if not ans:
        return default
    return ans.startswith("y")

def section(title):
    print(f"\n{bold(cyan('▸ ' + title))}")

def hr():
    print(f"  {dim('─' * 52)}")


REPO_ROOT = Path(__file__).parent
BACKEND_DIR = REPO_ROOT / "backend"
ENV_FILE = BACKEND_DIR / ".env"
ENV_EXAMPLE = BACKEND_DIR / ".env.example"


# ── API Key tester ────────────────────────────────────────────────────────────

async def test_odds_api_key(key: str) -> tuple[bool, str]:
    """Try a lightweight call to The Odds API to validate the key."""
    try:
        import httpx
    except ImportError:
        return True, "httpx not available for testing (will validate at runtime)"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.the-odds-api.com/v4/sports",
                params={"apiKey": key},
            )
            if resp.status_code == 200:
                data = resp.json()
                n = len(data)
                remaining = resp.headers.get("x-requests-remaining", "?")
                return True, f"{n} sports available | {remaining} API requests remaining"
            elif resp.status_code == 401:
                return False, "Invalid API key (401 Unauthorized)"
            else:
                return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        return False, f"Network error: {e}"


# ── Individual sections ───────────────────────────────────────────────────────

def collect_api_key() -> str:
    section("The Odds API Key")
    print(textwrap.dedent(f"""
  The Odds API aggregates live odds from 40+ bookmakers including
  Pinnacle (used as sharp reference for EV calculation).

  {bold('Free tier')}: 500 requests/month — enough for daily scans.
  {bold('Sign up')}: https://the-odds-api.com (takes ~1 minute)
    """).rstrip())

    while True:
        key = ask("Paste your API key (or press Enter to use demo mode)")
        if not key:
            warn("No key entered — running in DEMO mode with simulated data")
            warn("You can add the key later by editing backend/.env")
            return "YOUR_ODDS_API_KEY"

        print()
        info("Testing API key...")
        ok_flag, msg = asyncio.run(test_odds_api_key(key))
        if ok_flag:
            ok(f"API key valid! {msg}")
            return key
        else:
            err(f"API key test failed: {msg}")
            if not ask_yn("Try a different key?", default=True):
                warn("Proceeding with untested key")
                return key


def collect_bankroll() -> float:
    section("Simulated Bankroll")
    print(textwrap.dedent("""
  The bankroll is used for Kelly criterion stake sizing in the NBA simulator.
  This is a SIMULATION — no real money is involved.
    """).rstrip())
    while True:
        val = ask("Starting bankroll (EUR/USD)", default="1000")
        try:
            f = float(val.replace(",", "."))
            if f < 10:
                warn("Bankroll must be at least 10")
                continue
            ok(f"Bankroll set to {f:.2f}")
            return f
        except ValueError:
            err("Please enter a valid number (e.g. 1000 or 2500.50)")


def collect_daily_picks() -> int:
    section("Daily Pick Count")
    print(textwrap.dedent("""
  How many NBA bets should the bot select per day?
  More picks = more diversification but smaller individual stakes.
  Recommended: 3-7 picks per day.
    """).rstrip())
    while True:
        val = ask("Picks per day", default="5")
        try:
            n = int(val)
            if not 1 <= n <= 20:
                warn("Please choose between 1 and 20")
                continue
            ok(f"Bot will select {n} pick(s) per day")
            return n
        except ValueError:
            err("Please enter a whole number")


def collect_kelly() -> float:
    section("Kelly Fraction")
    options = {
        "1": ("0.10", "Tenth Kelly  — Very conservative (10% of full Kelly)"),
        "2": ("0.25", "Quarter Kelly — Conservative, recommended ✓"),
        "3": ("0.50", "Half Kelly    — Moderate"),
        "4": ("1.00", "Full Kelly    — Aggressive, high variance"),
    }
    print()
    for k, (val, desc) in options.items():
        print(f"    {bold(k)}) {desc}")
    print()
    choice = ask("Choose (1-4)", default="2")
    val, desc = options.get(choice, options["2"])
    ok(f"Kelly fraction set to {val} ({desc.split('—')[0].strip()})")
    return float(val)


def collect_min_ev() -> float:
    section("Minimum EV Threshold")
    print(textwrap.dedent("""
  Only bets with EV% above this threshold will be shown/picked.
  Higher threshold = fewer but higher-quality bets.
    """).rstrip())
    while True:
        val = ask("Minimum EV% (e.g. 2 for 2%)", default="2")
        try:
            f = float(val.replace("%", "").replace(",", "."))
            if not 0.1 <= f <= 20:
                warn("Please enter a value between 0.1 and 20")
                continue
            ok(f"Minimum EV set to {f:.1f}%")
            return f / 100.0
        except ValueError:
            err("Please enter a number like 2 or 3.5")


def collect_poll_interval() -> int:
    section("Odds Polling Interval")
    print(textwrap.dedent(f"""
  How often should the system refresh odds? More frequent = more accurate
  but uses more API requests from your monthly quota.

  {dim('Note: 500 requests/month free. At 5min intervals ~288 req/day if always on.')}
  {dim('Recommended for server: 10-15 min to conserve quota.')}
    """).rstrip())
    while True:
        val = ask("Interval in minutes", default="10")
        try:
            n = int(val)
            if not 1 <= n <= 60:
                warn("Please choose between 1 and 60 minutes")
                continue
            ok(f"Odds will refresh every {n} minutes")
            return n
        except ValueError:
            err("Please enter a whole number")


# ── Write .env ────────────────────────────────────────────────────────────────

def write_env(config: dict):
    content = f"""\
# Meck-Bet Configuration
# Generated by setup.py — edit manually to change settings

# The Odds API key (https://the-odds-api.com)
ODDS_API_KEY={config['api_key']}

# Simulated bankroll
DEFAULT_BANKROLL={config['bankroll']}

# NBA picks per day
DAILY_PICKS={config['daily_picks']}

# Kelly fraction (0.25 = Quarter Kelly, recommended)
KELLY_FRACTION={config['kelly']}

# Minimum EV% to show a bet
MIN_EV_THRESHOLD={config['min_ev']}

# Odds polling interval (minutes)
POLL_INTERVAL_MINUTES={config['poll_interval']}

# Minimum model confidence to include a pick (keep at 0.40)
MIN_MODEL_CONFIDENCE=0.40
"""
    ENV_FILE.write_text(content)
    ok(f"Configuration saved to {ENV_FILE}")


# ── DB init + demo data ───────────────────────────────────────────────────────

def init_database():
    section("Database initialization")
    info("Initializing SQLite database...")

    # We need to run inside the backend venv
    venv_python = BACKEND_DIR / ".venv" / "bin" / "python3"
    if not venv_python.exists():
        warn("Virtual environment not found — skipping DB init (install.sh handles this)")
        return

    import subprocess
    result = subprocess.run(
        [str(venv_python), "-c", """
import asyncio, sys
sys.path.insert(0, '.')
from models.database import init_db
asyncio.run(init_db())
print("OK")
"""],
        capture_output=True, text=True, cwd=str(BACKEND_DIR)
    )
    if result.returncode == 0:
        ok("Database initialized (meck_bet.db)")
    else:
        warn(f"DB init had an issue: {result.stderr[:200]}")


# ── Main wizard ───────────────────────────────────────────────────────────────

def main():
    # Header
    print()
    print(bold(cyan("╔══════════════════════════════════════════════════╗")))
    print(bold(cyan("║        🏀  MECK-BET  SETUP WIZARD               ║")))
    print(bold(cyan("╚══════════════════════════════════════════════════╝")))
    print()
    print("  This wizard sets up Meck-Bet for your server.")
    print(f"  Configuration will be saved to: {dim(str(ENV_FILE))}")
    print()
    print("  Press Enter to accept defaults shown in brackets.")
    print()

    # Collect all config
    api_key       = collect_api_key()
    bankroll      = collect_bankroll()
    daily_picks   = collect_daily_picks()
    kelly         = collect_kelly()
    min_ev        = collect_min_ev()
    poll_interval = collect_poll_interval()

    # Summary
    section("Configuration Summary")
    hr()
    print(f"  {'API Key':<25} {green('✓ set') if api_key != 'YOUR_ODDS_API_KEY' else yellow('demo mode')}")
    print(f"  {'Bankroll':<25} €{bankroll:.2f}")
    print(f"  {'Daily Picks':<25} {daily_picks} per day")
    print(f"  {'Kelly Fraction':<25} {kelly} ({int(kelly*100)}% of full Kelly)")
    print(f"  {'Minimum EV':<25} {min_ev*100:.1f}%")
    print(f"  {'Poll Interval':<25} every {poll_interval} minutes")
    hr()

    print()
    if not ask_yn("Save this configuration?", default=True):
        print("  Setup cancelled.")
        sys.exit(0)

    config = {
        "api_key": api_key,
        "bankroll": bankroll,
        "daily_picks": daily_picks,
        "kelly": kelly,
        "min_ev": min_ev,
        "poll_interval": poll_interval,
    }

    write_env(config)
    init_database()

    # Done
    print()
    print(bold(green("╔══════════════════════════════════════════════════╗")))
    print(bold(green("║              Setup complete! 🎉                  ║")))
    print(bold(green("╚══════════════════════════════════════════════════╝")))
    print()
    print("  Next steps:")
    print(f"    {cyan('make start')}         — Start Meck-Bet in background")
    print(f"    {cyan('make dev')}           — Start in foreground with live logs")
    print(f"    {cyan('make logs')}          — View logs")
    print()
    print(f"  Dashboard: {bold('http://localhost:8000')}")
    print(f"  API docs:  {bold('http://localhost:8000/api/docs')}")
    print()


if __name__ == "__main__":
    main()
