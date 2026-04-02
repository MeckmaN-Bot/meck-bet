"""
Meck-Bet - NBA Value Betting Analyzer
======================================
FastAPI backend:
- NBA daily simulation with online learning (SGD)
- Live EV+ bet detection (devigging vs. sharp books)
- Arbitrage finder across bookmakers
- Kelly criterion bet sizing
- Auto-polling via APScheduler (3 daily jobs)
- Serves frontend static files in production
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

# Frontend static files (built by `npm run build`)
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

scheduler = AsyncIOScheduler()


async def scheduled_scan():
    """Periodic odds scan across all configured sports."""
    async with AsyncSessionLocal() as session:
        try:
            result = await run_full_scan(session)
            logger.info(f"Scheduled scan: {result}")
        except Exception as e:
            logger.error(f"Scheduled scan failed: {e}", exc_info=True)


async def scheduled_daily_picks():
    """
    Daily job at 11:00 UTC (06:00 ET): generate NBA picks for today.
    NBA games typically start ~19:00 ET, so this runs well before tip-off.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await run_daily_picks(
                session,
                n_picks=settings.DAILY_PICKS,
                bankroll=settings.DEFAULT_BANKROLL,
            )
            logger.info(f"Daily NBA picks: {result}")
        except Exception as e:
            logger.error(f"Daily picks failed: {e}", exc_info=True)


async def scheduled_settlement():
    """
    Daily job at 08:00 UTC: settle yesterday's picks + update learning model.
    NBA games finish by ~04:00 UTC latest, so 08:00 UTC is safe.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await settle_pending_picks(session)
            logger.info(f"Settlement: {result}")
        except Exception as e:
            logger.error(f"Settlement failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Initializing database...")
    await init_db()

    # Load persisted model weights (or initialize with defaults)
    async with AsyncSessionLocal() as session:
        try:
            await load_model_from_db(session)
        except Exception as e:
            logger.warning(f"Model load failed, using defaults: {e}")

    # Initial odds scan on startup
    async with AsyncSessionLocal() as session:
        try:
            await run_full_scan(session)
        except Exception as e:
            logger.warning(f"Initial scan skipped (no API key configured?): {e}")

    # ── APScheduler ───────────────────────────────────────────────────────────
    scheduler.add_job(
        scheduled_scan,
        trigger=IntervalTrigger(minutes=settings.POLL_INTERVAL_MINUTES),
        id="odds_scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        scheduled_daily_picks,
        trigger=CronTrigger(hour=11, minute=0, timezone="UTC"),
        id="daily_picks",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        scheduled_settlement,
        trigger=CronTrigger(hour=8, minute=0, timezone="UTC"),
        id="daily_settlement",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started: odds_scan (every 5min), daily_picks (11:00 UTC), daily_settlement (08:00 UTC)")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Meck-Bet API",
    description="NBA value betting analyzer with online learning",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ───────────────────────────────────────────────────────────────
app.include_router(dashboard.router)
app.include_router(bets.router)
app.include_router(scan.router)
app.include_router(nba.router)


@app.get("/api/health")
async def health():
    jobs = [
        {
            "id": j.id,
            "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
        }
        for j in scheduler.get_jobs()
    ]
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "scheduler_running": scheduler.running,
        "jobs": jobs,
        "frontend_built": FRONTEND_DIST.exists(),
    }


@app.get("/api/config")
async def get_config():
    """Non-sensitive runtime config for the frontend."""
    return {
        "sports": settings.SPORTS,
        "markets": settings.MARKETS,
        "poll_interval_minutes": settings.POLL_INTERVAL_MINUTES,
        "min_ev_threshold": settings.MIN_EV_THRESHOLD,
        "kelly_fraction": settings.KELLY_FRACTION,
        "default_bankroll": settings.DEFAULT_BANKROLL,
        "daily_picks": settings.DAILY_PICKS,
        "sharp_books": settings.SHARP_BOOKS,
        "has_api_key": settings.ODDS_API_KEY not in ("YOUR_ODDS_API_KEY", "", None),
    }


# ── Static Frontend (production) ─────────────────────────────────────────────
# Must come AFTER all API routes so /api/* takes priority.
if FRONTEND_DIST.exists():
    # Serve /assets/* as static files
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """Catch-all: serve index.html for all non-API routes (SPA routing)."""
        # Don't catch API routes (belt and suspenders)
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"error": "Frontend not built. Run: cd frontend && npm run build"}
else:
    logger.info("Frontend dist not found — running in API-only mode (dev). Run 'npm run build' for production.")
