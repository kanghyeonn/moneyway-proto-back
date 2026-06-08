from __future__ import annotations

import asyncpg
from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.db.pool import get_pool
from app.kis.client import KisClient
from app.repositories.auth_repository import AuthRepository
from app.repositories.market_leadership_repository import MarketLeadershipRepository
from app.repositories.market_repository import MarketRepository
from app.services.auth_service import AuthService
from app.services.market_discovery_service import MarketDiscoveryService
from app.services.market_leadership_service import MarketLeadershipService
from app.services.market_service import MarketService


def get_kis_client(request: Request, settings: Settings = Depends(get_settings)) -> KisClient:
    client = getattr(request.app.state, "kis_client", None)
    if client is None:
        client = KisClient(settings)
        request.app.state.kis_client = client
    return client


def get_market_repository(pool: asyncpg.Pool = Depends(get_pool)) -> MarketRepository:
    return MarketRepository(pool)


def get_market_leadership_repository(
    pool: asyncpg.Pool = Depends(get_pool),
) -> MarketLeadershipRepository:
    return MarketLeadershipRepository(pool)


def get_auth_repository(pool: asyncpg.Pool = Depends(get_pool)) -> AuthRepository:
    return AuthRepository(pool)


def get_market_service(
    kis_client: KisClient = Depends(get_kis_client),
    repository: MarketRepository = Depends(get_market_repository),
) -> MarketService:
    return MarketService(kis_client, repository)


def get_market_discovery_service(
    kis_client: KisClient = Depends(get_kis_client),
) -> MarketDiscoveryService:
    return MarketDiscoveryService(kis_client)


def get_market_leadership_service(
    repository: MarketLeadershipRepository = Depends(get_market_leadership_repository),
) -> MarketLeadershipService:
    return MarketLeadershipService(repository)


def get_auth_service(
    repository: AuthRepository = Depends(get_auth_repository),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(repository, settings)
