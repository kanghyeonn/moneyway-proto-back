from __future__ import annotations

from datetime import datetime, timezone

import asyncpg

from app.schemas.market import StockDailyPrice, StockIntradayQuote


class MarketRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def active_snapshot_targets(
        self, *, limit: int | None = None
    ) -> list[dict[str, object]]:
        query = """
            SELECT id, short_code
            FROM public.stock
            WHERE is_active = true
            ORDER BY short_code
        """
        args: tuple[int, ...] = ()
        if limit is not None:
            query += " LIMIT $1"
            args = (limit,)

        rows = await self._pool.fetch(query, *args)
        return [{"stock_id": row["id"], "short_code": row["short_code"]} for row in rows]

    async def save_intraday_snapshot_batch(
        self,
        *,
        snapshot_batch_at: datetime,
        interval_minutes: int,
        target_stock_count: int,
        quotes: list[StockIntradayQuote],
        failed_stock_count: int,
        errors: list[str],
    ) -> tuple[int, int, str]:
        status = "completed"
        if failed_stock_count > 0:
            status = "partial" if quotes else "failed"

        short_codes = [quote.short_code for quote in quotes]
        inserted = 0
        skipped = 0

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                stock_rows = await conn.fetch(
                    """
                    SELECT id, short_code
                    FROM public.stock
                    WHERE short_code = ANY($1::text[])
                        AND is_active = true
                    """,
                    short_codes,
                )
                stock_ids_by_code = {
                    row["short_code"]: row["id"] for row in stock_rows
                }

                records = []
                observed_at = datetime.now(timezone.utc)
                for quote in quotes:
                    stock_id = stock_ids_by_code.get(quote.short_code)
                    if stock_id is None:
                        skipped += 1
                        continue
                    records.append(
                        (
                            stock_id,
                            snapshot_batch_at,
                            observed_at,
                            quote.price,
                            quote.accumulated_volume,
                            quote.accumulated_trade_amount,
                            quote.change_rate,
                        )
                    )

                await conn.execute(
                    """
                    INSERT INTO public.market_snapshot_batch (
                        snapshot_batch_at,
                        interval_minutes,
                        status,
                        target_stock_count,
                        success_stock_count,
                        failed_stock_count,
                        finished_at,
                        error_message
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, now(), $7)
                    ON CONFLICT (snapshot_batch_at) DO UPDATE SET
                        interval_minutes = EXCLUDED.interval_minutes,
                        status = EXCLUDED.status,
                        target_stock_count = EXCLUDED.target_stock_count,
                        success_stock_count = EXCLUDED.success_stock_count,
                        failed_stock_count = EXCLUDED.failed_stock_count,
                        finished_at = EXCLUDED.finished_at,
                        error_message = EXCLUDED.error_message
                    """,
                    snapshot_batch_at,
                    interval_minutes,
                    status,
                    target_stock_count,
                    len(records),
                    failed_stock_count,
                    "\n".join(errors[:20]) if errors else None,
                )

                if records:
                    await conn.executemany(
                        """
                        INSERT INTO public.stock_intraday_snapshot (
                            stock_id,
                            snapshot_batch_at,
                            observed_at,
                            price,
                            accumulated_volume,
                            accumulated_trade_amount,
                            change_rate
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (stock_id, snapshot_batch_at) DO UPDATE SET
                            observed_at = EXCLUDED.observed_at,
                            price = EXCLUDED.price,
                            accumulated_volume = EXCLUDED.accumulated_volume,
                            accumulated_trade_amount = EXCLUDED.accumulated_trade_amount,
                            change_rate = EXCLUDED.change_rate
                        """,
                        records,
                    )
                    inserted = len(records)

        return inserted, skipped, status

    async def save_daily_prices(
        self, *, daily_prices: list[StockDailyPrice]
    ) -> tuple[int, int]:
        if not daily_prices:
            return 0, 0

        short_codes = sorted({item.short_code for item in daily_prices})
        inserted = 0
        skipped = 0

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                stock_rows = await conn.fetch(
                    """
                    SELECT id, short_code
                    FROM public.stock
                    WHERE short_code = ANY($1::text[])
                        AND is_active = true
                    """,
                    short_codes,
                )
                stock_ids_by_code = {
                    row["short_code"]: row["id"] for row in stock_rows
                }

                records = []
                for item in daily_prices:
                    stock_id = stock_ids_by_code.get(item.short_code)
                    if stock_id is None:
                        skipped += 1
                        continue
                    records.append(
                        (
                            stock_id,
                            item.trading_date,
                            item.open_price,
                            item.high_price,
                            item.low_price,
                            item.close_price,
                            item.accumulated_volume,
                            item.accumulated_trade_amount,
                            item.change_amount,
                            item.change_rate,
                        )
                    )

                if records:
                    await conn.executemany(
                        """
                        INSERT INTO public.stock_daily_price (
                            stock_id,
                            trading_date,
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            accumulated_volume,
                            accumulated_trade_amount,
                            change_amount,
                            change_rate
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (stock_id, trading_date) DO UPDATE SET
                            open_price = EXCLUDED.open_price,
                            high_price = EXCLUDED.high_price,
                            low_price = EXCLUDED.low_price,
                            close_price = EXCLUDED.close_price,
                            accumulated_volume = EXCLUDED.accumulated_volume,
                            accumulated_trade_amount = EXCLUDED.accumulated_trade_amount,
                            change_amount = EXCLUDED.change_amount,
                            change_rate = EXCLUDED.change_rate
                        """,
                        records,
                    )
                    inserted = len(records)

        return inserted, skipped
