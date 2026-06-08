from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.kis.client import KisClient
from app.repositories.market_repository import MarketRepository
from app.schemas.market import MarketIndexItem, StockRankItem
from app.schemas.market_discovery import (
    DiscoveryAdvanceDeclineResponse,
    DiscoveryDirection,
    DiscoveryIndexItem,
    DiscoveryMarket,
    DiscoveryMarketSummaryResponse,
    DiscoveryOverviewResponse,
    DiscoveryPopularSearchItem,
    DiscoveryPopularSearchesResponse,
    DiscoveryRankingItem,
    DiscoveryRankingsResponse,
    DiscoveryRankingType,
    DiscoveryStatusResponse,
)


KST = ZoneInfo("Asia/Seoul")


class MarketDiscoveryService:
    def __init__(
        self,
        kis_client: KisClient,
        repository: MarketRepository | None = None,
    ) -> None:
        self._kis_client = kis_client
        self._repository = repository

    async def status(self) -> DiscoveryStatusResponse:
        now = datetime.now(timezone.utc).astimezone(KST)
        return DiscoveryStatusResponse(
            status_label="실시간 업데이트",
            basis_label="당일 기준",
            display_time=now.strftime("%H:%M"),
            latest_snapshot_at=now,
            is_delayed=False,
        )

    async def rankings(
        self,
        *,
        ranking_type: DiscoveryRankingType,
        limit: int,
        market: DiscoveryMarket,
    ) -> DiscoveryRankingsResponse:
        _validate_market_filter(market)
        items = await self._fetch_ranking_items(ranking_type=ranking_type, limit=limit)
        return DiscoveryRankingsResponse(
            type=ranking_type,
            basis_time=datetime.now(timezone.utc).astimezone(KST),
            items=[
                _to_discovery_ranking_item(rank=rank, item=item)
                for rank, item in enumerate(items, start=1)
            ],
        )

    async def market_summary(self) -> DiscoveryMarketSummaryResponse:
        indices = await self._kis_client.fetch_market_indices()
        return _market_summary_from_indices(indices)

    async def advance_decline(self) -> DiscoveryAdvanceDeclineResponse:
        indices = await self._kis_client.fetch_market_indices()
        up_count = sum(item.rising_stock_count or 0 for item in indices)
        down_count = sum(item.falling_stock_count or 0 for item in indices)
        unchanged_count = sum(item.unchanged_stock_count or 0 for item in indices)
        return DiscoveryAdvanceDeclineResponse(
            up_count=up_count,
            up_delta=0,
            down_count=down_count,
            down_delta=0,
            unchanged_count=unchanged_count,
            basis_time=datetime.now(timezone.utc).astimezone(KST),
        )

    async def popular_searches(
        self, *, limit: int
    ) -> DiscoveryPopularSearchesResponse:
        top_view_items = await self._kis_client.fetch_hts_top_view(top_n=limit)
        stock_names = await self._stock_names_by_short_codes(
            [item.short_code for item in top_view_items]
        )
        items: list[DiscoveryPopularSearchItem] = []

        for rank, item in enumerate(top_view_items, start=1):
            quote = await self._kis_client.fetch_current_price(short_code=item.short_code)
            name = stock_names.get(item.short_code) or item.short_code
            items.append(
                DiscoveryPopularSearchItem(
                    rank=rank,
                    short_code=quote.short_code,
                    name=name,
                    change_rate=_float_or_none(quote.change_rate),
                    direction=_direction(quote.change_rate),
                )
            )

        return DiscoveryPopularSearchesResponse(items=items)

    async def _stock_names_by_short_codes(
        self, short_codes: list[str]
    ) -> dict[str, str]:
        if self._repository is None:
            return {}
        return await self._repository.stock_names_by_short_codes(short_codes)

    async def overview(
        self,
        *,
        ranking_type: DiscoveryRankingType,
        ranking_limit: int,
        popular_limit: int,
        market: DiscoveryMarket,
    ) -> DiscoveryOverviewResponse:
        status, ranking, indices, popular_searches = await asyncio.gather(
            self.status(),
            self.rankings(
                ranking_type=ranking_type,
                limit=ranking_limit,
                market=market,
            ),
            self._kis_client.fetch_market_indices(),
            self.popular_searches(limit=popular_limit),
        )
        return DiscoveryOverviewResponse(
            status=status,
            ranking=ranking,
            market_summary=_market_summary_from_indices(indices),
            advance_decline=_advance_decline_from_indices(indices),
            popular_searches=popular_searches,
        )

    async def _fetch_ranking_items(
        self, *, ranking_type: DiscoveryRankingType, limit: int
    ) -> list[StockRankItem]:
        if ranking_type == "trading_value":
            return await self._kis_client.fetch_trade_amount_top(top_n=limit)
        if ranking_type == "trading_volume":
            return await self._kis_client.fetch_volume_top(top_n=limit)
        if ranking_type == "top_gainers":
            return await self._kis_client.fetch_risers(top_n=limit)
        return await self._kis_client.fetch_fallers(top_n=limit)


def _validate_market_filter(market: DiscoveryMarket) -> None:
    if market != "all":
        raise RuntimeError("Discovery market filter currently supports only: all")


def _advance_decline_from_indices(
    indices: list[MarketIndexItem],
) -> DiscoveryAdvanceDeclineResponse:
    return DiscoveryAdvanceDeclineResponse(
        up_count=sum(item.rising_stock_count or 0 for item in indices),
        up_delta=0,
        down_count=sum(item.falling_stock_count or 0 for item in indices),
        down_delta=0,
        unchanged_count=sum(item.unchanged_stock_count or 0 for item in indices),
        basis_time=datetime.now(timezone.utc).astimezone(KST),
    )


def _market_summary_from_indices(
    indices: list[MarketIndexItem],
) -> DiscoveryMarketSummaryResponse:
    return DiscoveryMarketSummaryResponse(
        indices=[_to_discovery_index_item(item) for item in indices],
    )


def _to_discovery_ranking_item(
    *, rank: int, item: StockRankItem
) -> DiscoveryRankingItem:
    return DiscoveryRankingItem(
        rank=rank,
        short_code=item.short_code,
        name=item.name or item.short_code,
        price=_float_or_none(item.price),
        trade_amount=_float_or_none(item.trade_amount),
        volume=item.trade_volume,
        change_rate=_float_or_none(item.change_rate),
        direction=_direction(item.change_rate),
    )


def _to_discovery_index_item(item: MarketIndexItem) -> DiscoveryIndexItem:
    return DiscoveryIndexItem(
        code=item.name,
        label=item.name,
        value=float(item.price),
        change=_float_or_none(item.change),
        change_rate=_float_or_none(item.change_rate),
        direction=_direction(item.change_rate or item.change),
    )


def _direction(value: Decimal | None) -> DiscoveryDirection:
    if value is None or value == 0:
        return "flat"
    return "up" if value > 0 else "down"


def _float_or_none(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)
