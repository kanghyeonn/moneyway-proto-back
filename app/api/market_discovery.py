from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_market_discovery_service
from app.schemas.market_discovery import (
    DiscoveryAdvanceDeclineResponse,
    DiscoveryMarket,
    DiscoveryMarketSummaryResponse,
    DiscoveryOverviewResponse,
    DiscoveryPopularSearchesResponse,
    DiscoveryRankingsResponse,
    DiscoveryRankingType,
    DiscoveryStatusResponse,
)
from app.services.market_discovery_service import MarketDiscoveryService


router = APIRouter(prefix="/api/market/discovery", tags=["market-discovery"])


@router.get("/status", response_model=DiscoveryStatusResponse)
async def discovery_status(
    service: MarketDiscoveryService = Depends(get_market_discovery_service),
) -> DiscoveryStatusResponse:
    return await service.status()


@router.get("/rankings", response_model=DiscoveryRankingsResponse)
async def discovery_rankings(
    ranking_type: DiscoveryRankingType = Query(alias="type"),
    limit: int = Query(default=30, ge=1, le=100),
    market: DiscoveryMarket = Query(default="all"),
    service: MarketDiscoveryService = Depends(get_market_discovery_service),
) -> DiscoveryRankingsResponse:
    return await service.rankings(
        ranking_type=ranking_type,
        limit=limit,
        market=market,
    )


@router.get("/market-summary", response_model=DiscoveryMarketSummaryResponse)
async def discovery_market_summary(
    service: MarketDiscoveryService = Depends(get_market_discovery_service),
) -> DiscoveryMarketSummaryResponse:
    return await service.market_summary()


@router.get("/advance-decline", response_model=DiscoveryAdvanceDeclineResponse)
async def discovery_advance_decline(
    service: MarketDiscoveryService = Depends(get_market_discovery_service),
) -> DiscoveryAdvanceDeclineResponse:
    return await service.advance_decline()


@router.get("/popular-searches", response_model=DiscoveryPopularSearchesResponse)
async def discovery_popular_searches(
    limit: int = Query(default=3, ge=1, le=20),
    service: MarketDiscoveryService = Depends(get_market_discovery_service),
) -> DiscoveryPopularSearchesResponse:
    return await service.popular_searches(limit=limit)


@router.get("/overview", response_model=DiscoveryOverviewResponse)
async def discovery_overview(
    ranking_type: DiscoveryRankingType = Query(default="trading_value"),
    ranking_limit: int = Query(default=30, ge=1, le=100),
    popular_limit: int = Query(default=3, ge=1, le=20),
    market: DiscoveryMarket = Query(default="all"),
    service: MarketDiscoveryService = Depends(get_market_discovery_service),
) -> DiscoveryOverviewResponse:
    return await service.overview(
        ranking_type=ranking_type,
        ranking_limit=ranking_limit,
        popular_limit=popular_limit,
        market=market,
    )
