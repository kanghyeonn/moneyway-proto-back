from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.dependencies import get_market_leadership_service
from app.schemas.market import (
    CategoryStockSort,
    CategoryStocksResponse,
    LeadershipResponse,
    LeadershipSide,
    LeadershipSnapshotItem,
    LeadershipSnapshotsResponse,
    LeadershipSort,
    LeadershipStatusResponse,
    LeadershipSummaryResponse,
)
from app.services.market_leadership_service import MarketLeadershipService


router = APIRouter(prefix="/api/market/leadership", tags=["market-leadership"])


def _top_n(value: int | None, settings: Settings) -> int:
    return value or settings.default_top_n


@router.get("/snapshots", response_model=LeadershipSnapshotsResponse)
async def leadership_snapshots(
    limit: int = Query(default=30, ge=1, le=365),
    snapshot_date: date | None = Query(default=None, alias="date"),
    service: MarketLeadershipService = Depends(get_market_leadership_service),
) -> LeadershipSnapshotsResponse:
    return await service.leadership_snapshots(
        limit=limit,
        snapshot_date=snapshot_date,
    )


@router.get("/snapshots/latest", response_model=LeadershipSnapshotItem)
async def latest_leadership_snapshot(
    snapshot_date: date | None = Query(default=None, alias="date"),
    service: MarketLeadershipService = Depends(get_market_leadership_service),
) -> LeadershipSnapshotItem:
    return await service.latest_leadership_snapshot(snapshot_date=snapshot_date)


@router.get("/status", response_model=LeadershipStatusResponse)
async def leadership_status(
    service: MarketLeadershipService = Depends(get_market_leadership_service),
) -> LeadershipStatusResponse:
    return await service.leadership_status()


@router.get("/sectors/summary", response_model=LeadershipSummaryResponse)
async def sector_leadership_summary(
    snapshot_batch_at: datetime | None = Query(default=None),
    service: MarketLeadershipService = Depends(get_market_leadership_service),
) -> LeadershipSummaryResponse:
    return await service.sector_leadership_summary(
        snapshot_batch_at=snapshot_batch_at,
    )


@router.get("/themes/summary", response_model=LeadershipSummaryResponse)
async def theme_leadership_summary(
    snapshot_batch_at: datetime | None = Query(default=None),
    service: MarketLeadershipService = Depends(get_market_leadership_service),
) -> LeadershipSummaryResponse:
    return await service.theme_leadership_summary(
        snapshot_batch_at=snapshot_batch_at,
    )


@router.get("/sectors", response_model=LeadershipResponse)
async def sector_leadership(
    top_n: int | None = Query(default=None, ge=1, le=100),
    side: LeadershipSide = Query(default="bullish"),
    sort: LeadershipSort = Query(default="score_desc"),
    snapshot_batch_at: datetime | None = Query(default=None),
    include_top_stocks: int = Query(default=0, ge=0, le=10),
    settings: Settings = Depends(get_settings),
    service: MarketLeadershipService = Depends(get_market_leadership_service),
) -> LeadershipResponse:
    return await service.sector_leadership(
        snapshot_batch_at=snapshot_batch_at,
        side=side,
        top_n=_top_n(top_n, settings),
        sort=sort,
        include_top_stocks=include_top_stocks,
    )


@router.get("/themes", response_model=LeadershipResponse)
async def theme_leadership(
    top_n: int | None = Query(default=None, ge=1, le=100),
    side: LeadershipSide = Query(default="bullish"),
    sort: LeadershipSort = Query(default="score_desc"),
    snapshot_batch_at: datetime | None = Query(default=None),
    include_top_stocks: int = Query(default=0, ge=0, le=10),
    settings: Settings = Depends(get_settings),
    service: MarketLeadershipService = Depends(get_market_leadership_service),
) -> LeadershipResponse:
    return await service.theme_leadership(
        snapshot_batch_at=snapshot_batch_at,
        side=side,
        top_n=_top_n(top_n, settings),
        sort=sort,
        include_top_stocks=include_top_stocks,
    )


@router.get("/sectors/{sector_id}/stocks", response_model=CategoryStocksResponse)
async def sector_leadership_stocks(
    sector_id: int,
    sort: CategoryStockSort = Query(default="change_rate_desc"),
    snapshot_batch_at: datetime | None = Query(default=None),
    service: MarketLeadershipService = Depends(get_market_leadership_service),
) -> CategoryStocksResponse:
    return await service.sector_stocks(
        sector_id=sector_id,
        snapshot_batch_at=snapshot_batch_at,
        sort=sort,
    )


@router.get("/themes/{theme_id}/stocks", response_model=CategoryStocksResponse)
async def theme_leadership_stocks(
    theme_id: int,
    sort: CategoryStockSort = Query(default="change_rate_desc"),
    snapshot_batch_at: datetime | None = Query(default=None),
    service: MarketLeadershipService = Depends(get_market_leadership_service),
) -> CategoryStocksResponse:
    return await service.theme_stocks(
        theme_id=theme_id,
        snapshot_batch_at=snapshot_batch_at,
        sort=sort,
    )
