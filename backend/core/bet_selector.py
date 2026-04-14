"""
Daily Bet Selector
==================
Picks the best N NBA bets for the day from all available odds.

Pipeline per day:
1. Fetch NBA odds from The Odds API
2. Fetch NBA team stats from balldontlie
3. For each event/outcome:
   a. Devig sharp odds → true probability
   b. Find soft books offering +EV
   c. Build BetFeatures (stats + odds data)
   d. Score with learning model
   e. Apply hard filters (min EV, min model confidence)
4. Sort by composite score, pick top N
5. Distribute bankroll using Kelly criterion (capped at 30% total)
6. Store picks in DB as a DailySimulation
"""

import logging
from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from core.ev_engine import (
    Market, Outcome, devig_multiplicative, calculate_ev, calculate_kelly,
)
from core.nba_fetcher import nba_fetcher
from core.learning_engine import get_model, BetFeatures, MIN_CONFIDENCE
from core.odds_fetcher import odds_client
from models.database import DailySimulation, DailyPick

logger = logging.getLogger(__name__)

NBA_SPORT_KEY = "basketball_nba"
DEFAULT_N_PICKS = 5
MAX_BANKROLL_PERCENT = 0.30   # Never stake more than 30% of bankroll total per day
MIN_EV = 0.015                # 1.5% minimum EV to even consider a bet


def _build_features(
    outcome_name: str,
    home_team: str,
    away_team: str,
    odds: float,
    true_prob: float,
    ev_percent: float,
    team_stats: dict,
) -> BetFeatures:
    """Construct BetFeatures from odds + team stats for the learning model."""
    ht = team_stats.get(home_team, {})
    at = team_stats.get(away_team, {})

    is_home = (outcome_name == home_team)
    pick_stats = ht if is_home else at
    opp_stats = at if is_home else ht

    pick_wp = pick_stats.get("win_pct", 0.5)
    opp_wp = opp_stats.get("win_pct", 0.5)
    pick_form = pick_stats.get("last_5_wins", 2) / 5.0
    opp_form = opp_stats.get("last_5_wins", 2) / 5.0
    pick_rest = pick_stats.get("days_rest", 2)
    opp_rest = opp_stats.get("days_rest", 2)

    # Offensive edge: how well pick team scores vs. how well opponent defends
    pick_scored = pick_stats.get("avg_points_scored", 112.0)
    opp_allowed = opp_stats.get("avg_points_allowed", 112.0)
    opp_scored = opp_stats.get("avg_points_scored", 112.0)
    pick_allowed = pick_stats.get("avg_points_allowed", 112.0)

    # Positive offense_edge → we score more than they allow on average
    offense_edge = pick_scored - opp_allowed
    # Positive defense_edge → they score less than we allow on average (we defend better)
    defense_edge = pick_allowed - opp_scored

    return BetFeatures(
        ev_percent=ev_percent,
        true_prob=true_prob,
        odds=odds,
        pick_team_wp=pick_wp,
        opp_team_wp=opp_wp,
        pick_team_form=pick_form,
        opp_team_form=opp_form,
        rest_advantage=(pick_rest - opp_rest) / 7.0,  # normalized to [-1, 1]
        offense_edge=offense_edge,
        defense_edge=defense_edge,
        is_home_pick=float(is_home),
    )


async def run_daily_picks(
    session: AsyncSession,
    n_picks: int = DEFAULT_N_PICKS,
    bankroll: float = 1000.0,
    sim_date: Optional[str] = None,
) -> dict:
    """
    Main entry point: run the full daily pick pipeline.
    Returns summary dict with simulation info.
    """
    today = sim_date or date.today().isoformat()
    model = get_model()

    # Idempotency: don't run twice for the same date
    existing = await session.scalar(
        select(DailySimulation).where(DailySimulation.sim_date == today)
    )
    if existing:
        logger.info(f"Daily picks already ran for {today} (sim_id={existing.id})")
        return {"status": "already_ran", "simulation_id": existing.id, "date": today}

    logger.info(f"Running daily NBA picks for {today} | n={n_picks} | bankroll={bankroll}")

    # ── 1. Fetch team stats ──────────────────────────────────────────────────
    try:
        team_stats = await nba_fetcher.get_team_stats()
    except Exception as e:
        logger.warning(f"Could not fetch live team stats, using demo defaults: {e}")
        team_stats = nba_fetcher.demo_team_stats()

    # ── 2. Fetch NBA odds (live_only=True: never use demo data for real picks) ─
    events = await odds_client.get_odds(sport_key=NBA_SPORT_KEY, markets="h2h", live_only=True)

    if not events:
        logger.warning("No NBA events returned. Cannot generate picks.")
        return {"status": "no_events", "date": today}

    # ── 3. Score all candidate bets ──────────────────────────────────────────
    candidates = []
    now = datetime.now(timezone.utc)

    for event in events:
        home = event["home_team"]
        away = event["away_team"]
        event_id = event["id"]

        try:
            commence = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
        except Exception:
            commence = now

        # Skip games that have already started
        if commence <= now:
            continue

        # ── Find the sharpest available reference market ──
        sharp_market: Optional[Market] = None
        sharp_book = ""

        for book_key in settings.SHARP_BOOKS:
            for bm in event.get("bookmakers", []):
                if bm["key"] != book_key:
                    continue
                for mkt in bm.get("markets", []):
                    if mkt["key"] != "h2h":
                        continue
                    valid_outcomes = [
                        o for o in mkt["outcomes"] if float(o["price"]) > 1.01
                    ]
                    if len(valid_outcomes) >= 2:
                        sharp_market = Market(outcomes=[
                            Outcome(name=o["name"], decimal_odds=float(o["price"]))
                            for o in valid_outcomes
                        ])
                        sharp_book = book_key
                        break
                if sharp_market:
                    break

        # Fallback: use market average as pseudo-sharp if no real sharp book present
        if not sharp_market:
            outcome_prices: dict[str, list[float]] = {}
            for bm in event.get("bookmakers", []):
                for mkt in bm.get("markets", []):
                    if mkt["key"] != "h2h":
                        continue
                    for o in mkt["outcomes"]:
                        price = float(o["price"])
                        if price > 1.01:
                            outcome_prices.setdefault(o["name"], []).append(price)

            if len(outcome_prices) == 2:
                # Use median odds per outcome (more robust than mean against outliers)
                avg_outcomes = []
                for name, prices in outcome_prices.items():
                    prices.sort()
                    mid = len(prices) // 2
                    median = prices[mid] if len(prices) % 2 else (prices[mid-1] + prices[mid]) / 2
                    avg_outcomes.append(Outcome(name=name, decimal_odds=median))
                sharp_market = Market(outcomes=avg_outcomes)
                sharp_book = "market_consensus"

        if not sharp_market:
            continue

        # ── Devig sharp market to get true probabilities ──
        true_probs = devig_multiplicative(sharp_market)

        # Sanity check: true probs should sum to ~1.0
        if abs(sum(true_probs.values()) - 1.0) > 0.01:
            logger.warning(f"Devigging anomaly for {home} vs {away}: {true_probs}")
            continue

        # ── Check each soft book for value vs. sharp reference ──
        for bm in event.get("bookmakers", []):
            # Skip sharp books — we use them as reference, not as targets
            if bm["key"] in settings.SHARP_BOOKS:
                continue
            # Also skip market_consensus reference (all books already averaged)
            for mkt in bm.get("markets", []):
                if mkt["key"] != "h2h":
                    continue

                for o in mkt["outcomes"]:
                    outcome_name = o["name"]
                    odds = float(o["price"])

                    # Basic sanity: odds must be valid and outcome must be in our reference
                    if odds <= 1.01 or outcome_name not in true_probs:
                        continue

                    tp = true_probs[outcome_name]

                    # EV = p_true * odds - 1  (profit per unit staked)
                    ev = calculate_ev(tp, odds)

                    if ev < MIN_EV:
                        continue

                    # Build feature vector for the learning model
                    features = _build_features(
                        outcome_name, home, away, odds, tp, ev * 100, team_stats
                    )

                    model_prob = model.predict(features)
                    composite_score = model.composite_score(features)

                    # Hard filter: model must have at least minimum confidence
                    if model_prob < MIN_CONFIDENCE:
                        continue

                    kelly = calculate_kelly(tp, odds, settings.KELLY_FRACTION)

                    # Skip if Kelly says don't bet (can happen with very small edge)
                    if kelly <= 0:
                        continue

                    candidates.append({
                        "event_id": event_id,
                        "home_team": home,
                        "away_team": away,
                        "commence_time": commence,
                        "outcome_name": outcome_name,
                        "bookmaker": bm["key"],
                        "odds": round(odds, 4),
                        "true_prob": round(tp, 6),
                        "ev_percent": round(ev * 100, 4),
                        "kelly_fraction": round(kelly, 6),
                        "model_win_prob": round(model_prob, 4),
                        "score": round(composite_score, 6),
                        "features": features.to_dict(),
                        "sharp_book": sharp_book,
                    })

    if not candidates:
        logger.info(f"No candidates passed EV/confidence filters for {today}.")
        return {"status": "no_candidates", "date": today}

    # ── 4. Deduplicate: one best pick per game ────────────────────────────────
    # Keep the highest-scored candidate per event
    best_per_event: dict[str, dict] = {}
    for c in candidates:
        eid = c["event_id"]
        if eid not in best_per_event or c["score"] > best_per_event[eid]["score"]:
            best_per_event[eid] = c

    # Sort by score descending, take top N
    top_picks = sorted(best_per_event.values(), key=lambda x: x["score"], reverse=True)[:n_picks]

    # ── 5. Bankroll allocation with safety cap ────────────────────────────────
    total_kelly = sum(p["kelly_fraction"] for p in top_picks)

    # If total Kelly exceeds our daily risk budget, scale all stakes down proportionally
    if total_kelly > MAX_BANKROLL_PERCENT:
        scale = MAX_BANKROLL_PERCENT / total_kelly
    else:
        scale = 1.0

    total_staked = 0.0
    for pick in top_picks:
        raw_stake = pick["kelly_fraction"] * scale * bankroll
        pick["stake"] = max(1.0, round(raw_stake, 2))
        total_staked += pick["stake"]

    # ── 6. Persist to DB ─────────────────────────────────────────────────────
    sim = DailySimulation(
        sim_date=today,
        bankroll_start=bankroll,
        n_picks=len(top_picks),
        n_pending=len(top_picks),
        total_staked=round(total_staked, 2),
        model_version=model.version,
    )
    session.add(sim)
    await session.flush()  # Get sim.id before adding picks

    for pick in top_picks:
        db_pick = DailyPick(
            simulation_id=sim.id,
            sim_date=today,
            event_id=pick["event_id"],
            home_team=pick["home_team"],
            away_team=pick["away_team"],
            commence_time=pick["commence_time"],
            market="h2h",
            outcome_name=pick["outcome_name"],
            bookmaker=pick["bookmaker"],
            odds=pick["odds"],
            true_prob=pick["true_prob"],
            ev_percent=pick["ev_percent"],
            score=pick["score"],
            kelly_fraction=pick["kelly_fraction"],
            stake=pick["stake"],
            features=pick["features"],
            model_win_prob=pick["model_win_prob"],
        )
        session.add(db_pick)

    await session.commit()

    logger.info(
        f"Daily picks done: {len(top_picks)} bets | staked €{total_staked:.2f} | "
        f"model v{model.version} | sim_id={sim.id}"
    )

    return {
        "status": "success",
        "date": today,
        "simulation_id": sim.id,
        "n_picks": len(top_picks),
        "total_staked": round(total_staked, 2),
        "picks": [
            {
                "match": f"{p['home_team']} vs {p['away_team']}",
                "pick": p["outcome_name"],
                "bookmaker": p["bookmaker"],
                "odds": p["odds"],
                "ev_percent": p["ev_percent"],
                "model_prob": p["model_win_prob"],
                "stake": p["stake"],
            }
            for p in top_picks
        ],
    }
