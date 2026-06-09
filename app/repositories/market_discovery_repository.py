from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Literal

import asyncpg

from app.schemas.market_discovery import (
    DiscoveryAdvanceDeclineResponse,
    DiscoveryIndexItem,
    DiscoveryPopularSearchItem,
    DiscoveryRankingItem,
    DiscoveryRankingType,
)


DiscoverySnapshotStatus = Literal["running", "completed", "partial", "failed"]
READY_SNAPSHOT_STATUSES = ("completed", "partial")


class MarketDiscoveryRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def begin_snapshot_batch(self, *, snapshot_batch_at: datetime) -> None:
        await self._pool.execute(
            """
            INSERT INTO public.market_discovery_snapshot_batch (
                snapshot_batch_at,
                status,
                started_at
            )
            VALUES ($1, 'running', now())
            ON CONFLICT (snapshot_batch_at) DO UPDATE SET
                status = 'running',
                started_at = now(),
                finished_at = NULL,
                ranking_success_count = 0,
                ranking_failed_count = 0,
                index_success_count = 0,
                index_failed_count = 0,
                popular_success_count = 0,
                popular_failed_count = 0,
                error_message = NULL
            """,
            snapshot_batch_at,
        )

    async def save_snapshot(
        self,
        *,
        snapshot_batch_at: datetime,
        status: DiscoverySnapshotStatus,
        rankings: dict[DiscoveryRankingType, list[DiscoveryRankingItem]],
        indices: list[DiscoveryIndexItem],
        popular_searches: list[DiscoveryPopularSearchItem],
        index_counts_by_code: dict[str, tuple[int, int, int]] | None = None,
        ranking_success_count: int | None = None,
        ranking_failed_count: int = 0,
        index_success_count: int | None = None,
        index_failed_count: int = 0,
        popular_success_count: int | None = None,
        popular_failed_count: int = 0,
        error_message: str | None = None,
    ) -> None:
        ranking_success_count = (
            len(rankings) if ranking_success_count is None else ranking_success_count
        )
        index_success_count = 1 if index_success_count is None and indices else (
            0 if index_success_count is None else index_success_count
        )
        popular_success_count = (
            1
            if popular_success_count is None and popular_searches
            else 0 if popular_success_count is None else popular_success_count
        )

        async with self._pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO public.market_discovery_snapshot_batch (
                        snapshot_batch_at,
                        status,
                        started_at,
                        finished_at,
                        ranking_success_count,
                        ranking_failed_count,
                        index_success_count,
                        index_failed_count,
                        popular_success_count,
                        popular_failed_count,
                        error_message
                    )
                    VALUES (
                        $1, $2, now(), now(), $3, $4, $5, $6, $7, $8, $9
                    )
                    ON CONFLICT (snapshot_batch_at) DO UPDATE SET
                        status = EXCLUDED.status,
                        finished_at = EXCLUDED.finished_at,
                        ranking_success_count = EXCLUDED.ranking_success_count,
                        ranking_failed_count = EXCLUDED.ranking_failed_count,
                        index_success_count = EXCLUDED.index_success_count,
                        index_failed_count = EXCLUDED.index_failed_count,
                        popular_success_count = EXCLUDED.popular_success_count,
                        popular_failed_count = EXCLUDED.popular_failed_count,
                        error_message = EXCLUDED.error_message
                    """,
                    snapshot_batch_at,
                    status,
                    ranking_success_count,
                    ranking_failed_count,
                    index_success_count,
                    index_failed_count,
                    popular_success_count,
                    popular_failed_count,
                    error_message,
                )

                await connection.execute(
                    """
                    DELETE FROM public.market_discovery_ranking_snapshot
                    WHERE snapshot_batch_at = $1
                    """,
                    snapshot_batch_at,
                )
                await connection.execute(
                    """
                    DELETE FROM public.market_discovery_index_snapshot
                    WHERE snapshot_batch_at = $1
                    """,
                    snapshot_batch_at,
                )
                await connection.execute(
                    """
                    DELETE FROM public.market_discovery_popular_search_snapshot
                    WHERE snapshot_batch_at = $1
                    """,
                    snapshot_batch_at,
                )

                ranking_records = [
                    (
                        snapshot_batch_at,
                        ranking_type,
                        item.rank,
                        item.short_code,
                        item.name,
                        _decimal_or_none(item.price),
                        _decimal_or_none(item.trade_amount),
                        item.volume,
                        _decimal_or_none(item.change_rate),
                        item.direction,
                        _jsonb({}),
                    )
                    for ranking_type, items in rankings.items()
                    for item in items
                ]
                if ranking_records:
                    await connection.executemany(
                        """
                        INSERT INTO public.market_discovery_ranking_snapshot (
                            snapshot_batch_at,
                            ranking_type,
                            rank,
                            short_code,
                            name,
                            price,
                            trade_amount,
                            volume,
                            change_rate,
                            direction,
                            raw
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        """,
                        ranking_records,
                    )

                index_records = [
                    (
                        snapshot_batch_at,
                        item.code,
                        item.label,
                        _decimal_or_none(item.value),
                        _decimal_or_none(item.change),
                        _decimal_or_none(item.change_rate),
                        item.direction,
                        _index_counts(index_counts_by_code, item.code)[0],
                        _index_counts(index_counts_by_code, item.code)[1],
                        _index_counts(index_counts_by_code, item.code)[2],
                        _jsonb({}),
                    )
                    for item in indices
                ]
                if index_records:
                    await connection.executemany(
                        """
                        INSERT INTO public.market_discovery_index_snapshot (
                            snapshot_batch_at,
                            code,
                            label,
                            value,
                            change,
                            change_rate,
                            direction,
                            up_count,
                            down_count,
                            unchanged_count,
                            raw
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        """,
                        index_records,
                    )

                popular_records = [
                    (
                        snapshot_batch_at,
                        item.rank,
                        item.short_code,
                        item.name,
                        _decimal_or_none(item.change_rate),
                        item.direction,
                        _jsonb({}),
                    )
                    for item in popular_searches
                ]
                if popular_records:
                    await connection.executemany(
                        """
                        INSERT INTO public.market_discovery_popular_search_snapshot (
                            snapshot_batch_at,
                            rank,
                            short_code,
                            name,
                            change_rate,
                            direction,
                            raw
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        popular_records,
                    )

    async def latest_snapshot_batch_at(self) -> datetime | None:
        return await self._pool.fetchval(
            """
            SELECT snapshot_batch_at
            FROM public.market_discovery_snapshot_batch
            WHERE status = ANY($1::text[])
            ORDER BY snapshot_batch_at DESC
            LIMIT 1
            """,
            list(READY_SNAPSHOT_STATUSES),
        )

    async def latest_ranking_batch_at(
        self, *, ranking_type: DiscoveryRankingType
    ) -> datetime | None:
        return await self._pool.fetchval(
            """
            SELECT ranking.snapshot_batch_at
            FROM public.market_discovery_ranking_snapshot AS ranking
            JOIN public.market_discovery_snapshot_batch AS batch
                ON batch.snapshot_batch_at = ranking.snapshot_batch_at
            WHERE batch.status = ANY($1::text[])
                AND ranking.ranking_type = $2
            GROUP BY ranking.snapshot_batch_at
            ORDER BY ranking.snapshot_batch_at DESC
            LIMIT 1
            """,
            list(READY_SNAPSHOT_STATUSES),
            ranking_type,
        )

    async def ranking_items(
        self,
        *,
        ranking_type: DiscoveryRankingType,
        limit: int,
        snapshot_batch_at: datetime | None = None,
    ) -> tuple[datetime, list[DiscoveryRankingItem]]:
        batch_at = snapshot_batch_at or await self.latest_ranking_batch_at(
            ranking_type=ranking_type
        )
        if batch_at is None:
            raise RuntimeError("No market discovery ranking snapshots are available")

        rows = await self._pool.fetch(
            """
            SELECT
                rank,
                short_code,
                name,
                price,
                trade_amount,
                volume,
                change_rate,
                direction
            FROM public.market_discovery_ranking_snapshot
            WHERE snapshot_batch_at = $1
                AND ranking_type = $2
            ORDER BY rank
            LIMIT $3
            """,
            batch_at,
            ranking_type,
            limit,
        )
        return batch_at, [
            DiscoveryRankingItem(
                rank=row["rank"],
                short_code=row["short_code"],
                name=row["name"],
                price=row["price"],
                trade_amount=row["trade_amount"],
                volume=row["volume"],
                change_rate=row["change_rate"],
                direction=row["direction"],
            )
            for row in rows
        ]

    async def latest_index_batch_at(self) -> datetime | None:
        return await self._pool.fetchval(
            """
            SELECT index_snapshot.snapshot_batch_at
            FROM public.market_discovery_index_snapshot AS index_snapshot
            JOIN public.market_discovery_snapshot_batch AS batch
                ON batch.snapshot_batch_at = index_snapshot.snapshot_batch_at
            WHERE batch.status = ANY($1::text[])
            GROUP BY index_snapshot.snapshot_batch_at
            ORDER BY index_snapshot.snapshot_batch_at DESC
            LIMIT 1
            """,
            list(READY_SNAPSHOT_STATUSES),
        )

    async def index_items(
        self, *, snapshot_batch_at: datetime | None = None
    ) -> tuple[datetime, list[DiscoveryIndexItem]]:
        batch_at = snapshot_batch_at or await self.latest_index_batch_at()
        if batch_at is None:
            raise RuntimeError("No market discovery index snapshots are available")

        rows = await self._pool.fetch(
            """
            SELECT
                code,
                label,
                value,
                change,
                change_rate,
                direction
            FROM public.market_discovery_index_snapshot
            WHERE snapshot_batch_at = $1
            ORDER BY code
            """,
            batch_at,
        )
        return batch_at, [
            DiscoveryIndexItem(
                code=row["code"],
                label=row["label"],
                value=row["value"],
                change=row["change"],
                change_rate=row["change_rate"],
                direction=row["direction"],
            )
            for row in rows
        ]

    async def advance_decline(
        self,
        *,
        snapshot_batch_at: datetime | None = None,
    ) -> DiscoveryAdvanceDeclineResponse:
        if snapshot_batch_at is not None:
            current = await self._aggregate_advance_decline(snapshot_batch_at)
            if current is None or current["row_count"] == 0:
                raise RuntimeError("No market discovery index snapshots are available")
            return DiscoveryAdvanceDeclineResponse(
                up_count=current["up_count"],
                up_delta=0,
                down_count=current["down_count"],
                down_delta=0,
                unchanged_count=current["unchanged_count"],
                basis_time=snapshot_batch_at,
            )

        rows = await self._pool.fetch(
            """
            WITH latest_batches AS (
                SELECT index_snapshot.snapshot_batch_at
                FROM public.market_discovery_index_snapshot AS index_snapshot
                JOIN public.market_discovery_snapshot_batch AS batch
                    ON batch.snapshot_batch_at = index_snapshot.snapshot_batch_at
                WHERE batch.status = ANY($1::text[])
                GROUP BY index_snapshot.snapshot_batch_at
                ORDER BY index_snapshot.snapshot_batch_at DESC
                LIMIT 2
            ),
            ranked_batches AS (
                SELECT
                    snapshot_batch_at,
                    ROW_NUMBER() OVER (
                        ORDER BY snapshot_batch_at DESC
                    ) AS row_number
                FROM latest_batches
            )
            SELECT
                ranked_batches.row_number,
                ranked_batches.snapshot_batch_at,
                COALESCE(SUM(index_snapshot.up_count), 0)::int AS up_count,
                COALESCE(SUM(index_snapshot.down_count), 0)::int AS down_count,
                COALESCE(SUM(index_snapshot.unchanged_count), 0)::int
                    AS unchanged_count
            FROM ranked_batches
            JOIN public.market_discovery_index_snapshot AS index_snapshot
                ON index_snapshot.snapshot_batch_at = ranked_batches.snapshot_batch_at
            GROUP BY ranked_batches.row_number, ranked_batches.snapshot_batch_at
            ORDER BY ranked_batches.row_number
            """,
            list(READY_SNAPSHOT_STATUSES),
        )
        if not rows:
            raise RuntimeError("No market discovery index snapshots are available")

        current = rows[0]
        previous = rows[1] if len(rows) > 1 else None
        previous_up_count = (
            previous["up_count"] if previous is not None else current["up_count"]
        )
        previous_down_count = (
            previous["down_count"] if previous is not None else current["down_count"]
        )
        return DiscoveryAdvanceDeclineResponse(
            up_count=current["up_count"],
            up_delta=current["up_count"] - previous_up_count,
            down_count=current["down_count"],
            down_delta=current["down_count"] - previous_down_count,
            unchanged_count=current["unchanged_count"],
            basis_time=current["snapshot_batch_at"],
        )

    async def latest_popular_search_batch_at(self) -> datetime | None:
        return await self._pool.fetchval(
            """
            SELECT popular.snapshot_batch_at
            FROM public.market_discovery_popular_search_snapshot AS popular
            JOIN public.market_discovery_snapshot_batch AS batch
                ON batch.snapshot_batch_at = popular.snapshot_batch_at
            WHERE batch.status = ANY($1::text[])
            GROUP BY popular.snapshot_batch_at
            ORDER BY popular.snapshot_batch_at DESC
            LIMIT 1
            """,
            list(READY_SNAPSHOT_STATUSES),
        )

    async def popular_search_items(
        self,
        *,
        limit: int,
        snapshot_batch_at: datetime | None = None,
    ) -> tuple[datetime, list[DiscoveryPopularSearchItem]]:
        batch_at = snapshot_batch_at or await self.latest_popular_search_batch_at()
        if batch_at is None:
            raise RuntimeError(
                "No market discovery popular search snapshots are available"
            )

        rows = await self._pool.fetch(
            """
            SELECT
                rank,
                short_code,
                name,
                change_rate,
                direction
            FROM public.market_discovery_popular_search_snapshot
            WHERE snapshot_batch_at = $1
            ORDER BY rank
            LIMIT $2
            """,
            batch_at,
            limit,
        )
        return batch_at, [
            DiscoveryPopularSearchItem(
                rank=row["rank"],
                short_code=row["short_code"],
                name=row["name"],
                change_rate=row["change_rate"],
                direction=row["direction"],
            )
            for row in rows
        ]

    async def _aggregate_advance_decline(
        self, snapshot_batch_at: datetime
    ) -> asyncpg.Record | None:
        return await self._pool.fetchrow(
            """
            SELECT
                COUNT(*)::int AS row_count,
                COALESCE(SUM(up_count), 0)::int AS up_count,
                COALESCE(SUM(down_count), 0)::int AS down_count,
                COALESCE(SUM(unchanged_count), 0)::int AS unchanged_count
            FROM public.market_discovery_index_snapshot
            WHERE snapshot_batch_at = $1
            """,
            snapshot_batch_at,
        )


def _jsonb(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _decimal_or_none(value: float | int | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _index_counts(
    counts_by_code: dict[str, tuple[int, int, int]] | None,
    code: str,
) -> tuple[int, int, int]:
    if counts_by_code is None:
        return 0, 0, 0
    return counts_by_code.get(code, (0, 0, 0))
