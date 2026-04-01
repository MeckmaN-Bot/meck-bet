from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # The Odds API - get free key at https://the-odds-api.com
    ODDS_API_KEY: str = "YOUR_ODDS_API_KEY"
    ODDS_API_BASE: str = "https://api.the-odds-api.com/v4"

    # Which bookmakers to use as "sharp" reference (no-vig truth)
    # Pinnacle is the gold standard for sharp lines
    SHARP_BOOKS: List[str] = ["pinnacle", "betfair_ex_eu", "matchbook"]

    # Soft books to find value against
    SOFT_BOOKS: List[str] = [
        "bet365", "unibet", "bwin", "williamhill", "betway",
        "betsson", "nordicbet", "draftkings", "fanduel", "betmgm"
    ]

    # Sports to track (The Odds API sport keys)
    SPORTS: List[str] = [
        "soccer_germany_bundesliga",
        "soccer_england_premier_league",
        "soccer_spain_la_liga",
        "soccer_italy_serie_a",
        "soccer_france_ligue_one",
        "soccer_uefa_champs_league",
        "basketball_nba",
        "americanfootball_nfl",
        "tennis_atp_french_open",
        "icehockey_nhl",
    ]

    # Markets to analyze
    MARKETS: List[str] = ["h2h", "spreads", "totals"]

    # How often to poll odds (minutes)
    POLL_INTERVAL_MINUTES: int = 5

    # Minimum EV threshold to show a bet (e.g., 0.03 = 3% edge)
    MIN_EV_THRESHOLD: float = 0.02

    # Minimum EV for arbitrage (0 = break-even, we want > 0)
    MIN_ARB_THRESHOLD: float = 0.001

    # Default bankroll for Kelly calculations
    DEFAULT_BANKROLL: float = 1000.0

    # Kelly fraction (0.25 = Quarter Kelly, conservative)
    KELLY_FRACTION: float = 0.25

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./meck_bet.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
