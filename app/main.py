from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.market_discovery import router as market_discovery_router
from app.api.market_leadership import router as market_leadership_router
from app.api.market_snapshots import router as market_snapshots_router
from app.core.config import get_settings
from app.db.pool import close_db_pool, init_db_pool
from app.kis.client import KisConfigurationError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await init_db_pool(app, settings)
    yield
    await close_db_pool(app)


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(KisConfigurationError)
async def kis_configuration_error_handler(
    _request: Request, exc: KisConfigurationError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RuntimeError)
async def runtime_error_handler(_request: Request, exc: RuntimeError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(httpx.HTTPError)
async def httpx_error_handler(_request: Request, exc: httpx.HTTPError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.include_router(market_discovery_router)
app.include_router(market_leadership_router)
app.include_router(market_snapshots_router)
