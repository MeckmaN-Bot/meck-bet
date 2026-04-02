"""
NBA Data Fetcher
================
Fetches NBA-specific data from two sources:

1. The Odds API  → Live bookmaker odds for NBA (basketball_nba)
2. balldontlie   → Free NBA stats API (no auth needed for basic endpoints)
   Docs: https://www.balldontlie.io/api/v1/

Team name normalization: The Odds API and balldontlie use different names,
so we maintain a canonical mapping.
"""

import httpx
import logging
from datetime import datetime, date, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

BALLDONTLIE_BASE = "https://www.balldontlie.io/api/v1"

# Map The Odds API team names → balldontlie full names
# Both use the full city+name format, but small differences exist.
TEAM_NAME_MAP: dict[str, str] = {
    "Atlanta Hawks": "Atlanta Hawks",
    "Boston Celtics": "Boston Celtics",
    "Brooklyn Nets": "Brooklyn Nets",
    "Charlotte Hornets": "Charlotte Hornets",
    "Chicago Bulls": "Chicago Bulls",
    "Cleveland Cavaliers": "Cleveland Cavaliers",
    "Dallas Mavericks": "Dallas Mavericks",
    "Denver Nuggets": "Denver Nuggets",
    "Detroit Pistons": "Detroit Pistons",
    "Golden State Warriors": "Golden State Warriors",
    "Houston Rockets": "Houston Rockets",
    "Indiana Pacers": "Indiana Pacers",
    "LA Clippers": "LA Clippers",
    "Los Angeles Clippers": "LA Clippers",
    "Los Angeles Lakers": "Los Angeles Lakers",
    "Memphis Grizzlies": "Memphis Grizzlies",
    "Miami Heat": "Miami Heat",
    "Milwaukee Bucks": "Milwaukee Bucks",
    "Minnesota Timberwolves": "Minnesota Timberwolves",
    "New Orleans Pelicans": "New Orleans Pelicans",
    "New York Knicks": "New York Knicks",
    "Oklahoma City Thunder": "Oklahoma City Thunder",
    "Orlando Magic": "Orlando Magic",
    "Philadelphia 76ers": "Philadelphia 76ers",
    "Phoenix Suns": "Phoenix Suns",
    "Portland Trail Blazers": "Portland Trail Blazers",
    "Sacramento Kings": "Sacramento Kings",
    "San Antonio Spurs": "San Antonio Spurs",
    "Toronto Raptors": "Toronto Raptors",
    "Utah Jazz": "Utah Jazz",
    "Washington Wizards": "Washington Wizards",
}

# balldontlie team IDs (stable, looked up once)
TEAM_IDS: dict[str, int] = {
    "Atlanta Hawks": 1, "Boston Celtics": 2, "Brooklyn Nets": 3,
    "Charlotte Hornets": 4, "Chicago Bulls": 5, "Cleveland Cavaliers": 6,
    "Dallas Mavericks": 7, "Denver Nuggets": 8, "Detroit Pistons": 9,
    "Golden State Warriors": 10, "Houston Rockets": 11, "Indiana Pacers": 12,
    "LA Clippers": 13, "Los Angeles Lakers": 14, "Memphis Grizzlies": 15,
    "Miami Heat": 16, "Milwaukee Bucks": 17, "Minnesota Timberwolves": 18,
    "New Orleans Pelicans": 19, "New York Knicks": 20, "Oklahoma City Thunder": 21,
    "Orlando Magic": 22, "Philadelphia 76ers": 23, "Phoenix Suns": 24,
    "Portland Trail Blazers": 25, "Sacramento Kings": 26, "San Antonio Spurs": 27,
    "Toronto Raptors": 28, "Utah Jazz": 29, "Washington Wizards": 30,
}


class NBADataFetcher:
    """
    Fetches and caches NBA team stats, recent game results, and schedules.
    Uses balldontlie (free, no API key) for historical data.
    """

    def __init__(self):
        self._team_stats_cache: dict[str, dict] = {}
        self._cache_ts: Optional[datetime] = None
        self._cache_ttl_hours = 6

    def _cache_valid(self) -> bool:
        if not self._cache_ts:
            return False
        return (datetime.now(timezone.utc) - self._cache_ts).total_seconds() < self._cache_ttl_hours * 3600

    async def get_team_stats(self, force_refresh: bool = False) -> dict[str, dict]:
        """
        Returns dict {team_name: stats_dict} for all 30 NBA teams.
        Cached for 6 hours to avoid hammering the free API.
        """
        if not force_refresh and self._cache_valid():
            return self._team_stats_cache

        stats = {}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                # Fetch current season standings / averages
                # balldontlie v1 season_averages needs player IDs, not teams.
                # For team-level data we use the games endpoint to compute stats.
                season = self._current_season()

                # Get all teams
                resp = await client.get(f"{BALLDONTLIE_BASE}/teams", params={"per_page": 30})
                if resp.status_code == 200:
                    teams_data = resp.json().get("data", [])
                    for team in teams_data:
                        name = self._normalize_team_name(team["full_name"])
                        stats[name] = self._default_stats(name, team)

                # Fetch recent games to compute form (last 14 days)
                recent_cutoff = (date.today() - timedelta(days=14)).isoformat()
                page = 1
                all_games = []
                while page <= 5:  # max 5 pages = 500 games
                    resp = await client.get(
                        f"{BALLDONTLIE_BASE}/games",
                        params={
                            "seasons[]": season,
                            "start_date": recent_cutoff,
                            "per_page": 100,
                            "page": page,
                        },
                    )
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    games = data.get("data", [])
                    if not games:
                        break
                    all_games.extend([g for g in games if g.get("status") == "Final"])
                    meta = data.get("meta", {})
                    if page >= meta.get("total_pages", 1):
                        break
                    page += 1

                self._enrich_stats_from_games(stats, all_games)

        except Exception as e:
            logger.warning(f"balldontlie API error: {e}. Using default stats.")
            # Return defaults for all teams so system still works
            for name in TEAM_NAME_MAP.values():
                if name not in stats:
                    stats[name] = self._default_stats(name, {})

        self._team_stats_cache = stats
        self._cache_ts = datetime.now(timezone.utc)
        return stats

    def _enrich_stats_from_games(self, stats: dict[str, dict], games: list[dict]):
        """
        Parse recent finished games and update team stats:
        - wins, losses, win_pct
        - last_5 form
        - avg points scored/allowed
        - days rest
        """
        # Track per-team game history (sorted by date)
        team_games: dict[str, list[dict]] = {}

        for g in games:
            home = self._normalize_team_name(g.get("home_team", {}).get("full_name", ""))
            away = self._normalize_team_name(g.get("visitor_team", {}).get("full_name", ""))
            home_score = g.get("home_team_score", 0) or 0
            away_score = g.get("visitor_team_score", 0) or 0
            game_date = g.get("date", "")[:10]

            if not home or not away:
                continue

            for team, opp, ts, os, is_home in [
                (home, away, home_score, away_score, True),
                (away, home, away_score, home_score, False),
            ]:
                if team not in team_games:
                    team_games[team] = []
                team_games[team].append({
                    "date": game_date,
                    "scored": ts,
                    "allowed": os,
                    "won": ts > os,
                    "is_home": is_home,
                })

        today = date.today()
        for team, game_list in team_games.items():
            if team not in stats:
                stats[team] = self._default_stats(team, {})

            game_list.sort(key=lambda x: x["date"])
            wins = sum(1 for g in game_list if g["won"])
            losses = len(game_list) - wins
            home_games = [g for g in game_list if g["is_home"]]
            away_games = [g for g in game_list if not g["is_home"]]

            last5 = game_list[-5:]
            avg_scored = sum(g["scored"] for g in game_list) / len(game_list) if game_list else 110.0
            avg_allowed = sum(g["allowed"] for g in game_list) / len(game_list) if game_list else 110.0

            # Days since last game
            if game_list:
                last_date = date.fromisoformat(game_list[-1]["date"])
                days_rest = (today - last_date).days
            else:
                days_rest = 3

            stats[team].update({
                "wins": wins,
                "losses": losses,
                "win_pct": wins / len(game_list) if game_list else 0.5,
                "home_wins": sum(1 for g in home_games if g["won"]),
                "home_losses": sum(1 for g in home_games if not g["won"]),
                "away_wins": sum(1 for g in away_games if g["won"]),
                "away_losses": sum(1 for g in away_games if not g["won"]),
                "last_5_wins": sum(1 for g in last5 if g["won"]),
                "avg_points_scored": round(avg_scored, 1),
                "avg_points_allowed": round(avg_allowed, 1),
                "days_rest": max(0, min(days_rest, 7)),
                "n_games": len(game_list),
            })

    async def get_game_result(self, home_team: str, away_team: str, game_date: str) -> Optional[dict]:
        """
        Fetch final score for a specific game.
        Returns {home_score, away_score, winner} or None if not finished.
        """
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{BALLDONTLIE_BASE}/games",
                    params={
                        "start_date": game_date,
                        "end_date": game_date,
                        "per_page": 30,
                    },
                )
                if resp.status_code != 200:
                    return None

                games = resp.json().get("data", [])
                norm_home = self._normalize_team_name(home_team)
                norm_away = self._normalize_team_name(away_team)

                for g in games:
                    g_home = self._normalize_team_name(g.get("home_team", {}).get("full_name", ""))
                    g_away = self._normalize_team_name(g.get("visitor_team", {}).get("full_name", ""))

                    if (g_home == norm_home and g_away == norm_away) or \
                       (g_home == norm_away and g_away == norm_home):
                        if g.get("status") != "Final":
                            return None
                        hs = g.get("home_team_score", 0) or 0
                        as_ = g.get("visitor_team_score", 0) or 0
                        # Map back to original orientation
                        if g_home == norm_home:
                            return {"home_score": hs, "away_score": as_, "winner": norm_home if hs > as_ else norm_away}
                        else:
                            return {"home_score": as_, "away_score": hs, "winner": norm_home if as_ > hs else norm_away}
        except Exception as e:
            logger.warning(f"Error fetching game result: {e}")
        return None

    def _default_stats(self, name: str, team_data: dict) -> dict:
        return {
            "team_name": name,
            "abbreviation": team_data.get("abbreviation", name[:3].upper()),
            "wins": 20, "losses": 20, "win_pct": 0.5,
            "home_wins": 12, "home_losses": 10,
            "away_wins": 8, "away_losses": 14,
            "last_5_wins": 2,
            "avg_points_scored": 112.0,
            "avg_points_allowed": 112.0,
            "days_rest": 2,
            "n_games": 40,
        }

    def _normalize_team_name(self, name: str) -> str:
        return TEAM_NAME_MAP.get(name, name)

    def _current_season(self) -> int:
        today = date.today()
        # NBA season starts in October; season year = year it ends (e.g. 2025-26 → 2025)
        return today.year if today.month >= 10 else today.year - 1

    # ── Demo fallback ──────────────────────────────────────────────────────────

    def demo_team_stats(self) -> dict[str, dict]:
        """Realistic demo stats for all 30 teams when API is unavailable."""
        import random
        rng = random.Random(42)
        demo = {}
        teams_config = [
            ("Boston Celtics", 0.72, 3), ("Oklahoma City Thunder", 0.70, 4),
            ("Cleveland Cavaliers", 0.68, 2), ("Minnesota Timberwolves", 0.60, 3),
            ("New York Knicks", 0.58, 2), ("Denver Nuggets", 0.58, 1),
            ("Milwaukee Bucks", 0.55, 2), ("Los Angeles Lakers", 0.54, 3),
            ("Golden State Warriors", 0.50, 2), ("Miami Heat", 0.50, 1),
            ("Dallas Mavericks", 0.53, 2), ("Phoenix Suns", 0.48, 3),
            ("Indiana Pacers", 0.52, 1), ("Sacramento Kings", 0.49, 2),
            ("Chicago Bulls", 0.43, 1), ("Toronto Raptors", 0.35, 2),
            ("Atlanta Hawks", 0.40, 3), ("Orlando Magic", 0.55, 2),
            ("Philadelphia 76ers", 0.36, 4), ("Memphis Grizzlies", 0.38, 1),
            ("Brooklyn Nets", 0.30, 2), ("Detroit Pistons", 0.32, 3),
            ("Charlotte Hornets", 0.28, 1), ("Washington Wizards", 0.25, 2),
            ("Houston Rockets", 0.46, 1), ("Utah Jazz", 0.35, 3),
            ("Portland Trail Blazers", 0.32, 2), ("San Antonio Spurs", 0.29, 1),
            ("New Orleans Pelicans", 0.45, 2), ("LA Clippers", 0.51, 2),
        ]
        g = 60
        for name, wp, rest in teams_config:
            w = round(g * wp)
            l = g - w
            demo[name] = {
                "team_name": name,
                "abbreviation": name.split()[-1][:3].upper(),
                "wins": w, "losses": l,
                "win_pct": wp,
                "home_wins": round(w * 0.6), "home_losses": round(l * 0.4),
                "away_wins": round(w * 0.4), "away_losses": round(l * 0.6),
                "last_5_wins": rng.randint(1, 5),
                "avg_points_scored": round(rng.uniform(105, 122), 1),
                "avg_points_allowed": round(rng.uniform(105, 122), 1),
                "days_rest": rest,
                "n_games": g,
            }
        return demo


nba_fetcher = NBADataFetcher()
