from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from app.repositories.market_leadership_repository import MarketLeadershipRepository
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


KST = ZoneInfo("Asia/Seoul")
LeadershipDataSourceKind = Literal["intraday", "daily"]


@dataclass(frozen=True)
class LeadershipDataSource:
    kind: LeadershipDataSourceKind
    value: datetime | date


class MarketLeadershipService:
    def __init__(self, repository: MarketLeadershipRepository) -> None:
        self._repository = repository

    async def sector_leadership(
        self,
        *,
        snapshot_batch_at: datetime | None,
        snapshot_date: date | None,
        side: LeadershipSide,
        top_n: int,
        sort: LeadershipSort,
        include_top_stocks: int = 0,
    ) -> LeadershipResponse:
        source = await self._resolve_data_source(
            snapshot_batch_at=snapshot_batch_at,
            snapshot_date=snapshot_date,
        )
        if source.kind == "intraday":
            batch_at, items = await self._repository.sector_leadership(
                snapshot_batch_at=_as_datetime(source.value),
                side=side,
                top_n=top_n,
                sort=sort,
                include_top_stocks=include_top_stocks,
            )
        else:
            trading_date, items = await self._repository.sector_daily_price_leadership(
                trading_date=_as_date(source.value),
                side=side,
                top_n=top_n,
                sort=sort,
                include_top_stocks=include_top_stocks,
            )
            batch_at = _daily_snapshot_batch_at(trading_date)
        return LeadershipResponse(
            as_of=datetime.now(timezone.utc),
            snapshot_batch_at=batch_at,
            side=side,
            top_n=top_n,
            min_trade_amount=self._repository.min_leadership_trade_amount,
            sort=sort,
            items=items,
        )

    async def theme_leadership(
        self,
        *,
        snapshot_batch_at: datetime | None,
        snapshot_date: date | None,
        side: LeadershipSide,
        top_n: int,
        sort: LeadershipSort,
        include_top_stocks: int = 0,
    ) -> LeadershipResponse:
        source = await self._resolve_data_source(
            snapshot_batch_at=snapshot_batch_at,
            snapshot_date=snapshot_date,
        )
        if source.kind == "intraday":
            batch_at, items = await self._repository.theme_leadership(
                snapshot_batch_at=_as_datetime(source.value),
                side=side,
                top_n=top_n,
                sort=sort,
                include_top_stocks=include_top_stocks,
            )
        else:
            trading_date, items = await self._repository.theme_daily_price_leadership(
                trading_date=_as_date(source.value),
                side=side,
                top_n=top_n,
                sort=sort,
                include_top_stocks=include_top_stocks,
            )
            batch_at = _daily_snapshot_batch_at(trading_date)
        return LeadershipResponse(
            as_of=datetime.now(timezone.utc),
            snapshot_batch_at=batch_at,
            side=side,
            top_n=top_n,
            min_trade_amount=self._repository.min_leadership_trade_amount,
            sort=sort,
            items=items,
        )

    async def leadership_snapshots(
        self,
        *,
        limit: int,
        snapshot_date: date | None = None,
    ) -> LeadershipSnapshotsResponse:
        items = await self._repository.leadership_snapshots(
            limit=limit,
            snapshot_date=snapshot_date,
        )
        return LeadershipSnapshotsResponse(
            as_of=datetime.now(timezone.utc),
            items=items,
        )

    async def latest_leadership_snapshot(
        self,
        *,
        snapshot_date: date | None,
    ) -> LeadershipSnapshotItem:
        item = await self._repository.latest_leadership_snapshot(
            snapshot_date=snapshot_date,
        )
        if item is None and snapshot_date is not None:
            trading_date = await self._resolve_daily_price_date(snapshot_date)
            return LeadershipSnapshotItem(
                snapshot_batch_at=_daily_snapshot_batch_at(trading_date),
                stock_count=await self._repository.daily_price_stock_count_on_date(
                    trading_date
                ),
                status="daily_price",
            )
        if item is None:
            return LeadershipSnapshotItem(
                snapshot_batch_at=None,
                stock_count=0,
                status="empty",
            )
        return item

    async def leadership_status(self) -> LeadershipStatusResponse:
        now = datetime.now(timezone.utc)
        item = await self._repository.latest_leadership_snapshot()
        if item is None:
            return LeadershipStatusResponse(
                as_of=now,
                display_time="데이터 없음",
                is_delayed=True,
                delay_minutes=None,
                latest_snapshot_batch_at=None,
                latest_snapshot_date=None,
                stock_count=0,
                status="empty",
            )

        latest_kst = item.snapshot_batch_at.astimezone(KST)
        now_kst = now.astimezone(KST)
        latest_date = latest_kst.date()
        today = now_kst.date()
        is_delayed = latest_date < today
        delay_minutes = None
        if is_delayed:
            delay_minutes = max(
                0,
                int((now_kst - latest_kst).total_seconds() // 60),
            )
        return LeadershipStatusResponse(
            as_of=now,
            display_time=latest_kst.strftime("%Y.%m.%d 기준"),
            is_delayed=is_delayed,
            delay_minutes=delay_minutes,
            latest_snapshot_batch_at=item.snapshot_batch_at,
            latest_snapshot_date=latest_date.isoformat(),
            stock_count=item.stock_count,
            status=item.status,
        )

    async def sector_leadership_summary(
        self,
        *,
        snapshot_batch_at: datetime | None,
        snapshot_date: date | None,
    ) -> LeadershipSummaryResponse:
        source = await self._resolve_data_source(
            snapshot_batch_at=snapshot_batch_at,
            snapshot_date=snapshot_date,
        )
        if source.kind == "intraday":
            batch_at, bullish_count, bearish_count, top_bullish, top_bearish = (
                await self._repository.sector_leadership_summary(
                    snapshot_batch_at=_as_datetime(source.value),
                )
            )
        else:
            trading_date, bullish_count, bearish_count, top_bullish, top_bearish = (
                await self._repository.sector_daily_price_leadership_summary(
                    trading_date=_as_date(source.value),
                )
            )
            batch_at = _daily_snapshot_batch_at(trading_date)
        return LeadershipSummaryResponse(
            as_of=datetime.now(timezone.utc),
            snapshot_batch_at=batch_at,
            category_type="sector",
            min_trade_amount=self._repository.min_leadership_trade_amount,
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            top_bullish=top_bullish,
            top_bearish=top_bearish,
        )

    async def theme_leadership_summary(
        self,
        *,
        snapshot_batch_at: datetime | None,
        snapshot_date: date | None,
    ) -> LeadershipSummaryResponse:
        source = await self._resolve_data_source(
            snapshot_batch_at=snapshot_batch_at,
            snapshot_date=snapshot_date,
        )
        if source.kind == "intraday":
            batch_at, bullish_count, bearish_count, top_bullish, top_bearish = (
                await self._repository.theme_leadership_summary(
                    snapshot_batch_at=_as_datetime(source.value),
                )
            )
        else:
            trading_date, bullish_count, bearish_count, top_bullish, top_bearish = (
                await self._repository.theme_daily_price_leadership_summary(
                    trading_date=_as_date(source.value),
                )
            )
            batch_at = _daily_snapshot_batch_at(trading_date)
        return LeadershipSummaryResponse(
            as_of=datetime.now(timezone.utc),
            snapshot_batch_at=batch_at,
            category_type="theme",
            min_trade_amount=self._repository.min_leadership_trade_amount,
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            top_bullish=top_bullish,
            top_bearish=top_bearish,
        )

    async def sector_stocks(
        self,
        *,
        sector_id: int,
        snapshot_batch_at: datetime | None,
        snapshot_date: date | None,
        sort: CategoryStockSort,
    ) -> CategoryStocksResponse:
        source = await self._resolve_data_source(
            snapshot_batch_at=snapshot_batch_at,
            snapshot_date=snapshot_date,
        )
        if source.kind == "intraday":
            batch_at, category_name, items = await self._repository.sector_stocks(
                sector_id=sector_id,
                snapshot_batch_at=_as_datetime(source.value),
                sort=sort,
            )
        else:
            trading_date, category_name, items = (
                await self._repository.sector_daily_price_stocks(
                    sector_id=sector_id,
                    trading_date=_as_date(source.value),
                    sort=sort,
                )
            )
            batch_at = _daily_snapshot_batch_at(trading_date)
        return CategoryStocksResponse(
            as_of=datetime.now(timezone.utc),
            snapshot_batch_at=batch_at,
            category_type="sector",
            category_id=sector_id,
            category_name=category_name,
            sort=sort,
            items=items,
        )

    async def theme_stocks(
        self,
        *,
        theme_id: int,
        snapshot_batch_at: datetime | None,
        snapshot_date: date | None,
        sort: CategoryStockSort,
    ) -> CategoryStocksResponse:
        source = await self._resolve_data_source(
            snapshot_batch_at=snapshot_batch_at,
            snapshot_date=snapshot_date,
        )
        if source.kind == "intraday":
            batch_at, category_name, items = await self._repository.theme_stocks(
                theme_id=theme_id,
                snapshot_batch_at=_as_datetime(source.value),
                sort=sort,
            )
        else:
            trading_date, category_name, items = (
                await self._repository.theme_daily_price_stocks(
                    theme_id=theme_id,
                    trading_date=_as_date(source.value),
                    sort=sort,
                )
            )
            batch_at = _daily_snapshot_batch_at(trading_date)
        return CategoryStocksResponse(
            as_of=datetime.now(timezone.utc),
            snapshot_batch_at=batch_at,
            category_type="theme",
            category_id=theme_id,
            category_name=category_name,
            sort=sort,
            items=items,
        )

    async def _resolve_data_source(
        self,
        *,
        snapshot_batch_at: datetime | None,
        snapshot_date: date | None,
    ) -> LeadershipDataSource:
        if snapshot_batch_at is not None:
            if await self._repository.has_intraday_snapshot_batch_at(snapshot_batch_at):
                return LeadershipDataSource(kind="intraday", value=snapshot_batch_at)
            return LeadershipDataSource(
                kind="daily",
                value=await self._resolve_daily_price_date(
                    snapshot_batch_at.astimezone(KST).date()
                ),
            )
        if snapshot_date is None:
            batch_at = await self._repository.latest_intraday_snapshot_batch_at()
            if batch_at is None:
                raise RuntimeError("No stock_intraday_snapshot batches are available")
            return LeadershipDataSource(kind="intraday", value=batch_at)

        item = await self.latest_leadership_snapshot(snapshot_date=snapshot_date)
        if item.status == "daily_price":
            return LeadershipDataSource(
                kind="daily",
                value=item.snapshot_batch_at.astimezone(KST).date(),
            )
        if item.snapshot_batch_at is None:
            raise RuntimeError("No market leadership source is available")
        return LeadershipDataSource(kind="intraday", value=item.snapshot_batch_at)

    async def _resolve_daily_price_date(self, snapshot_date: date) -> date:
        if await self._repository.has_daily_price_on_date(snapshot_date):
            return snapshot_date
        previous_date = await self._repository.latest_daily_price_date_before(
            snapshot_date
        )
        if previous_date is None:
            raise RuntimeError(
                "No stock_daily_price data is available for requested "
                f"trading date: {snapshot_date.isoformat()}"
            )
        return previous_date


def _daily_snapshot_batch_at(trading_date: date) -> datetime:
    return datetime.combine(trading_date, time.min, tzinfo=KST)


def _as_datetime(value: datetime | date) -> datetime:
    if not isinstance(value, datetime):
        raise RuntimeError("Expected intraday snapshot datetime")
    return value


def _as_date(value: datetime | date) -> date:
    if isinstance(value, datetime):
        raise RuntimeError("Expected daily trading date")
    return value
