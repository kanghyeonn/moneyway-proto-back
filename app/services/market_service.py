from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Callable

from app.kis.client import KisClient
from app.repositories.market_repository import MarketRepository
from app.schemas.market import (
    DailyPriceCollectionResult,
    IntradaySnapshotRunResult,
    StockDailyPrice,
    StockIntradayQuote,
)


class MarketService:
    def __init__(
        self, kis_client: KisClient, repository: MarketRepository | None
    ) -> None:
        self._kis_client = kis_client
        self._repository = repository

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

        targets = await repository.active_snapshot_targets(
            limit=limit,
            exclude_stock_types=["ETF", "ETN"],
        )
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

    async def run_daily_price_collection(
        self,
        *,
        start_date: date,
        end_date: date,
        limit: int | None,
        dry_run: bool,
        request_interval_seconds: float,
        market_div_code_resolver: Callable[[str], str] | None = None,
        progress_callback: Callable[[int, int, str, bool], None] | None = None,
    ) -> DailyPriceCollectionResult:
        if start_date > end_date:
            raise ValueError("start_date must be earlier than or equal to end_date")

        repository = self._require_repository()
        targets = await repository.active_snapshot_targets(limit=limit)
        daily_prices: list[StockDailyPrice] = []
        errors: list[str] = []

        total_count = len(targets)
        success_stock_count = 0
        for index, target in enumerate(targets):
            short_code = str(target["short_code"])
            success = False
            try:
                market_div_code = (
                    market_div_code_resolver(short_code)
                    if market_div_code_resolver is not None
                    else None
                )
                items = await self._kis_client.fetch_daily_prices(
                    short_code=short_code,
                    start_date=start_date,
                    end_date=end_date,
                    market_div_code=market_div_code,
                )
                daily_prices.extend(items)
                success_stock_count += 1
                success = True
            except Exception as exc:
                errors.append(f"{short_code}: {exc}")

            if progress_callback is not None:
                progress_callback(index + 1, total_count, short_code, success)

            if index < total_count - 1 and request_interval_seconds > 0:
                await asyncio.sleep(request_interval_seconds)

        failed_stock_count = total_count - success_stock_count
        status = "completed"
        if failed_stock_count > 0:
            status = "partial" if success_stock_count else "failed"

        if dry_run:
            return DailyPriceCollectionResult(
                start_date=start_date,
                end_date=end_date,
                target_stock_count=total_count,
                success_stock_count=success_stock_count,
                failed_stock_count=failed_stock_count,
                saved_price_count=len(daily_prices),
                skipped_unknown_stock=0,
                dry_run=True,
                status=status,
                errors=errors,
            )

        saved_count, skipped = await repository.save_daily_prices(
            daily_prices=daily_prices
        )
        return DailyPriceCollectionResult(
            start_date=start_date,
            end_date=end_date,
            target_stock_count=total_count,
            success_stock_count=success_stock_count,
            failed_stock_count=failed_stock_count,
            saved_price_count=saved_count,
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
