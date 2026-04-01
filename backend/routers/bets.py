"""Bets router - value bets, arbitrage, and user bet logging."""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update

from models.database import get_session, ValueBet, ArbitrageOpportunity, BetRecord
from core.ev_engine import calculate_kelly, calculate_clv, calculate_roi

router = APIRouter(prefix="/api/bets", tags=["bets"])


# ─── Value Bets ─────────────────────────────────────────────────────────────

@router.get("/value")
async def list_value_bets(
    min_ev: float = Query(0, description="Minimum EV% filter"),
    sport: Optional[str] = Query(None),
    bookmaker: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List active value bets, sorted by EV descending."""
    q = select(ValueBet).where(ValueBet.is_active == True)
    if min_ev > 0:
        q = q.where(ValueBet.ev_percent >= min_ev)
    if sport:
        q = q.where(ValueBet.sport_key == sport)
    if bookmaker:
        q = q.where(ValueBet.bookmaker == bookmaker)
    q = q.order_by(desc(ValueBet.ev_percent)).limit(limit)

    bets = (await session.execute(q)).scalars().all()
    return [_serialize_vb(b) for b in bets]


@router.get("/value/{bet_id}")
async def get_value_bet(bet_id: int, session: AsyncSession = Depends(get_session)):
    bet = await session.get(ValueBet, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    return _serialize_vb(bet)


def _serialize_vb(b: ValueBet) -> dict:
    return {
        "id": b.id,
        "event_id": b.event_id,
        "sport_key": b.sport_key,
        "match": f"{b.home_team} vs {b.away_team}",
        "home_team": b.home_team,
        "away_team": b.away_team,
        "commence_time": b.commence_time.isoformat() if b.commence_time else None,
        "market": b.market,
        "outcome": b.outcome_name,
        "bookmaker": b.bookmaker,
        "odds": b.odds,
        "true_prob": b.true_prob,
        "implied_prob": b.implied_prob,
        "ev_percent": b.ev_percent,
        "kelly_fraction": b.kelly_fraction,
        "sharp_reference": b.sharp_reference,
        "detected_at": b.detected_at.isoformat() if b.detected_at else None,
        "is_active": b.is_active,
    }


# ─── Arbitrage ───────────────────────────────────────────────────────────────

@router.get("/arbitrage")
async def list_arbitrage(
    min_profit: float = Query(0),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List active arbitrage opportunities, sorted by profit% descending."""
    q = (
        select(ArbitrageOpportunity)
        .where(ArbitrageOpportunity.is_active == True)
        .where(ArbitrageOpportunity.profit_percent >= min_profit)
        .order_by(desc(ArbitrageOpportunity.profit_percent))
        .limit(limit)
    )
    arbs = (await session.execute(q)).scalars().all()
    return [_serialize_arb(a) for a in arbs]


def _serialize_arb(a: ArbitrageOpportunity) -> dict:
    return {
        "id": a.id,
        "event_id": a.event_id,
        "sport_key": a.sport_key,
        "match": f"{a.home_team} vs {a.away_team}",
        "home_team": a.home_team,
        "away_team": a.away_team,
        "commence_time": a.commence_time.isoformat() if a.commence_time else None,
        "market": a.market,
        "profit_percent": a.profit_percent,
        "legs": a.legs,
        "detected_at": a.detected_at.isoformat() if a.detected_at else None,
        "is_active": a.is_active,
    }


# ─── Kelly Calculator ────────────────────────────────────────────────────────

class KellyRequest(BaseModel):
    true_prob: float = Field(..., ge=0.01, le=0.99)
    decimal_odds: float = Field(..., ge=1.01)
    bankroll: float = Field(..., ge=1)
    kelly_fraction: float = Field(0.25, ge=0.01, le=1.0)


@router.post("/kelly")
async def calculate_kelly_endpoint(req: KellyRequest):
    """Calculate Kelly bet size for given parameters."""
    kelly_f = calculate_kelly(req.true_prob, req.decimal_odds, req.kelly_fraction)
    stake = kelly_f * req.bankroll
    ev = req.true_prob * req.decimal_odds - 1.0

    return {
        "kelly_fraction": round(kelly_f, 6),
        "recommended_stake": round(stake, 2),
        "ev_percent": round(ev * 100, 3),
        "expected_profit": round(stake * ev, 2),
        "breakeven_prob": round(1.0 / req.decimal_odds, 4),
        "edge": round((req.true_prob - 1.0 / req.decimal_odds) * 100, 3),
    }


# ─── Bet Tracker ─────────────────────────────────────────────────────────────

class LogBetRequest(BaseModel):
    event_id: str
    sport_key: str
    home_team: str
    away_team: str
    commence_time: Optional[str] = None
    market: str
    outcome_name: str
    bookmaker: str
    odds_taken: float
    stake: float
    ev_percent_at_bet: Optional[float] = None
    notes: Optional[str] = None


class SettleBetRequest(BaseModel):
    result: str  # "won", "lost", "void"
    closing_odds: Optional[float] = None


@router.post("/log", status_code=201)
async def log_bet(req: LogBetRequest, session: AsyncSession = Depends(get_session)):
    """Log a bet placed by the user for tracking."""
    commence = None
    if req.commence_time:
        try:
            commence = datetime.fromisoformat(req.commence_time.replace("Z", "+00:00"))
        except Exception:
            pass

    bet = BetRecord(
        event_id=req.event_id,
        sport_key=req.sport_key,
        home_team=req.home_team,
        away_team=req.away_team,
        commence_time=commence,
        market=req.market,
        outcome_name=req.outcome_name,
        bookmaker=req.bookmaker,
        odds_taken=req.odds_taken,
        stake=req.stake,
        ev_percent_at_bet=req.ev_percent_at_bet,
        result="pending",
        notes=req.notes,
    )
    session.add(bet)
    await session.commit()
    await session.refresh(bet)
    return {"id": bet.id, "message": "Bet logged successfully"}


@router.patch("/log/{bet_id}/settle")
async def settle_bet(
    bet_id: int,
    req: SettleBetRequest,
    session: AsyncSession = Depends(get_session),
):
    """Settle a bet: record result and profit/loss."""
    bet = await session.get(BetRecord, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")

    if req.result not in ("won", "lost", "void"):
        raise HTTPException(status_code=400, detail="result must be 'won', 'lost', or 'void'")

    bet.result = req.result
    if req.closing_odds:
        bet.closing_odds = req.closing_odds

    if req.result == "won":
        bet.profit_loss = round(bet.stake * (bet.odds_taken - 1), 2)
    elif req.result == "lost":
        bet.profit_loss = -bet.stake
    else:
        bet.profit_loss = 0

    await session.commit()
    clv = None
    if req.closing_odds and req.closing_odds > 0:
        clv = round(calculate_clv(bet.odds_taken, req.closing_odds), 3)

    return {
        "id": bet_id,
        "result": req.result,
        "profit_loss": bet.profit_loss,
        "clv_percent": clv,
    }


@router.get("/log")
async def list_bets(
    limit: int = Query(100, le=500),
    result: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List all logged bets."""
    q = select(BetRecord).order_by(desc(BetRecord.placed_at)).limit(limit)
    if result:
        q = q.where(BetRecord.result == result)
    bets = (await session.execute(q)).scalars().all()
    return [
        {
            "id": b.id,
            "match": f"{b.home_team} vs {b.away_team}",
            "sport_key": b.sport_key,
            "market": b.market,
            "outcome": b.outcome_name,
            "bookmaker": b.bookmaker,
            "odds_taken": b.odds_taken,
            "stake": b.stake,
            "ev_percent_at_bet": b.ev_percent_at_bet,
            "closing_odds": b.closing_odds,
            "result": b.result,
            "profit_loss": b.profit_loss,
            "placed_at": b.placed_at.isoformat() if b.placed_at else None,
            "notes": b.notes,
        }
        for b in bets
    ]


@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_session)):
    """Overall betting statistics and ROI."""
    bets = (await session.execute(select(BetRecord))).scalars().all()
    bet_dicts = [
        {
            "stake": b.stake,
            "profit_loss": b.profit_loss,
            "ev_percent_at_bet": b.ev_percent_at_bet,
            "odds_taken": b.odds_taken,
            "result": b.result,
        }
        for b in bets
    ]
    stats = calculate_roi(bet_dicts)

    # CLV stats
    clv_bets = [
        b for b in bets if b.closing_odds and b.odds_taken
    ]
    avg_clv = None
    if clv_bets:
        clv_values = [calculate_clv(b.odds_taken, b.closing_odds) for b in clv_bets]
        avg_clv = round(sum(clv_values) / len(clv_values), 3)

    return {**stats, "avg_clv_percent": avg_clv}
