"""
Meck-Bet - Sports Betting Value Analyzer
=========================================
FastAPI backend with:
- Live EV+ bet detection (sharp vs. soft odds comparison)
- Arbitrage finder across bookmakers
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

from config import settings
from models.database import init_db, AsyncSessionLocal
from core.analyzer import run_full_scan
from routers import dashboard, bets, scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_scan():
    """APScheduler job: scan odds and update database."""
    async with AsyncSessionLocal() as session:
        try:
            result = await run_full_scan(session)
            logger.info(f"Scheduled scan: {result}")
        except Exception as e:
            logger.error(f"Scheduled scan failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()

    logger.info("Running initial odds scan...")
    async with AsyncSessionLocal() as session:
        try:
            await run_full_scan(session)
        except Exception as e:
            logger.warning(f"Initial scan failed (no API key?): {e}")

    logger.info(f"Starting scheduler (every {settings.POLL_INTERVAL_MINUTES} minutes)...")
    scheduler.add_job(
        scheduled_scan,
        trigger=IntervalTrigger(minutes=settings.POLL_INTERVAL_MINUTES),
        id="odds_scan",
        replace_existing=True,
    )
    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


app = FastAPI(
    title="Meck-Bet API",
    description="Automated sports betting value analyzer - finds EV+ bets and arbitrage",
    version="1.0.0",
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


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "scheduler_running": scheduler.running,
    }


@app.get("/api/config")
async def get_config():
    """Return non-sensitive config for the frontend."""
    return {
        "sports": settings.SPORTS,
        "markets": settings.MARKETS,
        "poll_interval_minutes": settings.POLL_INTERVAL_MINUTES,
        "min_ev_threshold": settings.MIN_EV_THRESHOLD,
        "kelly_fraction": settings.KELLY_FRACTION,
        "default_bankroll": settings.DEFAULT_BANKROLL,
        "sharp_books": settings.SHARP_BOOKS,
        "has_api_key": settings.ODDS_API_KEY != "YOUR_ODDS_API_KEY",
    }
