"""NBA router — daily simulations, performance tracking, learning model."""

from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from models.database import (
    get_session, DailySimulation, DailyPick,
    ModelWeights, ModelPerformance
)
from core.bet_selector import run_daily_picks
from core.result_settler import settle_pending_picks, load_model_from_db
from core.learning_engine import get_model
from config import settings

router = APIRouter(prefix="/api/nba", tags=["nba"])


# ── Daily Simulation ─────────────────────────────────────────────────────────

@router.post("/picks/run")
async def trigger_daily_picks(
    background_tasks: BackgroundTasks,
    n_picks: int = Query(default=None),
    bankroll: float = Query(default=None),
    sim_date: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Manually trigger today's NBA pick generation."""
    n = n_picks or settings.DAILY_PICKS
    bl = bankroll or settings.DEFAULT_BANKROLL

    async def _run():
        await run_daily_picks(session, n_picks=n, bankroll=bl, sim_date=sim_date)

    background_tasks.add_task(_run)
    return {"status": "started", "n_picks": n, "bankroll": bl}


@router.post("/settle")
async def trigger_settlement(
    background_tasks: BackgroundTasks,
    settle_date: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Manually trigger result settlement for a date (default: yesterday)."""
    async def _run():
        await settle_pending_picks(session, settle_date=settle_date)

    background_tasks.add_task(_run)
    return {"status": "started", "date": settle_date or (date.today() - timedelta(days=1)).isoformat()}


# ── Simulation History ────────────────────────────────────────────────────────

@router.get("/simulations")
async def list_simulations(
    limit: int = Query(30, le=365),
    session: AsyncSession = Depends(get_session),
):
    """All daily simulations, newest first."""
    sims = (
        await session.execute(
            select(DailySimulation).order_by(desc(DailySimulation.sim_date)).limit(limit)
        )
    ).scalars().all()
    return [_serialize_sim(s) for s in sims]


@router.get("/simulations/{sim_id}")
async def get_simulation(sim_id: int, session: AsyncSession = Depends(get_session)):
    """Single simulation with all picks."""
    sim = await session.get(DailySimulation, sim_id)
    if not sim:
        from fastapi import HTTPException
        raise HTTPException(404, "Simulation not found")

    picks = (
        await session.execute(
            select(DailyPick).where(DailyPick.simulation_id == sim_id)
        )
    ).scalars().all()

    return {
        **_serialize_sim(sim),
        "picks": [_serialize_pick(p) for p in picks],
    }


@router.get("/picks/today")
async def get_todays_picks(session: AsyncSession = Depends(get_session)):
    """Today's pick list."""
    today = date.today().isoformat()
    picks = (
        await session.execute(
            select(DailyPick)
            .where(DailyPick.sim_date == today)
            .order_by(desc(DailyPick.score))
        )
    ).scalars().all()
    return [_serialize_pick(p) for p in picks]


@router.get("/picks/pending")
async def get_pending_picks(session: AsyncSession = Depends(get_session)):
    """All picks still awaiting settlement."""
    picks = (
        await session.execute(
            select(DailyPick)
            .where(DailyPick.result == "pending")
            .order_by(desc(DailyPick.picked_at))
        )
    ).scalars().all()
    return [_serialize_pick(p) for p in picks]


# ── Performance & Stats ───────────────────────────────────────────────────────

@router.get("/performance/summary")
async def get_performance_summary(session: AsyncSession = Depends(get_session)):
    """Aggregated performance across all settled picks."""
    all_picks = (
        await session.execute(
            select(DailyPick).where(DailyPick.result.in_(["won", "lost"]))
        )
    ).scalars().all()

    if not all_picks:
        return {
            "total_picks": 0, "won": 0, "lost": 0,
            "hit_rate": None, "total_pl": 0, "roi_percent": None,
            "total_staked": 0, "avg_odds": None, "avg_ev": None,
            "best_day": None, "worst_day": None,
        }

    n = len(all_picks)
    n_won = sum(1 for p in all_picks if p.result == "won")
    total_pl = sum(p.profit_loss or 0 for p in all_picks)
    total_staked = sum(p.stake for p in all_picks)
    avg_odds = sum(p.odds for p in all_picks) / n
    avg_ev = sum(p.ev_percent for p in all_picks) / n

    # Best / worst day
    by_day: dict[str, float] = {}
    for p in all_picks:
        by_day[p.sim_date] = by_day.get(p.sim_date, 0) + (p.profit_loss or 0)

    best_day = max(by_day.items(), key=lambda x: x[1]) if by_day else None
    worst_day = min(by_day.items(), key=lambda x: x[1]) if by_day else None

    # Bankroll curve (cumulative PL per sim_date)
    sims = (
        await session.execute(
            select(DailySimulation).order_by(DailySimulation.sim_date)
        )
    ).scalars().all()

    bankroll_curve = []
    cumulative = 0.0
    for s in sims:
        if s.total_pl is not None:
            cumulative += s.total_pl
            bankroll_curve.append({
                "date": s.sim_date,
                "bankroll": round((sims[0].bankroll_start if sims else 1000) + cumulative, 2),
                "pl": round(s.total_pl, 2),
                "hit_rate": s.hit_rate,
            })

    return {
        "total_picks": n,
        "won": n_won,
        "lost": n - n_won,
        "hit_rate": round(n_won / n, 4),
        "total_pl": round(total_pl, 2),
        "roi_percent": round(total_pl / total_staked * 100, 2) if total_staked > 0 else 0,
        "total_staked": round(total_staked, 2),
        "avg_odds": round(avg_odds, 3),
        "avg_ev": round(avg_ev, 3),
        "best_day": {"date": best_day[0], "pl": round(best_day[1], 2)} if best_day else None,
        "worst_day": {"date": worst_day[0], "pl": round(worst_day[1], 2)} if worst_day else None,
        "bankroll_curve": bankroll_curve,
    }


@router.get("/performance/by-bookmaker")
async def get_performance_by_bookmaker(session: AsyncSession = Depends(get_session)):
    """Hit rate and ROI grouped by bookmaker."""
    picks = (
        await session.execute(
            select(DailyPick).where(DailyPick.result.in_(["won", "lost"]))
        )
    ).scalars().all()

    groups: dict[str, list] = {}
    for p in picks:
        groups.setdefault(p.bookmaker, []).append(p)

    return [
        {
            "bookmaker": bm,
            "n_bets": len(ps),
            "won": sum(1 for p in ps if p.result == "won"),
            "hit_rate": round(sum(1 for p in ps if p.result == "won") / len(ps), 4),
            "total_pl": round(sum(p.profit_loss or 0 for p in ps), 2),
            "roi_percent": round(
                sum(p.profit_loss or 0 for p in ps) / sum(p.stake for p in ps) * 100, 2
            ) if sum(p.stake for p in ps) > 0 else 0,
        }
        for bm, ps in sorted(groups.items(), key=lambda x: -len(x[1]))
    ]


# ── Learning Model ─────────────────────────────────────────────────────────────

@router.get("/model/weights")
async def get_model_weights(session: AsyncSession = Depends(get_session)):
    """Current model weights with feature importance."""
    model = get_model()
    return {
        "version": model.version,
        "n_updates": model.n_updates,
        "feature_importance": model.feature_importance(),
        "weights": model.weights,
    }


@router.get("/model/performance")
async def get_model_performance_history(
    limit: int = Query(50),
    session: AsyncSession = Depends(get_session),
):
    """Model performance snapshots over time — shows learning progress."""
    rows = (
        await session.execute(
            select(ModelPerformance)
            .order_by(ModelPerformance.model_version)
            .limit(limit)
        )
    ).scalars().all()

    return [
        {
            "version": r.model_version,
            "n_bets": r.n_bets,
            "hit_rate": r.hit_rate,
            "roi_percent": r.roi_percent,
            "avg_ev": r.avg_ev_at_pick,
            "avg_model_prob": r.avg_model_prob,
            "brier_score": r.brier_score,
            "log_loss": r.log_loss,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
        }
        for r in rows
    ]


@router.post("/model/reset")
async def reset_model(session: AsyncSession = Depends(get_session)):
    """Reset model weights to defaults (for testing)."""
    from core.learning_engine import LearningModel, set_model, DEFAULT_WEIGHTS
    model = LearningModel(weights=dict(DEFAULT_WEIGHTS))
    model.version = 1
    model.n_updates = 0
    set_model(model)
    from core.result_settler import save_model_to_db
    await save_model_to_db(session, model)
    return {"status": "reset", "version": 1}


# ── Demo Data Injection ───────────────────────────────────────────────────────

@router.post("/demo/inject")
async def inject_demo_history(
    days: int = Query(30, le=90),
    session: AsyncSession = Depends(get_session),
):
    """
    Inject realistic demo simulation history for testing the dashboard.
    Simulates N days of picks with realistic win rates and learning progress.
    """
    import random
    from datetime import datetime, timezone
    rng = random.Random(99)

    injected_sims = 0
    injected_picks = 0
    model = get_model()

    for d in range(days, 0, -1):
        sim_date = (date.today() - timedelta(days=d)).isoformat()

        # Skip if already exists
        existing = await session.scalar(
            select(DailySimulation).where(DailySimulation.sim_date == sim_date)
        )
        if existing:
            continue

        n_picks = settings.DAILY_PICKS
        bankroll = settings.DEFAULT_BANKROLL
        demo_picks_data = _generate_demo_picks(rng, n_picks, sim_date)

        total_pl = sum(p["profit_loss"] for p in demo_picks_data)
        n_won = sum(1 for p in demo_picks_data if p["result"] == "won")
        total_staked = sum(p["stake"] for p in demo_picks_data)

        sim = DailySimulation(
            sim_date=sim_date,
            bankroll_start=bankroll,
            bankroll_end=round(bankroll + total_pl, 2),
            n_picks=n_picks,
            n_won=n_won,
            n_lost=n_picks - n_won,
            n_pending=0,
            hit_rate=round(n_won / n_picks, 4),
            roi_percent=round(total_pl / total_staked * 100, 2) if total_staked else 0,
            total_staked=round(total_staked, 2),
            total_pl=round(total_pl, 2),
            model_version=model.version,
            settled_at=datetime.now(timezone.utc),
        )
        session.add(sim)
        await session.flush()

        for p in demo_picks_data:
            pick = DailyPick(
                simulation_id=sim.id,
                sim_date=sim_date,
                event_id=f"demo_{sim_date}_{p['outcome_name'][:3]}",
                home_team=p["home_team"],
                away_team=p["away_team"],
                commence_time=datetime.now(timezone.utc),
                market="h2h",
                outcome_name=p["outcome_name"],
                bookmaker=p["bookmaker"],
                odds=p["odds"],
                true_prob=p["true_prob"],
                ev_percent=p["ev_percent"],
                score=p["score"],
                kelly_fraction=p["kelly_fraction"],
                stake=p["stake"],
                features=p["features"],
                model_win_prob=p["model_win_prob"],
                result=p["result"],
                profit_loss=p["profit_loss"],
                settled_at=datetime.now(timezone.utc),
            )
            session.add(pick)
            injected_picks += 1

        injected_sims += 1

    await session.commit()
    return {"injected_simulations": injected_sims, "injected_picks": injected_picks}


def _generate_demo_picks(rng: "random.Random", n: int, sim_date: str) -> list[dict]:
    """Generate realistic demo picks for one day."""
    matchups = [
        ("Boston Celtics", "Cleveland Cavaliers"),
        ("Los Angeles Lakers", "Golden State Warriors"),
        ("Denver Nuggets", "Oklahoma City Thunder"),
        ("Miami Heat", "New York Knicks"),
        ("Milwaukee Bucks", "Indiana Pacers"),
        ("Phoenix Suns", "Dallas Mavericks"),
        ("Minnesota Timberwolves", "Sacramento Kings"),
    ]
    bookmakers = ["bet365", "draftkings", "fanduel", "bwin", "unibet", "williamhill"]
    picks = []

    for i in range(min(n, len(matchups))):
        home, away = matchups[i % len(matchups)]
        pick_home = rng.random() > 0.4
        outcome = home if pick_home else away
        odds = rng.uniform(1.65, 2.40)
        tp = rng.uniform(0.48, 0.62)
        ev = tp * odds - 1.0
        kelly = max(0.01, (tp * (odds - 1) - (1 - tp)) / (odds - 1) * 0.25)
        stake = round(kelly * 1000, 2)
        model_prob = rng.uniform(0.44, 0.65)
        score = model_prob * (1 + ev)
        won = rng.random() < (tp * 0.95 + 0.02)  # slight realism bias
        pl = round(stake * (odds - 1), 2) if won else -stake

        picks.append({
            "home_team": home,
            "away_team": away,
            "outcome_name": outcome,
            "bookmaker": rng.choice(bookmakers),
            "odds": round(odds, 2),
            "true_prob": round(tp, 4),
            "ev_percent": round(ev * 100, 3),
            "score": round(score, 5),
            "kelly_fraction": round(kelly, 5),
            "stake": max(1.0, stake),
            "model_win_prob": round(model_prob, 4),
            "result": "won" if won else "lost",
            "profit_loss": pl,
            "features": {
                "ev_percent": round(ev * 100, 3),
                "true_prob": round(tp, 4),
                "odds": round(odds, 2),
                "pick_team_wp": rng.uniform(0.45, 0.72),
                "opp_team_wp": rng.uniform(0.35, 0.65),
                "pick_team_form": rng.uniform(0.2, 0.8),
                "opp_team_form": rng.uniform(0.2, 0.8),
                "rest_advantage": rng.uniform(-0.4, 0.4),
                "offense_edge": rng.uniform(-5, 8),
                "defense_edge": rng.uniform(-5, 8),
                "is_home_pick": float(pick_home),
            },
        })
    return picks


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize_sim(s: DailySimulation) -> dict:
    return {
        "id": s.id,
        "sim_date": s.sim_date,
        "bankroll_start": s.bankroll_start,
        "bankroll_end": s.bankroll_end,
        "n_picks": s.n_picks,
        "n_won": s.n_won,
        "n_lost": s.n_lost,
        "n_pending": s.n_pending,
        "hit_rate": s.hit_rate,
        "roi_percent": s.roi_percent,
        "total_staked": s.total_staked,
        "total_pl": s.total_pl,
        "model_version": s.model_version,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "settled_at": s.settled_at.isoformat() if s.settled_at else None,
    }


def _serialize_pick(p: DailyPick) -> dict:
    return {
        "id": p.id,
        "simulation_id": p.simulation_id,
        "sim_date": p.sim_date,
        "match": f"{p.home_team} vs {p.away_team}",
        "home_team": p.home_team,
        "away_team": p.away_team,
        "commence_time": p.commence_time.isoformat() if p.commence_time else None,
        "market": p.market,
        "outcome": p.outcome_name,
        "bookmaker": p.bookmaker,
        "odds": p.odds,
        "true_prob": p.true_prob,
        "ev_percent": p.ev_percent,
        "score": p.score,
        "kelly_fraction": p.kelly_fraction,
        "stake": p.stake,
        "model_win_prob": p.model_win_prob,
        "result": p.result,
        "actual_home_score": p.actual_home_score,
        "actual_away_score": p.actual_away_score,
        "profit_loss": p.profit_loss,
        "picked_at": p.picked_at.isoformat() if p.picked_at else None,
        "settled_at": p.settled_at.isoformat() if p.settled_at else None,
    }
