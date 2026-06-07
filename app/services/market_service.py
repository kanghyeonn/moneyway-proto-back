from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Callable

from app.kis.client import KisClient
from app.repositories.market_repository import MarketRepository
from app.schemas.market import (
    IntradaySnapshotRunResult,
    MarketIndicesResponse,
    RankingResponse,
    StockIntradayQuote,
)


class MarketService:
    def __init__(
        self, kis_client: KisClient, repository: MarketRepository | None
    ) -> None:
        self._kis_client = kis_client
        self._repository = repository

    async def volume_top(self, *, top_n: int) -> RankingResponse:
        items = await self._kis_client.fetch_volume_top(top_n=top_n)
        return RankingResponse(as_of=datetime.now(timezone.utc), top_n=top_n, items=items)

    async def risers(self, *, top_n: int) -> RankingResponse:
        items = await self._kis_client.fetch_risers(top_n=top_n)
        return RankingResponse(as_of=datetime.now(timezone.utc), top_n=top_n, items=items)

    async def fallers(self, *, top_n: int) -> RankingResponse:
        items = await self._kis_client.fetch_fallers(top_n=top_n)
        return RankingResponse(as_of=datetime.now(timezone.utc), top_n=top_n, items=items)

    async def trade_amount_top(self, *, top_n: int) -> RankingResponse:
        items = await self._kis_client.fetch_trade_amount_top(top_n=top_n)
        return RankingResponse(as_of=datetime.now(timezone.utc), top_n=top_n, items=items)

    async def hts_top_view(self, *, top_n: int) -> RankingResponse:
        items = await self._kis_client.fetch_hts_top_view(top_n=top_n)
        return RankingResponse(as_of=datetime.now(timezone.utc), top_n=top_n, items=items)

    async def market_indices(self) -> MarketIndicesResponse:
        items = await self._kis_client.fetch_market_indices()
        return MarketIndicesResponse(as_of=datetime.now(timezone.utc), items=items)

    async def run_intraday_snapshot(
        self,
        *,
        snapshot_batch_at: datetime | None,
        interval_minutes: int,
        limit: int | None,
        dry_run: bool,
        request_interval_seconds: float,
        progress_callback: Callable[[int, int, str, bool], None] | None = None,
    ) -> IntradaySnapshotRunResult:
        repository = self._require_repository()
        batch_at = snapshot_batch_at or _floor_datetime_to_interval(
            datetime.now(timezone.utc), interval_minutes
        )
        if batch_at.tzinfo is None:
            batch_at = batch_at.replace(tzinfo=timezone.utc)

        targets = await repository.active_snapshot_targets(limit=limit)
        quotes: list[StockIntradayQuote] = []
        errors: list[str] = []

        total_count = len(targets)
        for index, target in enumerate(targets):
            short_code = str(target["short_code"])
            success = False
            try:
                quotes.append(await self._kis_client.fetch_current_price(short_code=short_code))
                success = True
            except Exception as exc:
                errors.append(f"{short_code}: {exc}")

            if progress_callback is not None:
                progress_callback(index + 1, total_count, short_code, success)

            if index < total_count - 1 and request_interval_seconds > 0:
                await asyncio.sleep(request_interval_seconds)

        failed_count = len(targets) - len(quotes)
        status = "completed"
        skipped = 0

        if failed_count > 0:
            status = "partial" if quotes else "failed"

        if dry_run:
            return IntradaySnapshotRunResult(
                snapshot_batch_at=batch_at,
                interval_minutes=interval_minutes,
                target_stock_count=len(targets),
                success_stock_count=len(quotes),
                failed_stock_count=failed_count,
                skipped_unknown_stock=0,
                dry_run=True,
                status=status,
                errors=errors,
            )

        inserted, skipped, status = await repository.save_intraday_snapshot_batch(
            snapshot_batch_at=batch_at,
            interval_minutes=interval_minutes,
            target_stock_count=len(targets),
            quotes=quotes,
            failed_stock_count=failed_count,
            errors=errors,
        )
        return IntradaySnapshotRunResult(
            snapshot_batch_at=batch_at,
            interval_minutes=interval_minutes,
            target_stock_count=len(targets),
            success_stock_count=inserted,
            failed_stock_count=failed_count,
            skipped_unknown_stock=skipped,
            dry_run=False,
            status=status,
            errors=errors,
        )

    def _require_repository(self) -> MarketRepository:
        if self._repository is None:
            raise RuntimeError("Database repository is required for this endpoint")
        return self._repository


def _floor_datetime_to_interval(value: datetime, interval_minutes: int) -> datetime:
    normalized = value.astimezone(timezone.utc)
    minute = (normalized.minute // interval_minutes) * interval_minutes
    return normalized.replace(minute=minute, second=0, microsecond=0)
