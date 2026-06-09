from __future__ import annotations

import asyncpg
from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.db.pool import get_pool
from app.kis.client import KisClient
from app.repositories.auth_repository import AuthRepository
from app.repositories.market_discovery_repository import MarketDiscoveryRepository
from app.repositories.market_leadership_repository import MarketLeadershipRepository
from app.repositories.market_repository import MarketRepository
from app.services.auth_service import AuthService
from app.services.market_discovery_service import MarketDiscoveryService
from app.services.market_leadership_service import MarketLeadershipService


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


def get_market_discovery_repository(
    pool: asyncpg.Pool = Depends(get_pool),
) -> MarketDiscoveryRepository:
    return MarketDiscoveryRepository(pool)


def get_auth_repository(pool: asyncpg.Pool = Depends(get_pool)) -> AuthRepository:
    return AuthRepository(pool)


def get_market_discovery_service(
    discovery_repository: MarketDiscoveryRepository = Depends(
        get_market_discovery_repository
    ),
) -> MarketDiscoveryService:
    return MarketDiscoveryService(discovery_repository)


def get_market_leadership_service(
    repository: MarketLeadershipRepository = Depends(get_market_leadership_repository),
) -> MarketLeadershipService:
    return MarketLeadershipService(repository)


def get_auth_service(
    repository: AuthRepository = Depends(get_auth_repository),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(repository, settings)
