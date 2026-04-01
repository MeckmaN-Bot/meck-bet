"""
Odds Fetcher - The Odds API Client
===================================
Fetches live odds from https://the-odds-api.com
Free tier: 500 requests/month. Each sport+market combo = 1 request.

Docs: https://the-odds-api.com/liveapi/guides/v4/
"""

import httpx
import logging
from datetime import datetime, timezone
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


class OddsAPIClient:
    def __init__(self):
        self.base_url = settings.ODDS_API_BASE
        self.api_key = settings.ODDS_API_KEY
        self._requests_used = 0
        self._requests_remaining = 500

    async def get_sports(self) -> list[dict]:
        """Get all available sports."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/sports",
                params={"apiKey": self.api_key},
            )
            resp.raise_for_status()
            self._update_quota(resp)
            return resp.json()

    async def get_odds(
        self,
        sport_key: str,
        markets: str = "h2h",
        regions: str = "eu,uk,us,au",
        odds_format: str = "decimal",
        bookmakers: Optional[str] = None,
    ) -> list[dict]:
        """
        Fetch odds for a sport.
        Returns list of events with bookmaker odds.
        Each request uses ~1 API credit per market per region combo.
        """
        if self.api_key == "YOUR_ODDS_API_KEY":
            logger.warning("No Odds API key set - returning demo data")
            return self._demo_data(sport_key, markets)

        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": "iso",
        }
        if bookmakers:
            params["bookmakers"] = bookmakers

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
                    logger.error("Invalid Odds API key. Set ODDS_API_KEY in .env")
                elif e.response.status_code == 422:
                    logger.warning(f"Sport {sport_key} not available in this region")
                else:
                    logger.error(f"HTTP error fetching {sport_key}: {e}")
                return []
            except Exception as e:
                logger.error(f"Error fetching odds for {sport_key}: {e}")
                return []

    def _update_quota(self, response: httpx.Response):
        used = response.headers.get("x-requests-used")
        remaining = response.headers.get("x-requests-remaining")
        if used:
            self._requests_used = int(used)
        if remaining:
            self._requests_remaining = int(remaining)

    def quota_info(self) -> dict:
        return {
            "requests_used": self._requests_used,
            "requests_remaining": self._requests_remaining,
        }

    def _demo_data(self, sport_key: str, markets: str) -> list[dict]:
        """
        Realistic demo data for development without an API key.
        Includes deliberate odds errors to demo value bet detection.
        """
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "demo_event_001",
                "sport_key": sport_key,
                "sport_title": "Soccer - Bundesliga",
                "commence_time": "2026-04-05T14:00:00Z",
                "home_team": "Bayern München",
                "away_team": "Borussia Dortmund",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "title": "Pinnacle",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Bayern München", "price": 1.65},
                                    {"name": "Borussia Dortmund", "price": 5.10},
                                    {"name": "Draw", "price": 4.00},
                                ],
                            }
                        ],
                    },
                    {
                        "key": "bet365",
                        "title": "Bet365",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    # Bet365 has Bayern slightly low, Dortmund high → VALUE on Dortmund
                                    {"name": "Bayern München", "price": 1.60},
                                    {"name": "Borussia Dortmund", "price": 5.50},
                                    {"name": "Draw", "price": 3.80},
                                ],
                            }
                        ],
                    },
                    {
                        "key": "bwin",
                        "title": "Bwin",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Bayern München", "price": 1.63},
                                    {"name": "Borussia Dortmund", "price": 5.00},
                                    {"name": "Draw", "price": 3.90},
                                ],
                            }
                        ],
                    },
                    {
                        "key": "williamhill",
                        "title": "William Hill",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Bayern München", "price": 1.62},
                                    {"name": "Borussia Dortmund", "price": 5.00},
                                    # Draw is mispriced here → ARB potential
                                    {"name": "Draw", "price": 4.50},
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "id": "demo_event_002",
                "sport_key": sport_key,
                "sport_title": "Basketball - NBA",
                "commence_time": "2026-04-06T01:00:00Z",
                "home_team": "Los Angeles Lakers",
                "away_team": "Golden State Warriors",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "title": "Pinnacle",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Los Angeles Lakers", "price": 2.05},
                                    {"name": "Golden State Warriors", "price": 1.85},
                                ],
                            }
                        ],
                    },
                    {
                        "key": "draftkings",
                        "title": "DraftKings",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    # Significant odds error on Lakers → +EV
                                    {"name": "Los Angeles Lakers", "price": 2.25},
                                    {"name": "Golden State Warriors", "price": 1.80},
                                ],
                            }
                        ],
                    },
                    {
                        "key": "fanduel",
                        "title": "FanDuel",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Los Angeles Lakers", "price": 2.10},
                                    {"name": "Golden State Warriors", "price": 1.82},
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "id": "demo_event_003",
                "sport_key": sport_key,
                "sport_title": "Soccer - Premier League",
                "commence_time": "2026-04-05T16:30:00Z",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "title": "Pinnacle",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Arsenal", "price": 1.95},
                                    {"name": "Chelsea", "price": 3.80},
                                    {"name": "Draw", "price": 3.60},
                                ],
                            }
                        ],
                    },
                    {
                        "key": "unibet",
                        "title": "Unibet",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Arsenal", "price": 1.90},
                                    # Massive error on Draw → value
                                    {"name": "Chelsea", "price": 3.75},
                                    {"name": "Draw", "price": 4.10},
                                ],
                            }
                        ],
                    },
                    {
                        "key": "betway",
                        "title": "Betway",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Arsenal", "price": 1.92},
                                    {"name": "Chelsea", "price": 3.80},
                                    {"name": "Draw", "price": 3.55},
                                ],
                            }
                        ],
                    },
                ],
            },
        ]


# Singleton client
odds_client = OddsAPIClient()
