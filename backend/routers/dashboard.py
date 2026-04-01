"""Dashboard router - summary statistics for the main overview."""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from models.database import get_session, ValueBet, ArbitrageOpportunity, BetRecord
from core.odds_fetcher import odds_client

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_summary(session: AsyncSession = Depends(get_session)):
    """Main dashboard summary: active value bets, arbs, bankroll stats."""
    # Active value bets
    vb_count = await session.scalar(
        select(func.count()).where(ValueBet.is_active == True)
    )

    # Active arbitrage
    arb_count = await session.scalar(
        select(func.count()).where(ArbitrageOpportunity.is_active == True)
    )

    # Best current EV bet
    best_vb = await session.scalar(
        select(ValueBet)
        .where(ValueBet.is_active == True)
        .order_by(desc(ValueBet.ev_percent))
    )

    # Best current arb
    best_arb = await session.scalar(
        select(ArbitrageOpportunity)
        .where(ArbitrageOpportunity.is_active == True)
        .order_by(desc(ArbitrageOpportunity.profit_percent))
    )

    # Bankroll stats from bet records
    total_bets = await session.scalar(select(func.count()).select_from(BetRecord))
    settled_bets = (
        await session.execute(
            select(BetRecord).where(BetRecord.result.in_(["won", "lost"]))
        )
    ).scalars().all()

    total_pl = sum(b.profit_loss or 0 for b in settled_bets)
    total_staked = sum(b.stake for b in settled_bets)
    roi = (total_pl / total_staked * 100) if total_staked > 0 else 0
    wins = sum(1 for b in settled_bets if b.result == "won")
    win_rate = (wins / len(settled_bets) * 100) if settled_bets else 0

    return {
        "active_value_bets": vb_count or 0,
        "active_arbitrage": arb_count or 0,
        "best_ev": {
            "ev_percent": best_vb.ev_percent if best_vb else None,
            "bookmaker": best_vb.bookmaker if best_vb else None,
            "match": f"{best_vb.home_team} vs {best_vb.away_team}" if best_vb else None,
            "outcome": best_vb.outcome_name if best_vb else None,
            "odds": best_vb.odds if best_vb else None,
        },
        "best_arb": {
            "profit_percent": best_arb.profit_percent if best_arb else None,
            "match": f"{best_arb.home_team} vs {best_arb.away_team}" if best_arb else None,
        },
        "bankroll": {
            "total_bets": total_bets or 0,
            "settled_bets": len(settled_bets),
            "total_pl": round(total_pl, 2),
            "total_staked": round(total_staked, 2),
            "roi_percent": round(roi, 2),
            "win_rate_percent": round(win_rate, 2),
        },
        "api_quota": odds_client.quota_info(),
    }


@router.get("/ev-history")
async def get_ev_history(days: int = 7, session: AsyncSession = Depends(get_session)):
    """EV distribution over time for charting."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    bets = (
        await session.execute(
            select(ValueBet)
            .where(ValueBet.detected_at >= since)
            .order_by(ValueBet.detected_at)
        )
    ).scalars().all()

    return [
        {
            "detected_at": b.detected_at.isoformat(),
            "ev_percent": b.ev_percent,
            "bookmaker": b.bookmaker,
            "sport_key": b.sport_key,
            "match": f"{b.home_team} vs {b.away_team}",
        }
        for b in bets
    ]
