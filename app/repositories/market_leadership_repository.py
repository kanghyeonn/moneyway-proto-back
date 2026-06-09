from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, NamedTuple

import asyncpg

from app.schemas.market import (
    CategoryStockItem,
    CategoryStockSort,
    LeadershipItem,
    LeadershipSnapshotItem,
    LeadershipSide,
    LeadershipSort,
)


MIN_LEADERSHIP_TRADE_AMOUNT = Decimal("100000000000")
MIN_DIRECTIONAL_LEADERSHIP_STOCK_COUNT = 3
LeadershipPriceSource = Literal["intraday", "daily"]


class StockPriceSourceSql(NamedTuple):
    table: str
    filter_column: str
    price_expression: str


class MarketLeadershipRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @property
    def min_leadership_trade_amount(self) -> Decimal:
        return MIN_LEADERSHIP_TRADE_AMOUNT

    async def latest_intraday_snapshot_batch_at(self) -> datetime | None:
        return await self._pool.fetchval(
            """
            SELECT snapshot_batch_at
            FROM public.stock_intraday_snapshot
            GROUP BY snapshot_batch_at
            ORDER BY snapshot_batch_at DESC
            LIMIT 1
            """
        )

    async def has_intraday_snapshot_batch_at(self, snapshot_batch_at: datetime) -> bool:
        return bool(
            await self._pool.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM public.stock_intraday_snapshot
                    WHERE snapshot_batch_at = $1
                    LIMIT 1
                )
                """,
                snapshot_batch_at,
            )
        )

    async def has_daily_price_on_date(self, trading_date: date) -> bool:
        return bool(
            await self._pool.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM public.stock_daily_price
                    WHERE trading_date = $1
                    LIMIT 1
                )
                """,
                trading_date,
            )
        )

    async def latest_daily_price_date_before(
        self, trading_date: date
    ) -> date | None:
        return await self._pool.fetchval(
            """
            SELECT MAX(trading_date)
            FROM public.stock_daily_price
            WHERE trading_date < $1
            """,
            trading_date,
        )

    async def daily_price_stock_count_on_date(self, trading_date: date) -> int:
        return await self._pool.fetchval(
            """
            SELECT COUNT(*)::int
            FROM public.stock_daily_price
            WHERE trading_date = $1
            """,
            trading_date,
        )

    async def leadership_snapshots(
        self, *, limit: int, snapshot_date: date | None = None
    ) -> list[LeadershipSnapshotItem]:
        date_filter = ""
        args: list[object] = [limit]
        if snapshot_date is not None:
            date_filter = (
                "WHERE (snapshot.snapshot_batch_at AT TIME ZONE 'Asia/Seoul')::date = $2"
            )
            args.append(snapshot_date)

        rows = await self._pool.fetch(
            f"""
            SELECT
                snapshot.snapshot_batch_at,
                COUNT(*)::int AS stock_count,
                batch.status
            FROM public.stock_intraday_snapshot AS snapshot
            LEFT JOIN public.market_snapshot_batch AS batch
                ON batch.snapshot_batch_at = snapshot.snapshot_batch_at
            {date_filter}
            GROUP BY snapshot.snapshot_batch_at, batch.status
            ORDER BY snapshot.snapshot_batch_at DESC
            LIMIT $1
            """,
            *args,
        )
        return [
            LeadershipSnapshotItem(
                snapshot_batch_at=row["snapshot_batch_at"],
                stock_count=row["stock_count"],
                status=row["status"],
            )
            for row in rows
        ]

    async def latest_leadership_snapshot(
        self, *, snapshot_date: date | None = None
    ) -> LeadershipSnapshotItem | None:
        items = await self.leadership_snapshots(limit=1, snapshot_date=snapshot_date)
        return items[0] if items else None

    async def latest_leadership_snapshot_before(
        self, *, snapshot_date: date
    ) -> LeadershipSnapshotItem | None:
        rows = await self._pool.fetch(
            """
            SELECT
                snapshot.snapshot_batch_at,
                COUNT(*)::int AS stock_count,
                batch.status
            FROM public.stock_intraday_snapshot AS snapshot
            LEFT JOIN public.market_snapshot_batch AS batch
                ON batch.snapshot_batch_at = snapshot.snapshot_batch_at
            WHERE (snapshot.snapshot_batch_at AT TIME ZONE 'Asia/Seoul')::date < $1
            GROUP BY snapshot.snapshot_batch_at, batch.status
            ORDER BY snapshot.snapshot_batch_at DESC
            LIMIT 1
            """,
            snapshot_date,
        )
        if not rows:
            return None
        row = rows[0]
        return LeadershipSnapshotItem(
            snapshot_batch_at=row["snapshot_batch_at"],
            stock_count=row["stock_count"],
            status=row["status"],
        )

    async def sector_leadership(
        self,
        *,
        snapshot_batch_at: datetime | None,
        side: LeadershipSide,
        top_n: int,
        sort: LeadershipSort,
        include_top_stocks: int = 0,
    ) -> tuple[datetime, list[LeadershipItem]]:
        batch_at = snapshot_batch_at or await self.latest_intraday_snapshot_batch_at()
        if batch_at is None:
            raise RuntimeError("No stock_intraday_snapshot batches are available")

        items = await self._daily_leadership(
            relation_table="public.stock_sector",
            category_table="public.sector",
            category_fk="sector_id",
            source="intraday",
            source_value=batch_at,
            side=side,
            top_n=top_n,
            sort=sort,
        )
        if include_top_stocks:
            await self._attach_top_stocks(
                items,
                relation_table="public.stock_sector",
                category_table="public.sector",
                category_fk="sector_id",
                source="intraday",
                source_value=batch_at,
                stock_top_n=include_top_stocks,
            )
        return batch_at, items

    async def sector_daily_price_leadership(
        self,
        *,
        trading_date: date,
        side: LeadershipSide,
        top_n: int,
        sort: LeadershipSort,
        include_top_stocks: int = 0,
    ) -> tuple[date, list[LeadershipItem]]:
        items = await self._daily_leadership(
            relation_table="public.stock_sector",
            category_table="public.sector",
            category_fk="sector_id",
            source="daily",
            source_value=trading_date,
            side=side,
            top_n=top_n,
            sort=sort,
        )
        if include_top_stocks:
            await self._attach_top_stocks(
                items,
                relation_table="public.stock_sector",
                category_table="public.sector",
                category_fk="sector_id",
                source="daily",
                source_value=trading_date,
                stock_top_n=include_top_stocks,
            )
        return trading_date, items

    async def theme_leadership(
        self,
        *,
        snapshot_batch_at: datetime | None,
        side: LeadershipSide,
        top_n: int,
        sort: LeadershipSort,
        include_top_stocks: int = 0,
    ) -> tuple[datetime, list[LeadershipItem]]:
        batch_at = snapshot_batch_at or await self.latest_intraday_snapshot_batch_at()
        if batch_at is None:
            raise RuntimeError("No stock_intraday_snapshot batches are available")

        items = await self._daily_leadership(
            relation_table="public.stock_theme",
            category_table="public.theme",
            category_fk="theme_id",
            source="intraday",
            source_value=batch_at,
            side=side,
            top_n=top_n,
            sort=sort,
        )
        if include_top_stocks:
            await self._attach_top_stocks(
                items,
                relation_table="public.stock_theme",
                category_table="public.theme",
                category_fk="theme_id",
                source="intraday",
                source_value=batch_at,
                stock_top_n=include_top_stocks,
            )
        return batch_at, items

    async def theme_daily_price_leadership(
        self,
        *,
        trading_date: date,
        side: LeadershipSide,
        top_n: int,
        sort: LeadershipSort,
        include_top_stocks: int = 0,
    ) -> tuple[date, list[LeadershipItem]]:
        items = await self._daily_leadership(
            relation_table="public.stock_theme",
            category_table="public.theme",
            category_fk="theme_id",
            source="daily",
            source_value=trading_date,
            side=side,
            top_n=top_n,
            sort=sort,
        )
        if include_top_stocks:
            await self._attach_top_stocks(
                items,
                relation_table="public.stock_theme",
                category_table="public.theme",
                category_fk="theme_id",
                source="daily",
                source_value=trading_date,
                stock_top_n=include_top_stocks,
            )
        return trading_date, items

    async def leadership_status(self) -> LeadershipSnapshotItem:
        latest = await self.latest_leadership_snapshot()
        if latest is None:
            raise RuntimeError("No stock_intraday_snapshot batches are available")
        return latest

    async def sector_leadership_summary(
        self,
        *,
        snapshot_batch_at: datetime | None,
    ) -> tuple[datetime, int, int, LeadershipItem | None, LeadershipItem | None]:
        return await self._leadership_summary(
            relation_table="public.stock_sector",
            category_table="public.sector",
            category_fk="sector_id",
            snapshot_batch_at=snapshot_batch_at,
        )

    async def sector_daily_price_leadership_summary(
        self,
        *,
        trading_date: date,
    ) -> tuple[date, int, int, LeadershipItem | None, LeadershipItem | None]:
        _basis, bullish_count, bearish_count, top_bullish, top_bearish = (
            await self._leadership_summary(
                relation_table="public.stock_sector",
                category_table="public.sector",
                category_fk="sector_id",
                source="daily",
                source_value=trading_date,
            )
        )
        return trading_date, bullish_count, bearish_count, top_bullish, top_bearish

    async def theme_leadership_summary(
        self,
        *,
        snapshot_batch_at: datetime | None,
    ) -> tuple[datetime, int, int, LeadershipItem | None, LeadershipItem | None]:
        return await self._leadership_summary(
            relation_table="public.stock_theme",
            category_table="public.theme",
            category_fk="theme_id",
            snapshot_batch_at=snapshot_batch_at,
        )

    async def theme_daily_price_leadership_summary(
        self,
        *,
        trading_date: date,
    ) -> tuple[date, int, int, LeadershipItem | None, LeadershipItem | None]:
        _basis, bullish_count, bearish_count, top_bullish, top_bearish = (
            await self._leadership_summary(
                relation_table="public.stock_theme",
                category_table="public.theme",
                category_fk="theme_id",
                source="daily",
                source_value=trading_date,
            )
        )
        return trading_date, bullish_count, bearish_count, top_bullish, top_bearish

    async def sector_stocks(
        self,
        *,
        sector_id: int,
        snapshot_batch_at: datetime | None,
        sort: CategoryStockSort,
    ) -> tuple[datetime, str, list[CategoryStockItem]]:
        batch_at = snapshot_batch_at or await self.latest_intraday_snapshot_batch_at()
        if batch_at is None:
            raise RuntimeError("No stock_intraday_snapshot batches are available")

        return await self._category_stocks(
            relation_table="public.stock_sector",
            category_table="public.sector",
            category_fk="sector_id",
            category_id=sector_id,
            source="intraday",
            source_value=batch_at,
            sort=sort,
        )

    async def sector_daily_price_stocks(
        self,
        *,
        sector_id: int,
        trading_date: date,
        sort: CategoryStockSort,
    ) -> tuple[date, str, list[CategoryStockItem]]:
        return await self._category_stocks(
            relation_table="public.stock_sector",
            category_table="public.sector",
            category_fk="sector_id",
            category_id=sector_id,
            source="daily",
            source_value=trading_date,
            sort=sort,
        )

    async def theme_stocks(
        self,
        *,
        theme_id: int,
        snapshot_batch_at: datetime | None,
        sort: CategoryStockSort,
    ) -> tuple[datetime, str, list[CategoryStockItem]]:
        batch_at = snapshot_batch_at or await self.latest_intraday_snapshot_batch_at()
        if batch_at is None:
            raise RuntimeError("No stock_intraday_snapshot batches are available")

        return await self._category_stocks(
            relation_table="public.stock_theme",
            category_table="public.theme",
            category_fk="theme_id",
            category_id=theme_id,
            source="intraday",
            source_value=batch_at,
            sort=sort,
        )

    async def theme_daily_price_stocks(
        self,
        *,
        theme_id: int,
        trading_date: date,
        sort: CategoryStockSort,
    ) -> tuple[date, str, list[CategoryStockItem]]:
        return await self._category_stocks(
            relation_table="public.stock_theme",
            category_table="public.theme",
            category_fk="theme_id",
            category_id=theme_id,
            source="daily",
            source_value=trading_date,
            sort=sort,
        )

    async def _category_stocks(
        self,
        *,
        relation_table: str,
        category_table: str,
        category_fk: str,
        category_id: int,
        source: LeadershipPriceSource,
        source_value: datetime | date,
        sort: CategoryStockSort,
    ) -> tuple[datetime | date, str, list[CategoryStockItem]]:
        order_direction = "DESC" if sort == "change_rate_desc" else "ASC"
        price_source = _stock_price_source_sql(source)
        query = f"""
            SELECT
                category.name AS category_name,
                stock.short_code,
                stock.name,
                {price_source.price_expression} AS price,
                stock_price.change_rate,
                stock_price.accumulated_volume,
                stock_price.accumulated_trade_amount
            FROM {price_source.table} AS stock_price
            JOIN public.stock
                ON stock.id = stock_price.stock_id
            JOIN {relation_table} AS stock_category
                ON stock_category.stock_id = stock.id
            JOIN {category_table} AS category
                ON category.id = stock_category.{category_fk}
            WHERE stock_price.{price_source.filter_column} = $1
                AND category.id = $2
            ORDER BY
                stock_price.change_rate {order_direction} NULLS LAST,
                stock_price.accumulated_trade_amount DESC,
                stock.short_code ASC
        """
        rows = await self._pool.fetch(query, source_value, category_id)
        if not rows:
            category_name = await self._pool.fetchval(
                f"SELECT name FROM {category_table} WHERE id = $1",
                category_id,
            )
            if category_name is None:
                raise RuntimeError(f"Category not found: {category_id}")
            return source_value, category_name, []

        return (
            source_value,
            rows[0]["category_name"],
            [
                CategoryStockItem(
                    short_code=row["short_code"],
                    name=row["name"],
                    price=row["price"],
                    change_rate=row["change_rate"],
                    accumulated_volume=row["accumulated_volume"],
                    accumulated_trade_amount=row["accumulated_trade_amount"],
                )
                for row in rows
            ],
        )

    async def _attach_top_stocks(
        self,
        items: list[LeadershipItem],
        *,
        relation_table: str,
        category_table: str,
        category_fk: str,
        source: LeadershipPriceSource,
        source_value: datetime | date,
        stock_top_n: int,
    ) -> None:
        if not items:
            return

        category_ids = [item.id for item in items]
        price_source = _stock_price_source_sql(source)
        query = f"""
            WITH ranked AS (
                SELECT
                    category.id AS category_id,
                    stock.short_code,
                    stock.name,
                    {price_source.price_expression} AS price,
                    stock_price.change_rate,
                    stock_price.accumulated_volume,
                    stock_price.accumulated_trade_amount,
                    ROW_NUMBER() OVER (
                        PARTITION BY category.id
                        ORDER BY
                            stock_price.change_rate DESC NULLS LAST,
                            stock_price.accumulated_trade_amount DESC,
                            stock.short_code ASC
                    ) AS stock_rank
                FROM {price_source.table} AS stock_price
                JOIN public.stock
                    ON stock.id = stock_price.stock_id
                JOIN {relation_table} AS stock_category
                    ON stock_category.stock_id = stock.id
                JOIN {category_table} AS category
                    ON category.id = stock_category.{category_fk}
                WHERE stock_price.{price_source.filter_column} = $1
                    AND category.id = ANY($2::int[])
            )
            SELECT
                category_id,
                short_code,
                name,
                price,
                change_rate,
                accumulated_volume,
                accumulated_trade_amount
            FROM ranked
            WHERE stock_rank <= $3
            ORDER BY category_id, stock_rank
        """
        rows = await self._pool.fetch(
            query,
            source_value,
            category_ids,
            stock_top_n,
        )
        stocks_by_category: dict[int, list[CategoryStockItem]] = {
            category_id: [] for category_id in category_ids
        }
        for row in rows:
            stocks_by_category[row["category_id"]].append(
                CategoryStockItem(
                    short_code=row["short_code"],
                    name=row["name"],
                    price=row["price"],
                    change_rate=row["change_rate"],
                    accumulated_volume=row["accumulated_volume"],
                    accumulated_trade_amount=row["accumulated_trade_amount"],
                )
            )

        for item in items:
            item.top_stocks = stocks_by_category.get(item.id, [])

    async def _daily_leadership(
        self,
        *,
        relation_table: str,
        category_table: str,
        category_fk: str,
        source: LeadershipPriceSource,
        source_value: datetime | date,
        side: LeadershipSide,
        top_n: int,
        sort: LeadershipSort,
    ) -> list[LeadershipItem]:
        order_by = _leadership_order_by(sort)
        price_source = _stock_price_source_sql(source)
        query = f"""
            WITH stock_flow AS (
                SELECT
                    stock_id,
                    accumulated_trade_amount AS trade_amount,
                    change_rate / 100 AS change_rate
                FROM {price_source.table}
                WHERE {price_source.filter_column} = $1
                    AND accumulated_trade_amount > 0
                    AND change_rate IS NOT NULL
            ),
            category_stock_flow AS (
                SELECT
                    category.id,
                    category.name,
                    stock_flow.stock_id,
                    stock_flow.trade_amount,
                    stock_flow.change_rate
                FROM stock_flow
                JOIN {relation_table} AS stock_category
                    ON stock_category.stock_id = stock_flow.stock_id
                JOIN {category_table} AS category
                    ON category.id = stock_category.{category_fk}
            ),
            category_flow AS (
                SELECT
                    id,
                    name,
                    SUM(trade_amount) AS trade_amount,
                    SUM(trade_amount * change_rate)
                        / NULLIF(SUM(trade_amount), 0) AS weighted_change_rate,
                    AVG((change_rate > 0)::int::numeric) AS advance_ratio,
                    SUM(
                        CASE WHEN change_rate > 0
                        THEN trade_amount ELSE 0 END
                    ) / NULLIF(SUM(trade_amount), 0) AS up_trade_amount_ratio,
                    AVG((change_rate < 0)::int::numeric) AS decline_ratio,
                    SUM(
                        CASE WHEN change_rate < 0
                        THEN trade_amount ELSE 0 END
                    ) / NULLIF(SUM(trade_amount), 0) AS down_trade_amount_ratio,
                    COUNT(*) AS stock_count,
                    SUM(
                        CASE WHEN change_rate > 0
                        THEN 1 ELSE 0 END
                    )::int AS advancing_stock_count,
                    SUM(
                        CASE WHEN change_rate < 0
                        THEN 1 ELSE 0 END
                    )::int AS declining_stock_count,
                    MAX(trade_amount)
                        / NULLIF(SUM(trade_amount), 0) AS top1_trade_amount_share
                FROM category_stock_flow
                GROUP BY id, name
            ),
            penalized AS (
                SELECT
                    *,
                    CASE
                        WHEN top1_trade_amount_share <= 0.4 THEN 1::numeric
                        WHEN top1_trade_amount_share >= 0.8 THEN 0.5::numeric
                        ELSE 1 - ((top1_trade_amount_share - 0.4) / 0.4) * 0.5
                    END AS concentration_penalty
                FROM category_flow
            ),
            scored AS (
                SELECT
                    *,
                    CASE
                        WHEN $2 = 'bullish' THEN
                            LN(1 + trade_amount)
                            * GREATEST(weighted_change_rate, 0)
                            * COALESCE(up_trade_amount_ratio, 0)
                            * LEAST(1, COALESCE(advance_ratio, 0) / 0.6)
                            * concentration_penalty
                        ELSE
                            LN(1 + trade_amount)
                            * ABS(LEAST(weighted_change_rate, 0))
                            * COALESCE(down_trade_amount_ratio, 0)
                            * LEAST(1, COALESCE(decline_ratio, 0) / 0.6)
                            * concentration_penalty
                    END AS score
                FROM penalized
            )
            SELECT
                id,
                name,
                $2::text AS side,
                score,
                trade_amount,
                weighted_change_rate,
                advance_ratio,
                up_trade_amount_ratio,
                decline_ratio,
                down_trade_amount_ratio,
                stock_count,
                top1_trade_amount_share,
                concentration_penalty
            FROM scored
            WHERE stock_count >= 3
                AND trade_amount >= $4
                AND (
                    (
                        $2 = 'bullish'
                        AND weighted_change_rate > 0
                        AND advancing_stock_count >= $5
                    )
                    OR (
                        $2 = 'bearish'
                        AND weighted_change_rate < 0
                        AND declining_stock_count >= $5
                    )
                )
            ORDER BY {order_by}
            LIMIT $3
        """
        rows = await self._pool.fetch(
            query,
            source_value,
            side,
            top_n,
            MIN_LEADERSHIP_TRADE_AMOUNT,
            MIN_DIRECTIONAL_LEADERSHIP_STOCK_COUNT,
        )
        return [
            LeadershipItem(
                id=row["id"],
                name=row["name"],
                side=row["side"],
                score=row["score"] or Decimal("0"),
                trade_amount=row["trade_amount"] or Decimal("0"),
                weighted_change_rate=row["weighted_change_rate"],
                advance_ratio=row["advance_ratio"],
                up_trade_amount_ratio=row["up_trade_amount_ratio"],
                decline_ratio=row["decline_ratio"],
                down_trade_amount_ratio=row["down_trade_amount_ratio"],
                stock_count=row["stock_count"],
                top1_trade_amount_share=row["top1_trade_amount_share"],
                concentration_penalty=row["concentration_penalty"],
            )
            for row in rows
        ]

    async def _leadership_summary(
        self,
        *,
        relation_table: str,
        category_table: str,
        category_fk: str,
        snapshot_batch_at: datetime | None = None,
        source: LeadershipPriceSource = "intraday",
        source_value: datetime | date | None = None,
    ) -> tuple[datetime | date, int, int, LeadershipItem | None, LeadershipItem | None]:
        resolved_source_value = source_value
        if source == "intraday" and resolved_source_value is None:
            resolved_source_value = (
                snapshot_batch_at or await self.latest_intraday_snapshot_batch_at()
            )
        if resolved_source_value is None:
            raise RuntimeError("No stock_intraday_snapshot batches are available")

        bullish = await self._daily_leadership(
            relation_table=relation_table,
            category_table=category_table,
            category_fk=category_fk,
            source=source,
            source_value=resolved_source_value,
            side="bullish",
            top_n=10000,
            sort="score_desc",
        )
        bearish = await self._daily_leadership(
            relation_table=relation_table,
            category_table=category_table,
            category_fk=category_fk,
            source=source,
            source_value=resolved_source_value,
            side="bearish",
            top_n=10000,
            sort="score_desc",
        )
        return (
            resolved_source_value,
            len(bullish),
            len(bearish),
            bullish[0] if bullish else None,
            bearish[0] if bearish else None,
        )


def _leadership_order_by(sort: LeadershipSort) -> str:
    if sort == "trade_amount_desc":
        return "trade_amount DESC, score DESC, name ASC"
    if sort == "weighted_change_rate_desc":
        return "weighted_change_rate DESC NULLS LAST, score DESC, name ASC"
    if sort == "weighted_change_rate_asc":
        return "weighted_change_rate ASC NULLS LAST, score DESC, name ASC"
    return "score DESC, name ASC"


def _stock_price_source_sql(source: LeadershipPriceSource) -> StockPriceSourceSql:
    if source == "intraday":
        return StockPriceSourceSql(
            table="public.stock_intraday_snapshot",
            filter_column="snapshot_batch_at",
            price_expression="stock_price.price",
        )
    return StockPriceSourceSql(
        table="public.stock_daily_price",
        filter_column="trading_date",
        price_expression="stock_price.close_price",
    )
