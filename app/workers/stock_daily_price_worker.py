from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import asyncpg

from app.core.config import Settings, get_settings
from app.kis.client import KisClient
from app.repositories.market_repository import MarketRepository
from app.schemas.market import DailyPriceCollectionResult
from app.services.market_service import MarketService


ProgressCallback = Callable[[int, int, str, bool], None]
STOCK_DAILY_PRICE_WORKER_LOCK_ID = 2026060702


class StockDailyPriceWorker:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def run(
        self,
        *,
        start_date: date,
        end_date: date,
        limit: int | None = None,
        dry_run: bool = False,
        request_interval_seconds: float | None = None,
        progress_callback: ProgressCallback | None = None,
        use_advisory_lock: bool = True,
    ) -> DailyPriceCollectionResult:
        pool = await asyncpg.create_pool(self._settings.database_url)
        try:
            if use_advisory_lock:
                await _acquire_worker_lock(pool)
            try:
                service = MarketService(
                    KisClient(self._settings),
                    MarketRepository(pool),
                )
                return await service.run_daily_price_collection(
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    dry_run=dry_run,
                    request_interval_seconds=(
                        request_interval_seconds
                        if request_interval_seconds is not None
                        else self._settings.kis_request_interval_seconds
                    ),
                    market_div_code_resolver=_build_daily_price_market_div_code_resolver(),
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
        STOCK_DAILY_PRICE_WORKER_LOCK_ID,
    )
    if not acquired:
        raise RuntimeError("Stock daily price worker is already running")


async def _release_worker_lock(pool: asyncpg.Pool) -> None:
    await pool.fetchval(
        "SELECT pg_advisory_unlock($1)",
        STOCK_DAILY_PRICE_WORKER_LOCK_ID,
    )


def _build_daily_price_market_div_code_resolver() -> Callable[[str], str]:
    nxt_codes = _load_nxt_master_codes()

    def resolve(short_code: str) -> str:
        normalized_code = short_code[1:] if short_code.startswith("A") else short_code
        return "UN" if normalized_code in nxt_codes else "J"

    return resolve


def _load_nxt_master_codes() -> set[str]:
    root_dir = Path(__file__).resolve().parents[2]
    master_dir = root_dir / "docs" / "kis" / "종목정보"
    paths = [
        master_dir / "nxt_kospi_code.mst",
        master_dir / "nxt_kosdaq_code.mst",
    ]
    codes: set[str] = set()
    for path in paths:
        if not path.exists():
            raise RuntimeError(f"NXT master file not found: {path}")
        with path.open("r", encoding="cp949", errors="ignore") as file:
            for line in file:
                code = line[:6].strip()
                if code:
                    codes.add(code)
    return codes
