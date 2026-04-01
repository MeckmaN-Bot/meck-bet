"""
Analyzer - Orchestrates fetching, analyzing, and storing opportunities.
Runs periodically via APScheduler and on-demand via API.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from config import settings
from core.ev_engine import (
    Market, Outcome, find_value_bets, find_best_arbitrage,
)
from core.odds_fetcher import odds_client
from models.database import OddsSnapshot, ValueBet, ArbitrageOpportunity

logger = logging.getLogger(__name__)


def _parse_market_from_event(event: dict, bookmaker_key: str, market_key: str) -> Optional[Market]:
    """Extract a Market object from raw API event data for a given bookmaker."""
    for bm in event.get("bookmakers", []):
        if bm["key"] != bookmaker_key:
            continue
        for mkt in bm.get("markets", []):
            if mkt["key"] != market_key:
                continue
            outcomes = [
                Outcome(
                    name=o["name"],
                    decimal_odds=float(o["price"]),
                    point=o.get("point"),
                )
                for o in mkt["outcomes"]
                if float(o["price"]) > 1.0
            ]
            if outcomes:
                return Market(outcomes=outcomes)
    return None


def _best_sharp_market(event: dict, market_key: str) -> tuple[Optional[Market], str]:
    """Try sharp books in priority order; return first available market + book name."""
    for sharp_key in settings.SHARP_BOOKS:
        mkt = _parse_market_from_event(event, sharp_key, market_key)
        if mkt and len(mkt.outcomes) >= 2:
            return mkt, sharp_key
    return None, ""


async def analyze_event(
    event: dict,
    session: AsyncSession,
    market_key: str = "h2h",
) -> dict:
    """
    Full analysis pipeline for a single event:
    1. Store raw odds snapshot
    2. Find value bets vs. sharp reference
    3. Find arbitrage opportunities
    Returns summary of findings.
    """
    event_id = event["id"]
    home = event["home_team"]
    away = event["away_team"]
    sport_key = event["sport_key"]

    try:
        commence = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
    except Exception:
        commence = datetime.now(timezone.utc)

    # ── 1. Store snapshots ──────────────────────────────────────────────
    for bm in event.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt["key"] != market_key:
                continue
            snap = OddsSnapshot(
                event_id=event_id,
                sport_key=sport_key,
                sport_title=event.get("sport_title", sport_key),
                home_team=home,
                away_team=away,
                commence_time=commence,
                market=market_key,
                bookmaker=bm["key"],
                outcomes=mkt["outcomes"],
            )
            session.add(snap)

    # ── 2. Value Bet Detection ──────────────────────────────────────────
    sharp_market, sharp_book = _best_sharp_market(event, market_key)
    value_bets_found = []

    if sharp_market:
        # Build soft book odds map: {bookmaker: {outcome_name: decimal_odds}}
        soft_odds: dict[str, dict[str, float]] = {}
        for bm in event.get("bookmakers", []):
            if bm["key"] in settings.SHARP_BOOKS:
                continue
            for mkt in bm.get("markets", []):
                if mkt["key"] != market_key:
                    continue
                soft_odds[bm["key"]] = {
                    o["name"]: float(o["price"])
                    for o in mkt["outcomes"]
                    if float(o["price"]) > 1.0
                }

        # Mark existing value bets as inactive (stale)
        await session.execute(
            update(ValueBet)
            .where(ValueBet.event_id == event_id, ValueBet.market == market_key)
            .values(is_active=False)
        )

        vb_results = find_value_bets(
            sharp_market=sharp_market,
            soft_book_odds=soft_odds,
            min_ev=settings.MIN_EV_THRESHOLD,
            kelly_fraction=settings.KELLY_FRACTION,
        )

        for vb in vb_results:
            db_vb = ValueBet(
                event_id=event_id,
                sport_key=sport_key,
                home_team=home,
                away_team=away,
                commence_time=commence,
                market=market_key,
                outcome_name=vb.outcome_name,
                bookmaker=vb.bookmaker,
                odds=vb.decimal_odds,
                true_prob=round(vb.true_prob, 6),
                implied_prob=round(vb.implied_prob, 6),
                ev_percent=vb.ev_percent,
                kelly_fraction=vb.kelly_fraction,
                sharp_reference=sharp_book,
                is_active=True,
            )
            session.add(db_vb)
            value_bets_found.append(vb)

    # ── 3. Arbitrage Detection ──────────────────────────────────────────
    all_book_odds: dict[str, dict[str, float]] = {}
    for bm in event.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt["key"] != market_key:
                continue
            all_book_odds[bm["key"]] = {
                o["name"]: float(o["price"])
                for o in mkt["outcomes"]
                if float(o["price"]) > 1.0
            }

    arb_result = find_best_arbitrage(all_book_odds, settings.MIN_ARB_THRESHOLD)
    arb_found = None

    if arb_result:
        # Deactivate old arb for this event
        await session.execute(
            update(ArbitrageOpportunity)
            .where(ArbitrageOpportunity.event_id == event_id, ArbitrageOpportunity.market == market_key)
            .values(is_active=False)
        )
        db_arb = ArbitrageOpportunity(
            event_id=event_id,
            sport_key=sport_key,
            home_team=home,
            away_team=away,
            commence_time=commence,
            market=market_key,
            profit_percent=arb_result.profit_percent,
            legs=[
                {
                    "outcome": leg.outcome_name,
                    "bookmaker": leg.bookmaker,
                    "odds": leg.decimal_odds,
                    "stake_percent": leg.stake_percent,
                }
                for leg in arb_result.legs
            ],
            is_active=True,
        )
        session.add(db_arb)
        arb_found = arb_result

    await session.commit()

    return {
        "event_id": event_id,
        "value_bets": len(value_bets_found),
        "arbitrage": arb_found is not None,
    }


async def run_full_scan(session: AsyncSession) -> dict:
    """
    Full scan across all configured sports and markets.
    Called by the scheduler every POLL_INTERVAL_MINUTES.
    """
    logger.info("Starting full odds scan...")
    total_events = 0
    total_vb = 0
    total_arb = 0

    for sport_key in settings.SPORTS:
        for market in settings.MARKETS:
            try:
                events = await odds_client.get_odds(
                    sport_key=sport_key,
                    markets=market,
                )
                for event in events:
                    result = await analyze_event(event, session, market_key=market)
                    total_events += 1
                    total_vb += result["value_bets"]
                    if result["arbitrage"]:
                        total_arb += 1
            except Exception as e:
                logger.error(f"Error processing {sport_key}/{market}: {e}")

    quota = odds_client.quota_info()
    logger.info(
        f"Scan complete: {total_events} events, {total_vb} value bets, "
        f"{total_arb} arbs. API quota: {quota}"
    )
    return {
        "events_scanned": total_events,
        "value_bets_found": total_vb,
        "arbitrage_found": total_arb,
        "api_quota": quota,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
