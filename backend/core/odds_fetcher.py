"""
Odds Fetcher — Multi-Source Client
====================================
Priority order:
  1. Action Network  (free, no API key, real odds for NBA)
  2. The Odds API    (optional key in .env — higher accuracy)
  3. Demo data       (fallback when both are unavailable)

Action Network API is an undocumented but publicly accessible API used by
actionnetwork.com for their odds comparison pages. No authentication required.
"""

import httpx
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# ── Action Network book ID → normalized key + display name ───────────────────
AN_BOOKS: dict[int, tuple[str, str]] = {
    3:   ("pinnacle",    "Pinnacle"),
    15:  ("draftkings",  "DraftKings"),
    16:  ("fanduel",     "FanDuel"),
    20:  ("betmgm",      "BetMGM"),
    283: ("caesars",     "Caesars"),
    750: ("espnbet",     "ESPN BET"),
    11:  ("betrivers",   "BetRivers"),
    19:  ("pointsbet",   "PointsBet"),
    2:   ("bet365",      "Bet365"),
    268: ("wynnbet",     "WynnBet"),
    18:  ("barstool",    "Barstool"),
    123: ("unibet",      "Unibet"),
}

AN_BASE = "https://api.actionnetwork.com/web/v1"


def _american_to_decimal(american: int | float | None) -> Optional[float]:
    """Convert American odds to decimal. Returns None for invalid values."""
    if american is None:
        return None
    try:
        am = float(american)
    except (TypeError, ValueError):
        return None
    if am == 0:
        return None
    if am > 0:
        return round(am / 100 + 1.0, 4)
    return round(100 / abs(am) + 1.0, 4)


def _normalize_an_game(game: dict) -> Optional[dict]:
    """
    Convert one Action Network game object to The Odds API event format.
    Returns None if the game has no usable odds.
    """
    home = game.get("home_team", {})
    away = game.get("away_team", {})
    home_name = home.get("full_name") or home.get("short_name") or "Home"
    away_name = away.get("full_name") or away.get("short_name") or "Away"

    start_raw = game.get("start_time") or game.get("scheduled")
    try:
        commence = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
        commence_iso = commence.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        commence_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    bookmakers: list[dict] = []
    for odds_entry in game.get("odds", []):
        book_id = odds_entry.get("book_id")
        if book_id not in AN_BOOKS:
            continue
        book_key, book_title = AN_BOOKS[book_id]

        # ── moneyline (h2h) ──────────────────────────────────────────
        ml_away = _american_to_decimal(odds_entry.get("ml_away"))
        ml_home = _american_to_decimal(odds_entry.get("ml_home"))
        h2h_outcomes = []
        if ml_away and ml_away > 1.0:
            h2h_outcomes.append({"name": away_name, "price": ml_away})
        if ml_home and ml_home > 1.0:
            h2h_outcomes.append({"name": home_name, "price": ml_home})

        # ── spread ───────────────────────────────────────────────────
        spread_away_line = _american_to_decimal(odds_entry.get("spread_away_line"))
        spread_home_line = _american_to_decimal(odds_entry.get("spread_home_line"))
        spread_away_pts  = odds_entry.get("spread_away")
        spread_home_pts  = odds_entry.get("spread_home")
        spread_outcomes = []
        if spread_away_line and spread_away_line > 1.0 and spread_away_pts is not None:
            spread_outcomes.append({"name": away_name, "price": spread_away_line,
                                    "point": float(spread_away_pts)})
        if spread_home_line and spread_home_line > 1.0 and spread_home_pts is not None:
            spread_outcomes.append({"name": home_name, "price": spread_home_line,
                                    "point": float(spread_home_pts)})

        # ── totals ───────────────────────────────────────────────────
        over_line  = _american_to_decimal(odds_entry.get("over_line"))
        under_line = _american_to_decimal(odds_entry.get("under_line"))
        total_pts  = odds_entry.get("over") or odds_entry.get("total")
        totals_outcomes = []
        if over_line and over_line > 1.0 and total_pts is not None:
            totals_outcomes.append({"name": "Over",  "price": over_line,  "point": float(total_pts)})
        if under_line and under_line > 1.0 and total_pts is not None:
            totals_outcomes.append({"name": "Under", "price": under_line, "point": float(total_pts)})

        markets = []
        if h2h_outcomes:
            markets.append({"key": "h2h",     "outcomes": h2h_outcomes})
        if spread_outcomes:
            markets.append({"key": "spreads", "outcomes": spread_outcomes})
        if totals_outcomes:
            markets.append({"key": "totals",  "outcomes": totals_outcomes})

        if markets:
            bookmakers.append({"key": book_key, "title": book_title, "markets": markets})

    if not bookmakers:
        return None

    return {
        "id":           f"an_{game['id']}",
        "sport_key":    "basketball_nba",
        "sport_title":  "NBA",
        "commence_time": commence_iso,
        "home_team":    home_name,
        "away_team":    away_name,
        "bookmakers":   bookmakers,
        "_source":      "action_network",
    }


class ActionNetworkClient:
    """Fetches NBA odds from api.actionnetwork.com — no API key required."""

    async def get_nba_odds(self, days_ahead: int = 3) -> list[dict]:
        """
        Returns upcoming NBA games (today + days_ahead) in normalized format.
        Fetches multiple date ranges to cover all scheduled games.
        """
        games: list[dict] = []
        seen_ids: set = set()

        dates_to_fetch = []
        today = datetime.now(timezone.utc).date()
        for i in range(days_ahead + 1):
            dates_to_fetch.append((today + timedelta(days=i)).strftime("%Y%m%d"))

        async with httpx.AsyncClient(
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (compatible; sports-analyzer/1.0)"},
            follow_redirects=True,
        ) as client:
            for date_str in dates_to_fetch:
                try:
                    resp = await client.get(
                        f"{AN_BASE}/games",
                        params={"sport": "nba", "league": "nba", "dates": date_str},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for raw_game in data.get("games", []):
                            gid = raw_game.get("id")
                            if gid in seen_ids:
                                continue
                            seen_ids.add(gid)
                            # Skip finished games
                            status = (raw_game.get("status") or "").lower()
                            if status in ("final", "complete", "finished"):
                                continue
                            normalized = _normalize_an_game(raw_game)
                            if normalized:
                                games.append(normalized)
                    else:
                        logger.warning(f"Action Network returned {resp.status_code} for {date_str}")
                except Exception as e:
                    logger.warning(f"Action Network fetch failed for {date_str}: {e}")

        logger.info(f"Action Network: fetched {len(games)} upcoming NBA games")
        return games


class OddsAPIClient:
    """Optional The Odds API client — used only when ODDS_API_KEY is configured."""

    def __init__(self):
        self.base_url = settings.ODDS_API_BASE
        self.api_key  = settings.ODDS_API_KEY
        self._requests_used      = 0
        self._requests_remaining = 500

    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key not in ("", "YOUR_ODDS_API_KEY")

    async def get_odds(
        self,
        sport_key: str,
        markets:    str = "h2h",
        regions:    str = "eu,uk,us,au",
        odds_format: str = "decimal",
    ) -> list[dict]:
        params = {
            "apiKey":    self.api_key,
            "regions":   regions,
            "markets":   markets,
            "oddsFormat": odds_format,
            "dateFormat": "iso",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/sports/{sport_key}/odds",
                    params=params,
                )
                resp.raise_for_status()
                self._update_quota(resp)
                return resp.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    logger.error("Invalid Odds API key")
                elif e.response.status_code == 422:
                    logger.warning(f"Sport {sport_key} not available in this region")
                else:
                    logger.error(f"Odds API HTTP error for {sport_key}: {e}")
                return []
            except Exception as e:
                logger.error(f"Odds API error for {sport_key}: {e}")
                return []

    def _update_quota(self, response: httpx.Response):
        used      = response.headers.get("x-requests-used")
        remaining = response.headers.get("x-requests-remaining")
        if used:      self._requests_used      = int(used)
        if remaining: self._requests_remaining = int(remaining)

    def quota_info(self) -> dict:
        return {
            "requests_used":      self._requests_used,
            "requests_remaining": self._requests_remaining,
        }


class UnifiedOddsClient:
    """
    Unified client: tries Action Network first (free), falls back to
    The Odds API if a key is configured, then to demo data.
    """

    def __init__(self):
        self._an  = ActionNetworkClient()
        self._oa  = OddsAPIClient()
        self._requests_used      = 0
        self._requests_remaining = 9999   # AN has no limit

    async def get_odds(
        self,
        sport_key: str = "basketball_nba",
        markets:   str = "h2h",
    ) -> list[dict]:
        """
        Returns events in The Odds API normalized format regardless of source.
        """
        # ── 1. Action Network (always try first for NBA) ──────────────────────
        if sport_key == "basketball_nba":
            try:
                events = await self._an.get_nba_odds(days_ahead=3)
                if events:
                    # Filter to requested market if not h2h
                    if markets != "h2h":
                        events = [
                            _filter_market(e, markets) for e in events
                        ]
                        events = [e for e in events if e]
                    return events
                logger.warning("Action Network returned no NBA games — trying fallback")
            except Exception as e:
                logger.warning(f"Action Network unavailable: {e}")

        # ── 2. The Odds API (optional, uses quota) ────────────────────────────
        if self._oa.is_configured():
            logger.info("Falling back to The Odds API")
            events = await self._oa.get_odds(sport_key=sport_key, markets=markets)
            if events:
                return events

        # ── 3. Demo data ──────────────────────────────────────────────────────
        logger.warning("All live sources failed — using demo data")
        return _demo_nba_data()

    def quota_info(self) -> dict:
        if self._oa.is_configured():
            return self._oa.quota_info()
        return {"source": "action_network", "requests_used": "unlimited", "requests_remaining": "unlimited"}


def _filter_market(event: dict, market_key: str) -> Optional[dict]:
    """Remove bookmakers that don't have the requested market; return None if none left."""
    filtered_bms = []
    for bm in event.get("bookmakers", []):
        mkts = [m for m in bm.get("markets", []) if m["key"] == market_key]
        if mkts:
            filtered_bms.append({**bm, "markets": mkts})
    if not filtered_bms:
        return None
    return {**event, "bookmakers": filtered_bms}


def _demo_nba_data() -> list[dict]:
    """Realistic NBA demo data with deliberate odds errors for UI testing."""
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [
        {
            "id": "demo_nba_001",
            "sport_key": "basketball_nba",
            "sport_title": "NBA",
            "commence_time": tomorrow,
            "home_team": "Boston Celtics",
            "away_team": "Miami Heat",
            "bookmakers": [
                {"key": "pinnacle", "title": "Pinnacle", "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Boston Celtics", "price": 1.65},
                    {"name": "Miami Heat",     "price": 2.35},
                ]}]},
                {"key": "draftkings", "title": "DraftKings", "markets": [{"key": "h2h", "outcomes": [
                    # Slight over-price on Heat → +EV
                    {"name": "Boston Celtics", "price": 1.62},
                    {"name": "Miami Heat",     "price": 2.55},
                ]}]},
                {"key": "fanduel", "title": "FanDuel", "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Boston Celtics", "price": 1.64},
                    {"name": "Miami Heat",     "price": 2.38},
                ]}]},
            ],
        },
        {
            "id": "demo_nba_002",
            "sport_key": "basketball_nba",
            "sport_title": "NBA",
            "commence_time": tomorrow,
            "home_team": "Los Angeles Lakers",
            "away_team": "Golden State Warriors",
            "bookmakers": [
                {"key": "pinnacle", "title": "Pinnacle", "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Los Angeles Lakers",    "price": 2.05},
                    {"name": "Golden State Warriors", "price": 1.85},
                ]}]},
                {"key": "betmgm", "title": "BetMGM", "markets": [{"key": "h2h", "outcomes": [
                    # Large mispricing on Lakers → strong +EV
                    {"name": "Los Angeles Lakers",    "price": 2.30},
                    {"name": "Golden State Warriors", "price": 1.78},
                ]}]},
                {"key": "caesars", "title": "Caesars", "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Los Angeles Lakers",    "price": 2.10},
                    {"name": "Golden State Warriors", "price": 1.83},
                ]}]},
            ],
        },
        {
            "id": "demo_nba_003",
            "sport_key": "basketball_nba",
            "sport_title": "NBA",
            "commence_time": tomorrow,
            "home_team": "Denver Nuggets",
            "away_team": "Phoenix Suns",
            "bookmakers": [
                {"key": "pinnacle", "title": "Pinnacle", "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Denver Nuggets", "price": 1.55},
                    {"name": "Phoenix Suns",   "price": 2.60},
                ]}]},
                {"key": "fanduel", "title": "FanDuel", "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Denver Nuggets", "price": 1.53},
                    {"name": "Phoenix Suns",   "price": 2.80},
                ]}]},
                {"key": "draftkings", "title": "DraftKings", "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Denver Nuggets", "price": 1.56},
                    {"name": "Phoenix Suns",   "price": 2.62},
                ]}]},
            ],
        },
    ]


# Singleton
odds_client = UnifiedOddsClient()
