from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

import asyncpg

from app.core.config import Settings, get_settings
from app.kis.client import KisClient
from app.repositories.market_repository import MarketRepository
from app.schemas.market import IntradaySnapshotRunResult
from app.services.market_service import MarketService


ProgressCallback = Callable[[int, int, str, bool], None]
MARKET_SNAPSHOT_WORKER_LOCK_ID = 2026060701


class MarketSnapshotWorker:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def run(
        self,
        *,
        snapshot_batch_at: datetime | None = None,
        limit: int | None = None,
        dry_run: bool = False,
        request_interval_seconds: float | None = None,
        progress_callback: ProgressCallback | None = None,
        use_advisory_lock: bool = True,
    ) -> IntradaySnapshotRunResult:
        pool = await asyncpg.create_pool(self._settings.database_url)
        try:
            if use_advisory_lock:
                await _acquire_worker_lock(pool)
            try:
                kis_settings = _market_snapshot_kis_settings(self._settings)
                service = MarketService(
                    KisClient(kis_settings),
                    MarketRepository(pool),
                )
                return await service.run_intraday_snapshot(
                    snapshot_batch_at=snapshot_batch_at,
                    interval_minutes=self._settings.market_snapshot_interval_minutes,
                    limit=limit,
                    dry_run=dry_run,
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
        MARKET_SNAPSHOT_WORKER_LOCK_ID,
    )
    if not acquired:
        raise RuntimeError("Market snapshot worker is already running")


async def _release_worker_lock(pool: asyncpg.Pool) -> None:
    await pool.fetchval(
        "SELECT pg_advisory_unlock($1)",
        MARKET_SNAPSHOT_WORKER_LOCK_ID,
    )


def _market_snapshot_kis_settings(settings: Settings) -> Settings:
    return replace(
        settings,
        kis_app_key=settings.kis_app_key_2,
        kis_app_secret=settings.kis_app_secret_2,
        kis_access_token=settings.kis_access_token_2,
        kis_access_token_expires_at=settings.kis_access_token_expires_at_2,
        kis_access_token_cache_key="KIS_ACCESS_TOKEN_2",
        kis_access_token_expires_at_cache_key="KIS_ACCESS_TOKEN_EXPIRES_AT_2",
    )
