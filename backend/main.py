"""
Meck-Bet - Sports Betting Value Analyzer
=========================================
FastAPI backend with:
- Live EV+ bet detection (sharp vs. soft odds comparison)
- Arbitrage finder across bookmakers
- NBA daily simulation with online learning
- Kelly criterion bet sizing
- Bankroll tracker with CLV analysis
- Auto-polling via APScheduler
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config import settings
from models.database import init_db, AsyncSessionLocal
from core.analyzer import run_full_scan
from core.bet_selector import run_daily_picks
from core.result_settler import settle_pending_picks, load_model_from_db
from routers import dashboard, bets, scan, nba

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_scan():
    """Periodic odds scan across all sports."""
    async with AsyncSessionLocal() as session:
        try:
            result = await run_full_scan(session)
            logger.info(f"Scheduled scan: {result}")
        except Exception as e:
            logger.error(f"Scheduled scan failed: {e}")


async def scheduled_daily_picks():
    """
    Daily job at 11:00 UTC: generate NBA picks for today.
    NBA games typically start 18:00–02:00 ET, so picking at 11:00 UTC
    (= 06:00 ET) gives plenty of time to review before tip-off.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await run_daily_picks(
                session,
                n_picks=settings.DAILY_PICKS,
                bankroll=settings.DEFAULT_BANKROLL,
            )
            logger.info(f"Daily picks: {result}")
        except Exception as e:
            logger.error(f"Daily picks failed: {e}")


async def scheduled_settlement():
    """
    Daily job at 08:00 UTC: settle yesterday's picks + update model.
    NBA games finish by ~04:00 UTC at the latest.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await settle_pending_picks(session)
            logger.info(f"Settlement: {result}")
        except Exception as e:
            logger.error(f"Settlement failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Initializing database...")
    await init_db()

    # Load model weights from DB (or initialize defaults)
    async with AsyncSessionLocal() as session:
        try:
            await load_model_from_db(session)
        except Exception as e:
            logger.warning(f"Model load failed, using defaults: {e}")

    # Initial odds scan
    logger.info("Running initial odds scan...")
    async with AsyncSessionLocal() as session:
        try:
            await run_full_scan(session)
        except Exception as e:
            logger.warning(f"Initial scan failed (no API key?): {e}")

    # ── Scheduler ─────────────────────────────────────────────────────────────
    logger.info(f"Starting scheduler...")

    # Odds scan every N minutes
    scheduler.add_job(
        scheduled_scan,
        trigger=IntervalTrigger(minutes=settings.POLL_INTERVAL_MINUTES),
        id="odds_scan",
        replace_existing=True,
    )

    # Daily picks at 11:00 UTC (06:00 ET) — before NBA games start
    scheduler.add_job(
        scheduled_daily_picks,
        trigger=CronTrigger(hour=11, minute=0, timezone="UTC"),
        id="daily_picks",
        replace_existing=True,
    )

    # Daily settlement at 08:00 UTC — all games from yesterday finished
    scheduler.add_job(
        scheduled_settlement,
        trigger=CronTrigger(hour=8, minute=0, timezone="UTC"),
        id="daily_settlement",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with 3 jobs: odds_scan, daily_picks, daily_settlement")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


app = FastAPI(
    title="Meck-Bet API",
    description="Automated sports betting value analyzer - NBA focus with online learning",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(bets.router)
app.include_router(scan.router)
app.include_router(nba.router)


@app.get("/api/health")
async def health():
    jobs = [
        {"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
        for j in scheduler.get_jobs()
    ]
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "scheduler_running": scheduler.running,
        "jobs": jobs,
    }


@app.get("/api/config")
async def get_config():
    return {
        "sports": settings.SPORTS,
        "markets": settings.MARKETS,
        "poll_interval_minutes": settings.POLL_INTERVAL_MINUTES,
        "min_ev_threshold": settings.MIN_EV_THRESHOLD,
        "kelly_fraction": settings.KELLY_FRACTION,
        "default_bankroll": settings.DEFAULT_BANKROLL,
        "daily_picks": settings.DAILY_PICKS,
        "sharp_books": settings.SHARP_BOOKS,
        "has_api_key": settings.ODDS_API_KEY != "YOUR_ODDS_API_KEY",
    }
