from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.repositories.market_discovery_repository import MarketDiscoveryRepository
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


KST = ZoneInfo("Asia/Seoul")


class MarketDiscoveryService:
    def __init__(self, discovery_repository: MarketDiscoveryRepository) -> None:
        self._discovery_repository = discovery_repository

    async def status(self) -> DiscoveryStatusResponse:
        latest_snapshot_at = await self._discovery_repository.latest_snapshot_batch_at()
        if latest_snapshot_at is None:
            raise RuntimeError("No market discovery snapshots are available")

        latest_kst = latest_snapshot_at.astimezone(KST)
        age_seconds = (
            datetime.now(timezone.utc) - latest_snapshot_at.astimezone(timezone.utc)
        ).total_seconds()
        is_delayed = age_seconds > 180
        return DiscoveryStatusResponse(
            status_label="업데이트 지연" if is_delayed else "실시간 업데이트",
            basis_label="당일 기준",
            display_time=latest_kst.strftime("%H:%M"),
            latest_snapshot_at=latest_kst,
            is_delayed=is_delayed,
        )

    async def rankings(
        self,
        *,
        ranking_type: DiscoveryRankingType,
        limit: int,
        market: DiscoveryMarket,
    ) -> DiscoveryRankingsResponse:
        _validate_market_filter(market)
        batch_at, items = await self._discovery_repository.ranking_items(
            ranking_type=ranking_type,
            limit=limit,
        )
        return DiscoveryRankingsResponse(
            type=ranking_type,
            basis_time=batch_at.astimezone(KST),
            items=items,
        )

    async def market_summary(self) -> DiscoveryMarketSummaryResponse:
        _batch_at, items = await self._discovery_repository.index_items()
        return DiscoveryMarketSummaryResponse(indices=items)

    async def advance_decline(self) -> DiscoveryAdvanceDeclineResponse:
        response = await self._discovery_repository.advance_decline()
        return response.model_copy(
            update={"basis_time": response.basis_time.astimezone(KST)}
        )

    async def popular_searches(
        self, *, limit: int
    ) -> DiscoveryPopularSearchesResponse:
        _batch_at, items = await self._discovery_repository.popular_search_items(
            limit=limit,
        )
        return DiscoveryPopularSearchesResponse(items=items)

    async def overview(
        self,
        *,
        ranking_type: DiscoveryRankingType,
        ranking_limit: int,
        popular_limit: int,
        market: DiscoveryMarket,
    ) -> DiscoveryOverviewResponse:
        (
            status,
            ranking,
            market_summary,
            advance_decline,
            popular_searches,
        ) = await asyncio.gather(
            self.status(),
            self.rankings(
                ranking_type=ranking_type,
                limit=ranking_limit,
                market=market,
            ),
            self.market_summary(),
            self.advance_decline(),
            self.popular_searches(limit=popular_limit),
        )
        return DiscoveryOverviewResponse(
            status=status,
            ranking=ranking,
            market_summary=market_summary,
            advance_decline=advance_decline,
            popular_searches=popular_searches,
        )


def _validate_market_filter(market: DiscoveryMarket) -> None:
    if market != "all":
        raise RuntimeError("Discovery market filter currently supports only: all")
