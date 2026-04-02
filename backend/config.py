from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── The Odds API ──────────────────────────────────────────────────────────
    # Get a free key at https://the-odds-api.com (500 requests/month free)
    ODDS_API_KEY: str = "YOUR_ODDS_API_KEY"
    ODDS_API_BASE: str = "https://api.the-odds-api.com/v4"

    # ── Sharp reference books (used as ground truth for true probabilities) ──
    # Pinnacle is the gold standard — very low margin, efficient market
    SHARP_BOOKS: List[str] = ["pinnacle", "betfair_ex_eu", "matchbook"]

    # ── Soft books to compare against for value detection ─────────────────────
    SOFT_BOOKS: List[str] = [
        "bet365", "unibet", "bwin", "williamhill", "betway",
        "betsson", "nordicbet", "draftkings", "fanduel", "betmgm"
    ]

    # ── Sports to scan (The Odds API sport keys) ───────────────────────────────
    SPORTS: List[str] = [
        "basketball_nba",
        "soccer_germany_bundesliga",
        "soccer_england_premier_league",
        "soccer_spain_la_liga",
        "soccer_italy_serie_a",
        "soccer_france_ligue_one",
        "soccer_uefa_champs_league",
        "americanfootball_nfl",
        "icehockey_nhl",
    ]

    # ── Markets to scan ────────────────────────────────────────────────────────
    MARKETS: List[str] = ["h2h", "spreads", "totals"]

    # ── Polling / Scheduler ───────────────────────────────────────────────────
    # How often to refresh odds (minutes). Lower = more API usage.
    POLL_INTERVAL_MINUTES: int = 5

    # ── EV Thresholds ─────────────────────────────────────────────────────────
    # Minimum EV% to show a value bet (0.02 = 2% edge required)
    MIN_EV_THRESHOLD: float = 0.02
    # Minimum guaranteed profit for arbitrage detection
    MIN_ARB_THRESHOLD: float = 0.001

    # ── Bankroll & Betting ────────────────────────────────────────────────────
    # Simulated bankroll in EUR/USD (used for Kelly stake sizing)
    DEFAULT_BANKROLL: float = 1000.0
    # Kelly fraction: 0.25 = Quarter Kelly (safe), 0.5 = Half Kelly
    KELLY_FRACTION: float = 0.25

    # ── NBA Daily Simulation ──────────────────────────────────────────────────
    # Number of bets to pick per day
    DAILY_PICKS: int = 5
    # Minimum model P(win) for a pick to be included (filters low-confidence bets)
    MIN_MODEL_CONFIDENCE: float = 0.40

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./meck_bet.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
