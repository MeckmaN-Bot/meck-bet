"""Scan router - manual trigger and status for odds scanning."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session
from core.analyzer import run_full_scan
from core.odds_fetcher import odds_client

router = APIRouter(prefix="/api/scan", tags=["scan"])

_last_scan_result: dict = {}
_scan_running: bool = False


@router.post("/run")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Manually trigger a full odds scan in the background."""
    global _scan_running
    if _scan_running:
        return {"status": "already_running", "message": "Scan is already in progress"}

    async def _run():
        global _scan_running, _last_scan_result
        _scan_running = True
        try:
            result = await run_full_scan(session)
            _last_scan_result = result
        finally:
            _scan_running = False

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Scan started in background"}


@router.get("/status")
async def scan_status():
    """Get scan status and last result."""
    return {
        "is_running": _scan_running,
        "last_result": _last_scan_result,
        "api_quota": odds_client.quota_info(),
    }
