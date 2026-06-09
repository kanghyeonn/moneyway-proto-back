from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal

from app.kis.client import KisClient
from app.repositories.market_discovery_repository import (
    DiscoverySnapshotStatus,
    MarketDiscoveryRepository,
)
from app.repositories.market_repository import MarketRepository
from app.schemas.market import MarketIndexItem, StockRankItem
from app.schemas.market_discovery import (
    DiscoveryDirection,
    DiscoveryIndexItem,
    DiscoveryPopularSearchItem,
    DiscoveryRankingItem,
    DiscoveryRankingType,
)


DiscoverySnapshotProgressCallback = Callable[[str, bool, str], None]
RANKING_TYPES: tuple[DiscoveryRankingType, ...] = (
    "trading_value",
    "trading_volume",
    "top_gainers",
    "top_losers",
)


class MarketDiscoverySnapshotService:
    def __init__(
        self,
        kis_client: KisClient,
        stock_repository: MarketRepository,
        discovery_repository: MarketDiscoveryRepository,
    ) -> None:
        self._kis_client = kis_client
        self._stock_repository = stock_repository
        self._discovery_repository = discovery_repository

    async def run_snapshot(
        self,
        *,
        snapshot_batch_at: datetime | None = None,
        ranking_limit: int = 30,
        popular_limit: int = 20,
        request_interval_seconds: float = 0,
        progress_callback: DiscoverySnapshotProgressCallback | None = None,
    ) -> datetime:
        batch_at = snapshot_batch_at or datetime.now(timezone.utc).replace(
            second=0,
            microsecond=0,
        )
        if batch_at.tzinfo is None:
            batch_at = batch_at.replace(tzinfo=timezone.utc)

        await self._discovery_repository.begin_snapshot_batch(
            snapshot_batch_at=batch_at,
        )

        rankings: dict[DiscoveryRankingType, list[DiscoveryRankingItem]] = {}
        indices: list[DiscoveryIndexItem] = []
        index_counts_by_code: dict[str, tuple[int, int, int]] = {}
        popular_searches: list[DiscoveryPopularSearchItem] = []
        errors: list[str] = []

        ranking_success_count = 0
        ranking_failed_count = 0
        for ranking_type in RANKING_TYPES:
            try:
                ranking_items = await self._fetch_ranking(
                    ranking_type=ranking_type,
                    limit=ranking_limit,
                )
                rankings[ranking_type] = ranking_items
                ranking_success_count += 1
                _notify(progress_callback, f"ranking:{ranking_type}", True, "")
            except Exception as exc:
                ranking_failed_count += 1
                message = f"ranking:{ranking_type}: {exc}"
                errors.append(message)
                _notify(progress_callback, f"ranking:{ranking_type}", False, str(exc))
            await _sleep_if_needed(request_interval_seconds)

        index_success_count = 0
        index_failed_count = 0
        try:
            market_indices = await self._kis_client.fetch_market_indices()
            indices = [_to_discovery_index_item(item) for item in market_indices]
            index_counts_by_code = {
                item.name: (
                    item.rising_stock_count or 0,
                    item.falling_stock_count or 0,
                    item.unchanged_stock_count or 0,
                )
                for item in market_indices
            }
            index_success_count = len(indices)
            _notify(progress_callback, "indices", True, "")
        except Exception as exc:
            index_failed_count = 1
            message = f"indices: {exc}"
            errors.append(message)
            _notify(progress_callback, "indices", False, str(exc))
        await _sleep_if_needed(request_interval_seconds)

        popular_success_count = 0
        popular_failed_count = 0
        try:
            popular_searches = await self._fetch_popular_searches(limit=popular_limit)
            popular_success_count = 1
            _notify(progress_callback, "popular_searches", True, "")
        except Exception as exc:
            popular_failed_count = 1
            message = f"popular_searches: {exc}"
            errors.append(message)
            _notify(progress_callback, "popular_searches", False, str(exc))

        status = _snapshot_status(
            has_data=bool(rankings or indices or popular_searches),
            has_errors=bool(errors),
        )
        await self._discovery_repository.save_snapshot(
            snapshot_batch_at=batch_at,
            status=status,
            rankings=rankings,
            indices=indices,
            popular_searches=popular_searches,
            index_counts_by_code=index_counts_by_code,
            ranking_success_count=ranking_success_count,
            ranking_failed_count=ranking_failed_count,
            index_success_count=index_success_count,
            index_failed_count=index_failed_count,
            popular_success_count=popular_success_count,
            popular_failed_count=popular_failed_count,
            error_message="\n".join(errors[:20]) if errors else None,
        )
        return batch_at

    async def _fetch_ranking(
        self, *, ranking_type: DiscoveryRankingType, limit: int
    ) -> list[DiscoveryRankingItem]:
        if ranking_type == "trading_value":
            items = await self._kis_client.fetch_trade_amount_top(top_n=limit)
        elif ranking_type == "trading_volume":
            items = await self._kis_client.fetch_volume_top(top_n=limit)
        elif ranking_type == "top_gainers":
            items = await self._kis_client.fetch_risers(top_n=limit)
        else:
            items = await self._kis_client.fetch_fallers(top_n=limit)

        return [
            _to_discovery_ranking_item(rank=rank, item=item)
            for rank, item in enumerate(items, start=1)
        ]

    async def _fetch_popular_searches(
        self, *, limit: int
    ) -> list[DiscoveryPopularSearchItem]:
        top_view_items = await self._kis_client.fetch_hts_top_view(top_n=limit)
        stock_names = await self._stock_repository.stock_names_by_short_codes(
            [item.short_code for item in top_view_items]
        )
        items: list[DiscoveryPopularSearchItem] = []

        for rank, item in enumerate(top_view_items, start=1):
            quote = await self._kis_client.fetch_current_price(short_code=item.short_code)
            change_rate = _float_or_none(quote.change_rate)
            items.append(
                DiscoveryPopularSearchItem(
                    rank=rank,
                    short_code=quote.short_code,
                    name=stock_names.get(item.short_code) or item.short_code,
                    change_rate=change_rate,
                    direction=_direction(quote.change_rate),
                )
            )
        return items


def _snapshot_status(
    *, has_data: bool, has_errors: bool
) -> DiscoverySnapshotStatus:
    if not has_errors:
        return "completed"
    return "partial" if has_data else "failed"


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


async def _sleep_if_needed(seconds: float) -> None:
    if seconds > 0:
        await asyncio.sleep(seconds)


def _notify(
    callback: DiscoverySnapshotProgressCallback | None,
    step: str,
    success: bool,
    message: str,
) -> None:
    if callback is not None:
        callback(step, success, message)
