"""
Result Settler + Model Updater
===============================
Runs daily (after games finish) to:
1. Fetch actual game results from balldontlie API
2. Settle all pending DailyPick records
3. Update DailySimulation totals (P&L, hit rate)
4. Feed outcomes into the learning engine (SGD update)
5. Persist updated model weights to DB
6. Snapshot model performance metrics
"""

import logging
from datetime import datetime, date, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from core.nba_fetcher import nba_fetcher
from typing import Optional
from core.learning_engine import (
    get_model, set_model, BetFeatures, LearningModel,
    compute_model_metrics,
)
from models.database import (
    DailySimulation, DailyPick, ModelWeights, ModelPerformance
)

logger = logging.getLogger(__name__)


async def load_model_from_db(session: AsyncSession) -> LearningModel:
    """Load latest model weights from DB, or use defaults."""
    latest_version = await session.scalar(
        select(ModelWeights.version).order_by(ModelWeights.version.desc()).limit(1)
    )
    if not latest_version:
        model = LearningModel()
        await save_model_to_db(session, model)
        return model

    rows = (
        await session.execute(
            select(ModelWeights)
            .where(ModelWeights.version == latest_version)
            .order_by(ModelWeights.feature_name)
        )
    ).scalars().all()

    weights = {row.feature_name: row.weight for row in rows}
    n_updates = max((row.n_updates for row in rows), default=0)

    model = LearningModel(weights=weights)
    model.version = latest_version
    model.n_updates = n_updates
    set_model(model)
    logger.info(f"Loaded model v{latest_version} ({n_updates} updates) from DB")
    return model


async def save_model_to_db(session: AsyncSession, model: LearningModel):
    """Persist current model weights as a new version."""
    new_version = model.version

    for feature_name, weight in model.weights.items():
        row = ModelWeights(
            version=new_version,
            feature_name=feature_name,
            weight=weight,
            n_updates=model.n_updates,
        )
        session.add(row)

    await session.commit()
    logger.info(f"Saved model v{new_version} ({model.n_updates} updates) to DB")


async def settle_pending_picks(session: AsyncSession, settle_date: Optional[str] = None) -> dict:
    """
    Fetch results and settle all pending picks for the given date.
    Defaults to yesterday (games from yesterday should be finished by now).
    """
    if not settle_date:
        settle_date = (date.today() - timedelta(days=1)).isoformat()

    logger.info(f"Settling picks for {settle_date}...")

    # Load pending picks for this date
    pending = (
        await session.execute(
            select(DailyPick)
            .where(DailyPick.sim_date == settle_date)
            .where(DailyPick.result == "pending")
        )
    ).scalars().all()

    if not pending:
        logger.info(f"No pending picks for {settle_date}")
        return {"date": settle_date, "settled": 0}

    model = get_model()
    n_won = n_lost = n_void = 0
    total_pl = 0.0
    updates_made = []

    for pick in pending:
        game_date = pick.commence_time.date().isoformat() if pick.commence_time else settle_date
        result_data = await nba_fetcher.get_game_result(
            pick.home_team, pick.away_team, game_date
        )

        if not result_data:
            logger.debug(f"No result yet for {pick.home_team} vs {pick.away_team}")
            continue

        winner = result_data["winner"]
        home_score = result_data["home_score"]
        away_score = result_data["away_score"]

        # Determine win/loss for our pick
        won = (pick.outcome_name == winner)
        result = "won" if won else "lost"
        profit_loss = round(pick.stake * (pick.odds - 1), 2) if won else -pick.stake

        pick.result = result
        pick.actual_home_score = home_score
        pick.actual_away_score = away_score
        pick.profit_loss = profit_loss
        pick.settled_at = datetime.now(timezone.utc)

        if won:
            n_won += 1
        else:
            n_lost += 1
        total_pl += profit_loss

        # Build features for learning update
        if pick.features:
            f = pick.features
            features = BetFeatures(
                ev_percent=f.get("ev_percent", pick.ev_percent),
                true_prob=f.get("true_prob", pick.true_prob),
                odds=f.get("odds", pick.odds),
                pick_team_wp=f.get("pick_team_wp", 0.5),
                opp_team_wp=f.get("opp_team_wp", 0.5),
                pick_team_form=f.get("pick_team_form", 0.4),
                opp_team_form=f.get("opp_team_form", 0.4),
                rest_advantage=f.get("rest_advantage", 0.0),
                offense_edge=f.get("offense_edge", 0.0),
                defense_edge=f.get("defense_edge", 0.0),
                is_home_pick=f.get("is_home_pick", 0.0),
            )
            model.update(features, won)
            updates_made.append({"model_win_prob": pick.model_win_prob, "result": result})

    await session.flush()

    # ── Update DailySimulation totals ────────────────────────────────────────
    sims = (
        await session.execute(
            select(DailySimulation).where(DailySimulation.sim_date == settle_date)
        )
    ).scalars().all()

    for sim in sims:
        # Re-aggregate all picks for this sim
        all_picks = (
            await session.execute(
                select(DailyPick).where(DailyPick.simulation_id == sim.id)
            )
        ).scalars().all()

        total_won = sum(1 for p in all_picks if p.result == "won")
        total_lost = sum(1 for p in all_picks if p.result == "lost")
        total_pending = sum(1 for p in all_picks if p.result == "pending")
        sim_pl = sum(p.profit_loss or 0 for p in all_picks)

        sim.n_won = total_won
        sim.n_lost = total_lost
        sim.n_pending = total_pending
        sim.total_pl = round(sim_pl, 2)
        sim.bankroll_end = round(sim.bankroll_start + sim_pl, 2)
        sim.roi_percent = round(sim_pl / sim.total_staked * 100, 2) if sim.total_staked > 0 else 0

        settled_count = total_won + total_lost
        sim.hit_rate = round(total_won / settled_count, 4) if settled_count > 0 else None

        if total_pending == 0:
            sim.settled_at = datetime.now(timezone.utc)

    # ── Bump model version and save ──────────────────────────────────────────
    if updates_made:
        model.version += 1
        await save_model_to_db(session, model)
        set_model(model)

        # ── Snapshot model performance ───────────────────────────────────────
        # Gather all-time settled picks for metrics
        all_settled = (
            await session.execute(
                select(DailyPick).where(DailyPick.result.in_(["won", "lost"]))
            )
        ).scalars().all()

        metrics = compute_model_metrics([
            {"model_win_prob": p.model_win_prob, "result": p.result, "ev_percent": p.ev_percent}
            for p in all_settled if p.model_win_prob
        ])

        if metrics:
            perf = ModelPerformance(
                model_version=model.version,
                n_bets=metrics["n_bets"],
                hit_rate=metrics["hit_rate"],
                roi_percent=round(
                    sum(p.profit_loss or 0 for p in all_settled) /
                    sum(p.stake for p in all_settled) * 100
                    if all_settled else 0, 2
                ),
                avg_ev_at_pick=metrics["avg_ev"],
                avg_model_prob=metrics["avg_model_prob"],
                brier_score=metrics.get("brier_score"),
                log_loss=metrics.get("log_loss"),
            )
            session.add(perf)

    await session.commit()

    summary = {
        "date": settle_date,
        "settled": n_won + n_lost,
        "won": n_won,
        "lost": n_lost,
        "void": n_void,
        "total_pl": round(total_pl, 2),
        "model_updates": len(updates_made),
        "new_model_version": model.version,
    }
    logger.info(f"Settlement done: {summary}")
    return summary
