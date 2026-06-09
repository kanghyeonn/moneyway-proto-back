from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import asyncpg

from app.core.config import Settings, get_settings
from app.kis.client import KisClient
from app.repositories.market_discovery_repository import MarketDiscoveryRepository
from app.repositories.market_repository import MarketRepository
from app.services.market_discovery_snapshot_service import (
    MarketDiscoverySnapshotService,
)


DiscoverySnapshotWorkerProgressCallback = Callable[[str, bool, str], None]
MARKET_DISCOVERY_SNAPSHOT_WORKER_LOCK_ID = 2026060901


class MarketDiscoverySnapshotWorker:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def run(
        self,
        *,
        snapshot_batch_at: datetime | None = None,
        ranking_limit: int = 30,
        popular_limit: int = 20,
        request_interval_seconds: float | None = None,
        progress_callback: DiscoverySnapshotWorkerProgressCallback | None = None,
        use_advisory_lock: bool = True,
    ) -> datetime:
        pool = await asyncpg.create_pool(self._settings.database_url)
        try:
            if use_advisory_lock:
                await _acquire_worker_lock(pool)
            try:
                service = MarketDiscoverySnapshotService(
                    KisClient(self._settings),
                    MarketRepository(pool),
                    MarketDiscoveryRepository(pool),
                )
                return await service.run_snapshot(
                    snapshot_batch_at=snapshot_batch_at,
                    ranking_limit=ranking_limit,
                    popular_limit=popular_limit,
                    request_interval_seconds=(
                        request_interval_seconds
                        if request_interval_seconds is not None
                        else self._settings.kis_request_interval_seconds
                    ),
                    progress_callback=progress_callback,
                )
            finally:
                if use_advisory_lock:
                    await _release_worker_lock(pool)
        finally:
            await pool.close()


async def _acquire_worker_lock(pool: asyncpg.Pool) -> None:
    acquired = await pool.fetchval(
        "SELECT pg_try_advisory_lock($1)",
        MARKET_DISCOVERY_SNAPSHOT_WORKER_LOCK_ID,
    )
    if not acquired:
        raise RuntimeError("Market discovery snapshot worker is already running")


async def _release_worker_lock(pool: asyncpg.Pool) -> None:
    await pool.fetchval(
        "SELECT pg_advisory_unlock($1)",
        MARKET_DISCOVERY_SNAPSHOT_WORKER_LOCK_ID,
    )
