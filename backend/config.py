from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── The Odds API ──────────────────────────────────────────────────────────
    ODDS_API_KEY: str = "YOUR_ODDS_API_KEY"
    ODDS_API_BASE: str = "https://api.the-odds-api.com/v4"

    # ── Server ────────────────────────────────────────────────────────────────
    # Bind address — use 127.0.0.1 if nginx proxies, 0.0.0.0 for direct access
    HOST: str = "0.0.0.0"
    # Port — change if 8000 is taken by another service
    PORT: int = 8000
    # Public URL shown in logs and health endpoint (e.g. https://bet.example.com)
    PUBLIC_URL: str = ""

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins.
    # Use "*" to allow all (safe behind nginx with restricted upstream).
    # For direct access without nginx, list your exact URLs:
    #   CORS_ORIGINS=https://bet.example.com,http://192.168.1.10:8080
    CORS_ORIGINS: str = "*"

    # ── Sharp reference books ─────────────────────────────────────────────────
    SHARP_BOOKS: List[str] = ["pinnacle", "betfair_ex_eu", "matchbook"]

    # ── Soft books ────────────────────────────────────────────────────────────
    SOFT_BOOKS: List[str] = [
        "bet365", "unibet", "bwin", "williamhill", "betway",
        "betsson", "nordicbet", "draftkings", "fanduel", "betmgm"
    ]

    # ── Sports to scan ────────────────────────────────────────────────────────
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

    # ── Markets ───────────────────────────────────────────────────────────────
    MARKETS: List[str] = ["h2h", "spreads", "totals"]

    # ── Polling ───────────────────────────────────────────────────────────────
    POLL_INTERVAL_MINUTES: int = 10

    # ── EV Thresholds ─────────────────────────────────────────────────────────
    MIN_EV_THRESHOLD: float = 0.02
    MIN_ARB_THRESHOLD: float = 0.001

    # ── Bankroll & Betting ────────────────────────────────────────────────────
    DEFAULT_BANKROLL: float = 1000.0
    KELLY_FRACTION: float = 0.25

    # ── NBA Daily Simulation ──────────────────────────────────────────────────
    DAILY_PICKS: int = 5
    MIN_MODEL_CONFIDENCE: float = 0.40

    # ── Database ──────────────────────────────────────────────────────────────
    # Default: sqlite file relative to backend/ directory
    DATABASE_URL: str = "sqlite+aiosqlite:///./meck_bet.db"

    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into a list."""
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
