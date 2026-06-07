from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.dependencies import get_kis_client, get_market_repository
from app.kis.client import KisClient
from app.repositories.market_repository import MarketRepository
from app.schemas.market import IntradaySnapshotRunResult
from app.services.market_service import MarketService


router = APIRouter(prefix="/api/market", tags=["market-snapshots"])


@router.post("/intraday-snapshots/run", response_model=IntradaySnapshotRunResult)
async def run_intraday_snapshots(
    limit: int | None = Query(default=None, ge=1, le=5000),
    dry_run: bool = Query(default=False),
    snapshot_batch_at: datetime | None = Query(default=None),
    settings: Settings = Depends(get_settings),
    kis_client: KisClient = Depends(get_kis_client),
    repository: MarketRepository = Depends(get_market_repository),
) -> IntradaySnapshotRunResult:
    service = MarketService(kis_client, repository)
    return await service.run_intraday_snapshot(
        snapshot_batch_at=snapshot_batch_at,
        interval_minutes=settings.market_snapshot_interval_minutes,
        limit=limit,
        dry_run=dry_run,
        request_interval_seconds=settings.kis_request_interval_seconds,
    )
