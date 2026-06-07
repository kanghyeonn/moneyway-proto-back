from __future__ import annotations

import asyncpg
from fastapi import FastAPI, Request

from app.core.config import Settings, get_settings


async def init_db_pool(app: FastAPI, settings: Settings) -> None:
    if not settings.database_url:
        app.state.db_pool = None
        return

    app.state.db_pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=10,
        command_timeout=10,
    )


async def close_db_pool(app: FastAPI) -> None:
    pool = getattr(app.state, "db_pool", None)
    if pool is not None:
        await pool.close()


def get_pool(request: Request) -> asyncpg.Pool:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise RuntimeError("DATABASE_URL is required for DB-backed market endpoints")
    return pool
